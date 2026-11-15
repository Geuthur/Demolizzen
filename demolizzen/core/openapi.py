# Standard Library
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from types import SimpleNamespace
from typing import TYPE_CHECKING, Union

# Third Party
import aiohttp
from esi.exceptions import HTTPClientError
from esi.openapi_clients import ESIClientProvider

# Django
from django.db import IntegrityError

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

    # Seconds to wait for ESI to answer a name lookup, and ids per request.
    NAME_TIMEOUT = 15
    NAME_BATCH = 1000

    def __init__(
        self,
        session: aiohttp.ClientSession,
    ):
        self.session = session
        # django-esi's client is synchronous; its calls run in these threads so
        # they never block the event loop.
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="esi")
        self._regions: dict[int, int] = {}

    def close(self) -> None:
        """Stop the worker threads. Calls that are still running are not waited for."""
        self._executor.shutdown(wait=False, cancel_futures=True)

    async def _call(self, operation):
        """Run an ESI operation without blocking the event loop.

        ``operation`` is a function without arguments that builds the ESI
        operation. django-esi's client is synchronous, so building and
        executing both happen in a worker thread.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor, lambda: operation().result(use_etag=False)
        )

    # ------------------------------------------------------------------ names

    async def _fetch_names(self, ids: list[int]) -> list[UniverseName]:
        data = await self._call(lambda: esi.client.Universe.PostUniverseNames(body=ids))
        return [
            UniverseName(category=item.category, id=item.id, name=item.name)
            for item in data or []
        ]

    async def _fetch_names_safely(self, ids: list[int]) -> list[UniverseName]:
        """Ask ESI for names. Never raises and never waits longer than the limit."""
        try:
            return await asyncio.wait_for(self._fetch_names(ids), self.NAME_TIMEOUT)
        except HTTPClientError as error:
            if error.status_code != HTTPStatus.NOT_FOUND or len(ids) == 1:
                if error.status_code != HTTPStatus.NOT_FOUND:
                    log.warning("ESI refused the name lookup for %s: %s", ids, error)
                return []
            # ESI rejects the whole request when one id is invalid; ask one by
            # one so the valid ids still get their names.
            results = await asyncio.gather(
                *[self._fetch_names_safely([entity_id]) for entity_id in ids]
            )
            return [name for result in results for name in result]
        except TimeoutError:
            log.warning("ESI name lookup timed out for %s id(s).", len(ids))
        except Exception as error:  # pylint: disable=broad-except
            log.warning("ESI name lookup failed for %s id(s): %r", len(ids), error)
        return []

    async def resolve_names(self, ids) -> dict[int, str]:
        """Return the names of characters, corporations, alliances and stations.

        Names come from the database cache; everything missing is asked from ESI
        in one request and stored. Ids that cannot be resolved are returned as
        ``"Unknown"`` and are not stored, so they are tried again next time.
        """
        wanted = list(dict.fromkeys(entity_id for entity_id in ids if entity_id))
        if not wanted:
            return {}

        names = {
            entry.entity_id: entry.entity_name
            async for entry in models.EveEntityCache.objects.filter(
                entity_id__in=wanted
            )
        }
        missing = [entity_id for entity_id in wanted if entity_id not in names]
        if missing:
            batches = [
                missing[start : start + self.NAME_BATCH]
                for start in range(0, len(missing), self.NAME_BATCH)
            ]
            fetched = [
                name
                for batch in await asyncio.gather(
                    *[self._fetch_names_safely(batch) for batch in batches]
                )
                for name in batch
            ]
            new = {name.id: name for name in fetched if name.id in missing}
            if new:
                await models.EveEntityCache.objects.abulk_create(
                    [
                        models.EveEntityCache(
                            entity_id=name.id,
                            entity_name=name.name[:64],
                            category=name.category,
                        )
                        for name in new.values()
                    ],
                    ignore_conflicts=True,
                )
            for entity_id in missing:
                names[entity_id] = (
                    new[entity_id].name if entity_id in new else "Unknown"
                )
        return {entity_id: names[entity_id] for entity_id in wanted}

    async def get_region_id(self, system_id: int | None) -> int | None:
        """Return the region of a solar system. Regions never change, so each
        system is read from the database once."""
        if not system_id:
            return None
        if system_id not in self._regions:
            system = await models.MapSolarSystems.objects.filter(
                solarSystemID=system_id
            ).afirst()
            if system is None or system.regionID is None:
                return None
            self._regions[system_id] = system.regionID
        return self._regions[system_id]

    # ------------------------------------------------------------------ universe

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
            data = await self._call(
                lambda: esi.client.Universe.GetUniverseSystemsSystemId(
                    system_id=system_id
                )
            )
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

    async def get_celestial_info(self, celestial_id):
        """Fetch celestial info by ID from OpenAPI with DB caching."""
        # Look in the database cache first
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

    @esi_request_handler("system_id")
    async def get_system_name(self, system_id):
        data = await self._call(
            lambda: esi.client.Universe.GetUniverseSystemsSystemId(system_id=system_id)
        )
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
        return await self._call(
            lambda: esi.client.Universe.GetUniverseConstellationsConstellationId(
                constellation_id=constellation_id
            )
        )

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
        return await self._call(
            lambda: esi.client.Universe.GetUniversePlanetsPlanetId(planet_id=planet_id)
        )

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
        return await self._call(
            lambda: esi.client.Universe.GetUniverseMoonsMoonId(moon_id=moon_id)
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
        return await self._call(
            lambda: esi.client.Universe.GetUniverseAsteroidBeltsAsteroidBeltId(
                asteroid_id=asteroid_id
            )
        )

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
        return await self._call(
            lambda: esi.client.Universe.GetUniverseStargatesStargateId(
                stargate_id=stargate_id
            )
        )

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
        return await self._call(
            lambda: esi.client.Universe.GetUniverseStarsStarId(star_id=star_id)
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
        return await self._call(
            lambda: esi.client.Universe.GetUniverseStationsStationId(
                station_id=station_id
            )
        )

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
        data = await self._call(
            lambda: esi.client.Universe.GetUniverseTypesTypeId(type_id=item_id)
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

        data = await self._call(
            lambda: esi.client.Killmails.GetKillmailsKillmailIdKillmailHash(
                killmail_id=killmail_id, killmail_hash=killmail_hash
            )
        )
        if data:
            return data
        return None

    @esi_request_handler()
    async def server_info(self):
        """Fetch ESI server status info."""

        data = await self._call(esi.client.Status.GetStatus)
        if data:
            return data
        return None
