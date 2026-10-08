# Standard Library
import asyncio
import logging
from http import HTTPStatus
from types import SimpleNamespace
from typing import TYPE_CHECKING, Union

# Third Party
import aiohttp
from asgiref.sync import sync_to_async
from esi.exceptions import HTTPClientError
from esi.openapi_clients import ESIClientProvider

# Django
from django.db import IntegrityError
from django.db.transaction import TransactionManagementError

# Demolizzen
from demolizzen import (
    __esi_compatibility_date__,
    __github_url__,
    __package_name__,
    __version__,
    models,
)
from demolizzen.core.esi_context import UniverseName
from demolizzen.decorators import esi_request_handler

if TYPE_CHECKING:
    # Third Party
    from esi.stubs import (
        UniverseAsteroidBeltsAsteroidBeltIdGet,
        UniverseConstellationsConstellationIdGet,
        UniverseMoonsMoonIdGet,
        UniversePlanetsPlanetIdGet,
        UniverseStargatesStargateIdGet,
        UniverseStarsStarIdGet,
        UniverseStationsStationIdGet,
        UniverseTypesTypeIdGet,
    )

log = logging.getLogger("esi")

ESI_URL = "https://esi.evetech.net/latest"
FUZZ_URL = "https://www.fuzzwork.co.uk/api"
MARKET_URL = "https://market.fuzzwork.co.uk/aggregates"

esi = ESIClientProvider(
    compatibility_date=__esi_compatibility_date__,
    ua_appname=__package_name__,
    ua_version=__version__,
    ua_url=__github_url__,
    operations=[
        "PostUniverseNames",
        "GetUniverseSystemsSystemId",
        "GetUniverseConstellationsConstellationId",
        "GetUniversePlanetsPlanetId",
        "GetUniverseMoonsMoonId",
        "GetUniverseAsteroidBeltsAsteroidBeltId",
        "GetUniverseStargatesStargateId",
        "GetUniverseStarsStarId",
        "GetUniverseStationsStationId",
        "GetUniverseTypesTypeId",
        "GetKillmailsKillmailIdKillmailHash",
        "GetStatus",
    ],
)


