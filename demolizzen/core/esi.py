# Standard Library
import asyncio
import json
import logging

# Third Party
import aiohttp
from aiohttp.client_exceptions import (
    ClientConnectionError,
    ClientConnectorDNSError,
    ClientConnectorError,
)

# Django
from django.db import IntegrityError

# Demolizzen
from demolizzen import __user_agent__, models

log = logging.getLogger(__name__)

ESI_URL = "https://esi.evetech.net/latest"
FUZZ_URL = "https://www.fuzzwork.co.uk/api"
MARKET_URL = "https://market.fuzzwork.co.uk/aggregates"


# pylint: disable=too-many-public-methods, too-many-instance-attributes
class ESI:
    """Data manager for requesting and returning ESI data."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
    ):
        self.session = session
        self._types_cache = {}
        self._celestial_cache = {}
        self._system_cache = {}
        self._constellation_cache = {}
        self._region_cache = {}
        self._planet_cache = {}
        self._station_cache = {}
        self._stargate_cache = {}
        self._star_cache = {}
        self._moon_cache = {}
        self._asteroid_cache = {}
        self._eve_item_db = {}
        self._killmail_cache = {}
        # Killmail Cache
        self._item_name_cache = {}
        self._entity_name_cache = {}
        self._system_id_name_cache = {}
        self._region_id_cache = {}
        # Load DB Cache Files
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.fetch_char_name())
        # Locks for concurrent access
        self._character_lock = asyncio.Lock()
        self._corporation_lock = asyncio.Lock()
        self._alliance_lock = asyncio.Lock()
        # Batch Name Resolver
        self._batch_queues = {"character": {}, "corporation": {}, "alliance": {}}
        self._batch_task = self.loop.create_task(self._batch_name_worker())

    async def close_batch_task(self):
        """Close the batch task."""
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass
            self._batch_task = None

    async def start_batch_task(self):
        """Start the batch task if not already running."""
        if self._batch_task is None or self._batch_task.done():
            self._batch_task = self.loop.create_task(self._batch_name_worker())

    async def _batch_name_worker(self):
        """Worker to handle batch name resolution."""
        while True:
            await asyncio.sleep(30)
            # Alle IDs aus allen Kategorien sammeln
            all_ids = set()
            for category in ["character", "corporation", "alliance"]:
                all_ids.update(self._batch_queues[category].keys())
            if not all_ids:
                continue
            try:
                names = await self.universe_names(list(all_ids))
            except Exception as e:  # pylint: disable=broad-except
                log.error(f"Batch universe_names error: {e}")
                names = None

            # Wenn universe_names None oder leer, alle IDs erneut in die Warteschlange
            if not names:
                log.warning(
                    f"universe_names returned None or empty. Retrying all IDs in next batch: {list(all_ids)}"
                )
                # Die Warteschlangen werden nicht geleert, damit die Futures offen bleiben
                continue

            # Ergebnisse den jeweiligen Futures zuordnen
            for category in ["character", "corporation", "alliance"]:
                queue = self._batch_queues[category]
                remove_ids = []
                for eid, fut in queue.items():
                    name = names.get(eid, "Unknown")
                    if name == "Unknown":
                        log.warning(
                            f"Unknown name for ID {eid} in category {category}. universe_names result: {names}"
                        )
                        # ID bleibt in der Warteschlange, Future bleibt offen
                        continue
                    if not fut.done():
                        fut.set_result(name)
                    self._entity_name_cache[eid] = name
                    log.debug("Saving name for ID %s: %s", eid, name)
                    remove_ids.append(eid)
                # Nur erfolgreich aufgelöste IDs entfernen
                for eid in remove_ids:
                    queue.pop(eid, None)

    async def fetch_char_name(self):
        results = [r async for r in models.EveEntityCache.objects.all()]
        if results:
            self._entity_name_cache = {
                result.entity_id: result.entity_name for result in results
            }

    async def get_data(self, url, token=None):
        """
        Base data retrieval method.
        """
        try:
            if token:
                header = {"Authorization": f"Bearer {token}"}
            else:
                header = {"Accepts": "application/json"}
            header["User-Agent"] = __user_agent__
            async with self.session.get(url, headers=header) as r:
                try:
                    data = await r.json(content_type=None)
                except json.JSONDecodeError:
                    return None
            return data
        except asyncio.TimeoutError:
            log.debug("Timeout when requesting URL: %s", url)
            return None
        # Handle aiohttp connection errors (incl. DNS resolution problems)
        except (
            ClientConnectorError,
            ClientConnectorDNSError,
            ClientConnectionError,
        ) as e:
            log.debug("Connection error on Get Data (%s): %s", url, e)
            return None
        # Network-level socket errors (e.g., getaddrinfo failures)
        except OSError as e:
            log.debug("OS error on Get Data (%s): %s", url, e)
            return None
        except Exception as e:
            # Fallback logging for unexpected errors
            log.exception("Error on Get Data: %s", e)
            return None

    async def post_data(self, url, data=None, token=None):
        """
        Base data posting method.
        """
        try:
            if token:
                header = {"Authorization": f"Bearer {token}"}
            else:
                header = {"Accepts": "application/json"}
            header["User-Agent"] = __user_agent__
            async with self.session.post(url, headers=header, json=data) as r:
                try:
                    response = await r.json(content_type=None)
                except json.JSONDecodeError:
                    return None
            return response
        except asyncio.TimeoutError:
            log.debug("Timeout when requesting URL: %s", url)
            return None
        # Handle aiohttp connection errors (incl. DNS resolution problems)
        except (
            ClientConnectorError,
            ClientConnectorDNSError,
            ClientConnectionError,
        ) as e:
            log.debug("Connection error on Get Data (%s): %s", url, e)
            return None
        # Network-level socket errors (e.g., getaddrinfo failures)
        except OSError as e:
            log.debug("OS error on Get Data (%s): %s", url, e)
            return None
        except Exception as e:
            # Fallback logging for unexpected errors
            log.exception("Error on Get Data: %s", e)
            return None

    async def server_info(self):
        url = f"{ESI_URL}/status/"
        return await self.get_data(url)

    # Location Stuff

    # Catch all for unknown ID
    async def celestial_info(self, celestial_id, allow_cache=True):
        if allow_cache and celestial_id in self._celestial_cache:
            return self._celestial_cache[celestial_id]

        # DB-Cache prüfen
        try:
            query = await models.EveEntityCache.objects.aget(
                entity_id=celestial_id, category="celestial"
            )
            self._celestial_cache[celestial_id] = {
                "name": query.entity_name,
                "id": query.entity_id,
            }
            return self._celestial_cache[celestial_id]
        except models.EveEntityCache.DoesNotExist:
            log.debug(f"Fetching celestial info for ID: {celestial_id}")
            # Alle Quellen abfragen
            for info_func in [
                self.planet_info,
                self.stargate_info,
                self.star_info,
                self.station_info,
                self.moon_info,
                self.asteroid_info,
            ]:
                location_info = await info_func(celestial_id)
                if location_info and "name" in location_info:
                    self._celestial_cache[celestial_id] = location_info
                    try:
                        await models.EveEntityCache.objects.acreate(
                            entity_id=celestial_id,
                            entity_name=location_info["name"],
                            category="celestial",
                        )
                        log.debug(
                            f"Added Celestial to Database: {location_info['name']}"
                        )
                    except IntegrityError:
                        pass
                    except Exception as e:  # pylint: disable=broad-except
                        log.error(f"Error adding Celestial to Database: {e}")
                    return location_info
            log.debug(f"No celestial info found for ID: {celestial_id}")
            self._celestial_cache[celestial_id] = {}
            return {}

    async def system_info(self, system_id):
        url = f"{ESI_URL}/universe/systems/{system_id}/"
        return await self.get_data(url)

    async def get_or_create_solar_system(
        self, system_id
    ) -> models.MapSolarSystems | None:
        """
        Fetches or creates a solar system entry in the database.
        """
        try:
            query = await models.MapSolarSystems.objects.aget(solarSystemID=system_id)
            return query
        except models.MapSolarSystems.DoesNotExist:
            url = f"{ESI_URL}/universe/systems/{system_id}/"
            log.debug(f"Fetching solar system info for ID: {system_id}")
            data = await self.get_data(url)
            if data:
                # Create a new MapSolarSystems instance
                new_system = await models.MapSolarSystems.objects.acreate(
                    solarSystemID=data.get("system_id"),
                    solarSystemName=data.get("name"),
                    constellationID=data.get("constellation_id"),
                    security=data.get("security_status"),
                    securityClass=data.get("security_class"),
                    x=data.get("position", {}).get("x"),
                    y=data.get("position", {}).get("y"),
                    z=data.get("position", {}).get("z"),
                )
                log.debug(
                    f"Created new solar system entry for ID: {system_id} ({data.get('name')})"
                )
                return new_system
            return None

    async def system_name(self, system_id):
        url = f"{ESI_URL}/universe/systems/{system_id}/"
        data = await self.get_data(url)
        if not data:
            return None
        return data.get("name")

    async def constellation_info(self, constellation_id, allow_cache=True):
        if allow_cache:
            if constellation_id in self._constellation_cache:
                return self._constellation_cache[constellation_id]

        url = f"{ESI_URL}/universe/constellations/{constellation_id}/"
        data = await self.get_data(url)
        if data:
            self._constellation_cache[constellation_id] = data
        return data

    async def get_region_info(
        self, system_id, allow_cache=True
    ) -> models.MapSolarSystems | None:
        """
        Fetches the region information based on the solar system ID.
        """
        if allow_cache:
            if system_id in self._region_id_cache:
                return self._region_id_cache[system_id]

        if not system_id:
            return None

        try:
            query = await models.MapSolarSystems.objects.aget(solarSystemID=system_id)
            if query:
                self._region_id_cache[system_id] = query
                return query
        except models.MapSolarSystems.DoesNotExist:
            pass
        return None

    async def planet_info(self, planet_id, allow_cache=True):
        if allow_cache:
            if planet_id in self._planet_cache:
                return self._planet_cache[planet_id]

        url = f"{ESI_URL}/universe/planets/{planet_id}/"
        data = await self.get_data(url)
        if data:
            self._planet_cache[planet_id] = data
        return data

    async def moon_info(self, moon_id, allow_cache=True):
        if allow_cache:
            if moon_id in self._moon_cache:
                return self._moon_cache[moon_id]

        url = f"{ESI_URL}/universe/moons/{moon_id}/"
        data = await self.get_data(url)
        if data:
            self._moon_cache[moon_id] = data
        return data

    async def asteroid_info(self, asteroid_id, allow_cache=True):
        if allow_cache:
            if asteroid_id in self._asteroid_cache:
                return self._asteroid_cache[asteroid_id]

        url = f"{ESI_URL}/universe/asteroid_belts/{asteroid_id}/"
        data = await self.get_data(url)
        if data:
            self._asteroid_cache[asteroid_id] = data
        return data

    async def stargate_info(self, stargate_id, allow_cache=True):
        if allow_cache:
            if stargate_id in self._stargate_cache:
                return self._stargate_cache[stargate_id]

        url = f"{ESI_URL}/universe/stargates/{stargate_id}/"
        data = await self.get_data(url)
        if data:
            self._stargate_cache[stargate_id] = data
        return data

    async def star_info(self, star_id, allow_cache=True):
        if allow_cache:
            if star_id in self._star_cache:
                return self._star_cache[star_id]

        url = f"{ESI_URL}/universe/stars/{star_id}/"
        data = await self.get_data(url)
        if data:
            self._star_cache[star_id] = data
        return data

    async def station_info(self, station_id, allow_cache=True):
        if allow_cache:
            if station_id in self._station_cache:
                return self._station_cache[station_id]

        url = f"{ESI_URL}/universe/stations/{station_id}/"
        data = await self.get_data(url)
        if data:
            self._station_cache[station_id] = data
        return data

    async def get_jump_info(self, system_id=None):
        url = f"{ESI_URL}/universe/system_jumps/"
        data = await self.get_data(url)
        if not data:
            return None

        if system_id:
            for system in data:
                if system["system_id"] == system_id:
                    return system["ship_jumps"]
            return 0
        return data

    async def get_incursion_info(self):
        url = f"{ESI_URL}/incursions/"
        return await self.get_data(url)

    async def get_active_sov_battles(self):
        url = f"{ESI_URL}/sovereignty/campaigns/?datasource=tranquility"
        return await self.get_data(url)

    # Character Stuff

    async def character_info(self, character_id):
        url = f"{ESI_URL}/characters/{character_id}/"
        return await self.get_data(url)

    async def character_corp_id(self, character_id):
        data = await self.character_info(character_id)
        if not data:
            return None
        return data.get("corporation_id")

    async def corporation_info(self, corporation_id):
        url = f"{ESI_URL}/corporations/{corporation_id}/"
        return await self.get_data(url)

    async def character_alliance_id(self, character_id):
        data = await self.character_info(character_id)
        if not data:
            return None
        return data.get("alliance_id")

    async def alliance_info(self, alliance_id):
        url = f"{ESI_URL}/alliances/{alliance_id}/"
        return await self.get_data(url)

    async def get_or_create_character_name(self, character_id: int, allow_cache=True):
        """Batch-resolved character name."""
        if allow_cache and character_id in self._entity_name_cache:
            return self._entity_name_cache[character_id]
        if not character_id:
            return None

        try:
            query = await models.EveEntityCache.objects.aget(entity_id=character_id)
            self._entity_name_cache[character_id] = query.entity_name
            return query.entity_name
        except models.EveEntityCache.DoesNotExist:
            # Batch-Queue
            future = self._batch_queues["character"].get(character_id)
            if not future:
                future = asyncio.get_event_loop().create_future()
                self._batch_queues["character"][character_id] = future
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

    async def get_or_create_corporation_name(
        self, corporation_id: int, allow_cache=True
    ):
        """Batch-resolved corporation name."""
        if allow_cache and corporation_id in self._entity_name_cache:
            return self._entity_name_cache[corporation_id]
        if not corporation_id:
            return None

        try:
            query = await models.EveEntityCache.objects.aget(entity_id=corporation_id)
            self._entity_name_cache[corporation_id] = query.entity_name
            return query.entity_name
        except models.EveEntityCache.DoesNotExist:
            future = self._batch_queues["corporation"].get(corporation_id)
            if not future:
                future = asyncio.get_event_loop().create_future()
                self._batch_queues["corporation"][corporation_id] = future
            name = await future
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

    async def get_or_create_alliance_name(self, alliance_id: int, allow_cache=True):
        """Batch-resolved alliance name."""
        if allow_cache and alliance_id in self._entity_name_cache:
            return self._entity_name_cache[alliance_id]
        if not alliance_id:
            return None

        try:
            query = await models.EveEntityCache.objects.aget(entity_id=alliance_id)
            self._entity_name_cache[alliance_id] = query.entity_name
            return query.entity_name
        except models.EveEntityCache.DoesNotExist:
            future = self._batch_queues["alliance"].get(alliance_id)
            if not future:
                future = asyncio.get_event_loop().create_future()
                self._batch_queues["alliance"][alliance_id] = future
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

    # Item Stuff

    async def item_id(self, item_name):
        url = f"{FUZZ_URL}/typeid.php?typename={item_name}"

        data = await self.get_data(url)

        if not data:
            return None
        return data.get("typeID")

    async def universe_names(self, ids):
        """Fetches names for a list of IDs from the ESI universe names endpoint."""
        if not ids:
            return {}

        url = f"{ESI_URL}/universe/names/"
        # ESI expects a JSON array of IDs, not a dict
        data = await self.post_data(url, data=ids)

        if not data or isinstance(data, dict) and data.get("error"):
            log.warning(f"universe_names returned None or error. Data: {data}")
            return {}

        return {
            item["id"]: item["name"] for item in data if "id" in item and "name" in item
        }

    async def item_info(self, item_id, allow_cache=True):
        if allow_cache:
            if item_id in self._types_cache:
                return self._types_cache[item_id]
        url = f"{ESI_URL}/universe/types/{item_id}/"
        data = await self.get_data(url)
        if data:
            self._types_cache[item_id] = data
        return data

    # Fetch Item Info from Database
    async def item_info_db(self, item_id, allow_cache=True):
        if allow_cache:
            if item_id in self._item_name_cache:
                return self._item_name_cache[item_id]

        if not item_id:
            return None

        try:
            query = await models.InvTypes.objects.aget(typeID=item_id)

            result_dict = {
                field.name: getattr(query, field.name) for field in query._meta.fields
            }
            self._item_name_cache[item_id] = result_dict
            return result_dict
        except models.InvTypes.DoesNotExist:
            try:
                url = f"{ESI_URL}/universe/types/{item_id}/"
                data = await self.get_data(url)
                if data:
                    self._item_name_cache[item_id] = data
                    return data
            # pylint: disable=broad-except
            except Exception:
                return None
        return self._item_name_cache[item_id]

    async def market_data_fuzz(self, item_name, station):
        item_id = await self.item_id(item_name)
        if not item_id:
            return None

        url = f"{MARKET_URL}/?station={station}&types={item_id}"
        data = await self.get_data(url)
        if not data:
            return None

        return data[str(item_id)]

    async def killmail(self, killmail_id, killmail_hash, allow_cache=True):
        if allow_cache:
            if killmail_id in self._killmail_cache:
                return self._region_cache[killmail_id]

        url = f"{ESI_URL}/killmails/{killmail_id}/{killmail_hash}"
        data = await self.get_data(url)
        if data:
            self._killmail_cache[killmail_id] = data
        return data

    # Token Restricted

    async def esi_search(self, item, character_id, category, force_strict=False):
        strict = "true" if force_strict else "false"

        # ESI Search now needs a Token
        try:
            query = await models.AccessToken.objects.aget(character_id=character_id)

        except models.AccessToken.DoesNotExist:
            return None

        url = f"{ESI_URL}/characters/{character_id}/search/?categories={category}&datasource=tranquility&language=en-us&search={item}&strict={strict}"
        data = await self.get_data(url, query.access_token)

        if category not in data:
            return None

        # if multiple, try stricter search
        if len(data[category]) > 1 and not force_strict:
            strict_data = await self.get_data(
                url.format(ESI_URL, category, item, "true"), query.access_token
            )

            # if no strict results, use non-strict results
            if category not in strict_data:
                return data
            data = strict_data

        # TODO: don't return category dict; return result list.
        # example: like `return data[category]`

        return data

    async def notifications(self, alliance_id):
        url = f"{ESI_URL}/alliances/{alliance_id}/"
        return await self.get_data(url)

    async def market_data(self, item_name, station, character_id):
        results = await self.esi_search(item_name, character_id, "inventory_type")
        if not results:
            return None

        item_id = results["inventory_type"][0]
        url = f"{MARKET_URL}/?station={station}&types={item_id}"
        data = await self.get_data(url)
        if not data:
            return None

        return data[str(item_id)]