# pylint: disable=too-many-public-methods, too-many-instance-attributes
class OpenAPI:
    """Data manager for requesting and returning ESI data."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
    ):
        self.session = session
        # Keep only waiting futures in memory; tasks/retries are persisted in DB.
        self._entity_futures = {
            "character": {},
            "corporation": {},
            "alliance": {},
            "station": {},
        }

    async def _queue_entity_task(self, entity_id: int, category: str):
        """Persist entity resolution task if it does not exist yet."""

        async def _create_task():
            """Try to create the task, handling transaction errors gracefully."""
            try:
                # First try with the default behavior
                await models.EveEntityTask.objects.aget_or_create(
                    entity_id=entity_id,
                    category=category,
                )
            except IntegrityError:
                # Task already exists, which is fine
                pass
            except TransactionManagementError:
                # Transaction is broken, try with a clean transaction using sync_to_async
                try:

                    @sync_to_async(thread_sensitive=False)
                    def _sync_create():
                        try:
                            models.EveEntityTask.objects.get_or_create(
                                entity_id=entity_id,
                                category=category,
                            )
                        except IntegrityError:
                            pass

                    await _sync_create()
                except Exception as sync_error:  # pylint: disable=broad-except
                    log.debug(
                        f"Failed to queue entity task for {entity_id} ({category}): {sync_error}"
                    )

        await _create_task()

    def _get_or_create_entity_future(
        self, category: str, entity_id: int
    ) -> asyncio.Future:
        """Return existing pending future or create a new one for the entity."""
        future = self._entity_futures[category].get(entity_id)
        if not future or future.done():
            future = asyncio.get_event_loop().create_future()
            self._entity_futures[category][entity_id] = future
        return future

    async def _entity_name_worker(self):
        """Worker to handle batch entity name resolution."""
        while True:
            await asyncio.sleep(30)
            categories = ["character", "corporation", "alliance", "station"]
            tasks = [
                task
                async for task in models.EveEntityTask.objects.filter(
                    category__in=categories
                )
            ]

            all_ids = {task.entity_id for task in tasks}

            if not all_ids:
                continue

            try:
                names = await self.get_universe_names(list(all_ids))
            except HTTPClientError as e:
                log.error(f"Batch universe_names HTTP error: {e.status_code}")
                if e.status_code == HTTPStatus.NOT_FOUND:
                    await self._handle_entity_error(tasks)
                    continue
                names = None

            # Wenn universe_names None oder leer, alle IDs erneut in die Warteschlange
            if not names:
                log.warning(
                    f"universe_names returned None or empty. Retrying all IDs in next batch: {list(all_ids)}"
                )
                continue

            # Verarbeite Ergebnisse
            for task in tasks:
                await self._resolve_id_name(task.entity_id, names, task.category)

    async def _handle_entity_error(self, tasks: list[models.EveEntityTask]):
        """Handle error when batch contains invalid IDs. Remove first ID and retry."""
        if not tasks:
            return

        first_task = min(tasks, key=lambda task: task.task_id)
        retry_count = first_task.retry_count + 1
        first_task.retry_count = retry_count

        if retry_count >= 3:
            log.warning(
                "ID %s in category %s failed 3 times. Marking as Unknown without saving.",
                first_task.entity_id,
                first_task.category,
            )
            future = self._entity_futures[first_task.category].get(first_task.entity_id)
            if future and not future.done():
                future.set_result("Unknown")

            self._entity_futures[first_task.category].pop(first_task.entity_id, None)
            await models.EveEntityTask.objects.filter(
                entity_id=first_task.entity_id,
                category=first_task.category,
            ).adelete()
        else:
            log.warning(
                "ID %s in category %s caused error. Retry %s/3 in next batch.",
                first_task.entity_id,
                first_task.category,
                retry_count,
            )
            await first_task.asave(update_fields=["retry_count", "last_attempt"])

    async def _resolve_id_name(
        self,
        eid: int,
        names: list[UniverseName],
        category: str,
    ):
        """Resolve name for a single ID with retry logic."""
        name = next(
            (n.name for n in names if n.id == eid and n.category == category), None
        )
        if name:
            # Erfolgreich aufgelöst: speichern
            future = self._entity_futures[category].get(eid)
            if future and not future.done():
                future.set_result(name)
            log.debug("Saving name for ID %s: %s", eid, name)
            self._entity_futures[category].pop(eid, None)
            await models.EveEntityTask.objects.filter(
                entity_id=eid,
                category=category,
            ).adelete()

    @esi_request_handler("system_id")
    async def get_or_create_solar_system(
        self, system_id
    ) -> models.MapSolarSystems | None:
        """Fetches or creates a solar system entry in the database."""
        try:
            query = await models.MapSolarSystems.objects.aget(solarSystemID=system_id)
            return query
        except models.MapSolarSystems.DoesNotExist:
            log.debug(f"Fetching solar system info for ID: {system_id}")
            data = esi.client.Universe.GetUniverseSystemsSystemId(
                system_id=system_id
            ).result(use_etag=False)
            if data:
                # Create a new MapSolarSystems instance
                new_system = await models.MapSolarSystems.objects.acreate(
                    solarSystemID=data.system_id,
                    solarSystemName=data.name,
                    constellationID=data.constellation_id,
                    security=data.security_status,
                    securityClass=data.security_class,
                    x=data.position.x,
                    y=data.position.y,
                    z=data.position.z,
                )
                log.debug(
                    f"Created new solar system entry for ID: {system_id} ({data.name})"
                )
                return new_system
            return None

    async def get_region_info(self, system_id) -> models.MapSolarSystems | None:
        """Fetches region info for a given solar system ID from the database."""
        if not system_id:
            return None

        try:
            query = await models.MapSolarSystems.objects.aget(solarSystemID=system_id)
            if query:
                return query
        except models.MapSolarSystems.DoesNotExist:
            pass
        return None

    async def get_or_create_character_name(self, character_id: int):
        """Get or create character name with batch resolution."""
        if not character_id:
            return None

        try:
            query = await models.EveEntityCache.objects.aget(entity_id=character_id)
            return query.entity_name
        except models.EveEntityCache.DoesNotExist:
            await self._queue_entity_task(character_id, "character")
            future = self._get_or_create_entity_future("character", character_id)
            name = await future

            # DB persist
            if not name == "Unknown":
                try:
                    await models.EveEntityCache.objects.acreate(
                        entity_id=character_id,
                        entity_name=name,
                        category="character",
                    )
                except IntegrityError:
                    pass
                except Exception as e:  # pylint: disable=broad-except
                    log.error(f"Error adding Character to Database: {e}")
        return name

    async def get_or_create_corporation_name(self, corporation_id: int):
        """Get corporation name by ID with batch resolution."""
        if not corporation_id:
            return None

        try:
            query = await models.EveEntityCache.objects.aget(entity_id=corporation_id)
            return query.entity_name
        except models.EveEntityCache.DoesNotExist:
            await self._queue_entity_task(corporation_id, "corporation")
            future = self._get_or_create_entity_future("corporation", corporation_id)
            name = await future
            if not name == "Unknown":
                try:
                    await models.EveEntityCache.objects.acreate(
                        entity_id=corporation_id,
                        entity_name=name,
                        category="corporation",
                    )
                except IntegrityError:
                    pass
                except Exception as e:  # pylint: disable=broad-except
                    log.error(f"Error adding Corporation to Database: {e}")
        return name

    async def get_or_create_alliance_name(self, alliance_id: int):
        """Get or create alliance name with batch resolution."""
        if not alliance_id:
            return None

        try:
            query = await models.EveEntityCache.objects.aget(entity_id=alliance_id)
            return query.entity_name
        except models.EveEntityCache.DoesNotExist:
            await self._queue_entity_task(alliance_id, "alliance")
            future = self._get_or_create_entity_future("alliance", alliance_id)
            name = await future

            if not name == "Unknown":
                try:
                    await models.EveEntityCache.objects.acreate(
                        entity_id=alliance_id,
                        entity_name=name,
                        category="alliance",
                    )
                    log.debug(f"Added Alliance to Database: {name}")
                except IntegrityError:
                    pass
                except Exception as e:  # pylint: disable=broad-except
                    log.error(f"Error adding Alliance to Database: {e}")
        return name

    # Catch all for unknown ID
    async def get_celestial_info(self, celestial_id):
        """Fetch celestial info by ID from OpenAPI with DB caching."""
        # DB-Cache prüfen
        try:
            query = await models.EveEntityCache.objects.aget(
                entity_id=celestial_id, category="celestial"
            )
            celestial = SimpleNamespace(
                name=query.entity_name,
                id=query.entity_id,
            )
            return celestial
        except models.EveEntityCache.DoesNotExist:
            log.debug(f"Fetching celestial info for ID: {celestial_id}")
            # Alle Quellen abfragen
            for info_func in [
                self.get_planet_info,
                self.get_stargate_info,
                self.get_star_info,
                self.get_station_info,
                self.get_moon_info,
                self.get_asteroid_info,
            ]:
                location_info = await info_func(celestial_id)
                if location_info and getattr(location_info, "name", None):
                    try:
                        await models.EveEntityCache.objects.acreate(
                            entity_id=celestial_id,
                            entity_name=location_info.name,
                            category="celestial",
                        )
                        log.debug(f"Added Celestial to Database: {location_info.name}")
                    except IntegrityError:
                        pass
                    except Exception as e:  # pylint: disable=broad-except
                        log.error(f"Error adding Celestial to Database: {e}")
                    return location_info
            log.debug(f"No celestial info found for ID: {celestial_id}")
            return None

    @esi_request_handler("ids")
    async def get_universe_names(self, ids):
        """Fetches names for a list of IDs from the ESI universe names endpoint."""
        if not ids:
            return None

        data = esi.client.Universe.PostUniverseNames(body=ids).result(use_etag=False)

        # Return list of UniverseName
        universe_names = [
            UniverseName(category=item.category, id=item.id, name=item.name)
            for item in data
        ]

        return universe_names

    @esi_request_handler("system_id")
    async def get_system_name(self, system_id):
        data = esi.client.Universe.GetUniverseSystemsSystemId(
            system_id=system_id
        ).result(use_etag=False)
        if data:
            return data.name
        return None

    @esi_request_handler("constellation_id")
    async def get_constellation_info(
        self, constellation_id
    ) -> Union["UniverseConstellationsConstellationIdGet", None]:
        """Fetch constellation info by ID from OpenAPI.

        Args:
            constellation_id (int): The ID of the constellation to fetch.
        Returns:
            constellation_id (int): The ID of the constellation.
            name (str): The name of the constellation.
            posisition: X, Y, Z coordinates of the constellation.
            region_id (int): The ID of the region the constellation is in.
            systems (list): A list of solar system IDs in the constellation.
        """
        return esi.client.Universe.GetUniverseConstellationsConstellationId(
            constellation_id=constellation_id
        ).result(use_etag=False)

    @esi_request_handler("planet_id")
    async def get_planet_info(
        self, planet_id
    ) -> Union["UniversePlanetsPlanetIdGet", None]:
        """Fetch planet info by ID from OpenAPI.

        Args:
            planet_id (int): The ID of the planet to fetch.
        Returns:
            planet_id (int): The ID of the planet.
            name (str): The name of the planet.
            position (Object): X, Y, Z coordinates of the planet.
            system_id (int): The ID of the solar system the planet is in.
            type_id (int): The ID of the planet type.
        """
        return esi.client.Universe.GetUniversePlanetsPlanetId(
            planet_id=planet_id
        ).result(use_etag=False)

    @esi_request_handler("moon_id")
    async def get_moon_info(self, moon_id) -> Union["UniverseMoonsMoonIdGet", None]:
        """Fetch moon info by ID from OpenAPI.

        Args:
            moon_id (int): The ID of the moon to fetch.
        Returns:
            moon_id (int): The ID of the moon.
            name (str): The name of the moon.
            position (Object): X, Y, Z coordinates of the moon.
            system_id (int): The ID of the solar system the moon is in.
        """
        return esi.client.Universe.GetUniverseMoonsMoonId(moon_id=moon_id).result(
            use_etag=False
        )

    @esi_request_handler("asteroid_id")
    async def get_asteroid_info(
        self, asteroid_id
    ) -> Union["UniverseAsteroidBeltsAsteroidBeltIdGet", None]:
        """Fetch asteroid belt info by ID from OpenAPI.

        Args:
            asteroid_id (int): The ID of the asteroid belt to fetch.
        Returns:
            name (str): The name of the asteroid belt.
            position (Object): X, Y, Z coordinates of the asteroid belt.
            system_id (int): The ID of the solar system the asteroid belt is in.
        """
        return esi.client.Universe.GetUniverseAsteroidBeltsAsteroidBeltId(
            asteroid_id=asteroid_id
        ).result(use_etag=False)

    @esi_request_handler("stargate_id")
    async def get_stargate_info(
        self, stargate_id
    ) -> Union["UniverseStargatesStargateIdGet", None]:
        """Fetch stargate info by ID from OpenAPI.

        Args:
            stargate_id (int): The ID of the stargate to fetch.
        Returns:
            destination (Object): The destination stargate.
            name (str): The name of the stargate.
            position (Object): X, Y, Z coordinates of the stargate.
            stargate_id (int): The ID of the destination stargate.
            system_id (int): The ID of the solar system the stargate is in.
            type_id (int): The ID of the stargate type.
        """
        return esi.client.Universe.GetUniverseStargatesStargateId(
            stargate_id=stargate_id
        ).result(use_etag=False)

    @esi_request_handler("star_id")
    async def get_star_info(self, star_id) -> Union["UniverseStarsStarIdGet", None]:
        """Fetch star info by ID from OpenAPI.

        Args:
            star_id (int): The ID of the star to fetch.
        Returns:
            age (int): The age of the star in years.
            luminosity (float): The luminosity of the star in solar units.
            name (str): The name of the star.
            radius (int): The radius of the star in solar units.
            solar_system_id (int): The ID of the solar system the star is in.
            spectral_class (Literal): The spectral class of the star.
            temperature (int): The surface temperature of the star in Kelvin.
            type_id (int): The ID of the star type.
        """
        return esi.client.Universe.GetUniverseStarsStarId(star_id=star_id).result(
            use_etag=False
        )

    @esi_request_handler("station_id")
    async def get_station_info(
        self, station_id
    ) -> Union["UniverseStationsStationIdGet", None]:
        """Fetch station info by ID from OpenAPI.

        Args:
            station_id (int): The ID of the station to fetch.
        Returns:
            max_dockable_ship_volume (float): The maximum dockable ship volume in cubic meters.
            name (str): The name of the station.
            office_rental_cost (float): The cost to rent an office in ISK.
            owner (int): The ID of the station owner.
            position (Object): X, Y, Z coordinates of the station.
            race_id (int): The ID of the station's race.
            reprocessing_efficiency (float): The reprocessing efficiency of the station in percent.
            reprocessing_stations_take (float): The percentage of reprocessed materials the station takes.
            services (list): A list of services offered by the station.
            station_id (int): The ID of the station.
            system_id (int): The ID of the solar system the station is in.
            type_id (int): The ID of the station type.
        """
        return esi.client.Universe.GetUniverseStationsStationId(
            station_id=station_id
        ).result(use_etag=False)

    # Item Stuff
    @esi_request_handler("item_id")
    async def get_item_info(self, item_id) -> Union["UniverseTypesTypeIdGet", None]:
        """Fetch item info by ID from OpenAPI.

        Args:
            item_id (int): The ID of the item to fetch.
        Returns:
            type_id (int): The ID of the item type.
            group_id (int): The ID of the group the item belongs to.
            name (str): The name of the item.
            description (str): The description of the item.
            mass (float): The mass of the item in kg.
            radius (float): The radius of the item in meters.
            volume (float): The volume of the item in cubic meters.
            published (bool): Whether the item is published in the market.
            market_group_id (int): The ID of the market group the item belongs to.
        """
        data = esi.client.Universe.GetUniverseTypesTypeId(type_id=item_id).result(
            use_etag=False
        )
        if data:
            return data
        return None

    # Fetch Item Info from Database
    async def item_info_db(self, item_id) -> Union["UniverseTypesTypeIdGet", None]:
        if not item_id:
            return None

        try:
            query = await models.InvTypes.objects.aget(typeID=item_id)

            result_dict = {
                field.name: getattr(query, field.name) for field in query._meta.fields
            }
            data = SimpleNamespace(
                name=result_dict.get("typeName"),
                description=result_dict.get("description"),
                type_id=result_dict.get("typeID"),
                group_id=result_dict.get("groupID"),
                mass=result_dict.get("mass"),
                radius=result_dict.get("radius"),
                volume=result_dict.get("volume"),
                published=result_dict.get("published"),
                market_group_id=result_dict.get("marketGroupID"),
            )
            return data
        except models.InvTypes.DoesNotExist:
            try:
                data = await self.get_item_info(item_id)
                if data:
                    await models.InvTypes.objects.acreate(
                        typeID=data.type_id,
                        groupID=data.group_id,
                        typeName=data.name,
                        description=data.description,
                        mass=data.mass,
                        radius=data.radius,
                        volume=data.volume,
                        published=1,
                        marketGroupID=data.market_group_id,
                    )
                    return data
            # pylint: disable=broad-except
            except Exception:
                return None
        return None

    @esi_request_handler("killmail_id")
    async def killmail(self, killmail_id, killmail_hash):
        if not killmail_id:
            return None

        data = esi.client.Killmails.GetKillmailsKillmailIdKillmailHash(
            killmail_id=killmail_id, killmail_hash=killmail_hash
        ).result(use_etag=False)
        if data:
            return data
        return None

    @esi_request_handler()
    async def server_info(self):
        """Fetch ESI server status info."""

        data = esi.client.Status.GetStatus().result(use_etag=False)
        if data:
            return data
        return None
