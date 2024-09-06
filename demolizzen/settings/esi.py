import asyncio
import json
import logging

import aiohttp
from aiohttp import BasicAuth
from settings import db
from settings.cache import CacheManager

log = logging.getLogger("discord")
log_testing = logging.getLogger("testing")

ESI_URL = "https://esi.evetech.net/latest"
FUZZ_URL = "https://www.fuzzwork.co.uk/api"
MARKET_URL = "https://market.fuzzwork.co.uk/aggregates"
OAUTH_URL = "https://login.eveonline.com/oauth/verify"
OTOKEN_URL = "https://login.eveonline.com/oauth/token"

cache_manager = CacheManager()
cache = cache_manager.get_cache()


# pylint: disable=too-many-public-methods
class ESI:
    """Data manager for requesting and returning ESI data."""

    def __init__(self, session):
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
        self._char_name_cache = {}
        self._system_id_name_cache = {}
        self._region_id_cache = {}
        # Load DB Cache Files
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.fetch_char_name())

    async def fetch_char_name(self):
        sql = "SELECT character_id, char_name FROM eve_charname_cache"
        results = await db.select(sql)
        if results:
            self._char_name_cache = {result[0]: result[1] for result in results}

    async def get_data(self, url, token=None):
        """
        Base data retrieval method.
        """
        try:
            if token:
                header = {"Authorization": f"Bearer {token}"}
            else:
                header = {"Accepts": "application/json"}
            async with self.session.get(url, headers=header) as r:
                try:
                    data = await r.json(content_type=None)
                except json.JSONDecodeError:
                    return None
            return data
        except asyncio.TimeoutError:
            return None
        # pylint: disable=broad-except
        except Exception as e:
            # Handle the connection error here
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

        location_info = await self.planet_info(celestial_id)
        if location_info and "name" in location_info:
            self._celestial_cache[celestial_id] = location_info
            return location_info

        location_info = await self.stargate_info(celestial_id)
        if location_info and "name" in location_info:
            self._celestial_cache[celestial_id] = location_info
            return location_info

        location_info = await self.star_info(celestial_id)
        if location_info and "name" in location_info:
            self._celestial_cache[celestial_id] = location_info
            return location_info

        location_info = await self.station_info(celestial_id)
        if location_info and "name" in location_info:
            self._celestial_cache[celestial_id] = location_info
            return location_info

        location_info = await self.moon_info(celestial_id)
        if location_info and "name" in location_info:
            self._celestial_cache[celestial_id] = location_info
            return location_info

        location_info = await self.asteroid_info(celestial_id)
        if location_info and "name" in location_info:
            self._celestial_cache[celestial_id] = location_info
            return location_info

        self._celestial_cache[celestial_id] = {}
        return {}

    async def system_info(self, system_id):
        url = f"{ESI_URL}/universe/systems/{system_id}/"
        return await self.get_data(url)

    # Get System info from Database
    async def system_info_db(self, system_id, allow_cache=True):
        if allow_cache:
            if system_id in self._system_id_name_cache:
                cached_name = self._system_id_name_cache[system_id]
                # log_testing.error(f"{character_id}: {cached_name}")
                if cached_name is not None and cached_name != "None":
                    return cached_name
                # return self._system_id_name_cache[system_id]

        if not system_id:
            return None

        sql = f"SELECT * FROM mapSolarSystems where solarSystemID = {system_id}"
        result = await db.select(sql, dictlist=True)

        if result:
            for row in result:
                self._system_id_name_cache[system_id] = row
        else:
            return None

        return self._system_id_name_cache[system_id]

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

    async def region_info(self, region_id, allow_cache=True):
        if allow_cache:
            if region_id in self._region_cache:
                cached_name = self._region_cache[region_id]
                # log_testing.error(f"{character_id}: {cached_name}")
                if cached_name is not None and cached_name != "None":
                    return cached_name
                # return self._region_cache[region_id]

        url = f"{ESI_URL}/universe/regions/{region_id}/"
        data = await self.get_data(url)
        if data:
            self._region_cache[region_id] = data
        return data

    async def region_id_info(self, system_id, allow_cache=True):
        if allow_cache:
            if system_id in self._region_id_cache:
                return self._region_id_cache[system_id]

        if not system_id:
            return None

        sql = f"SELECT * FROM mapSolarSystems where solarSystemID = {system_id}"
        result = await db.select(sql, dictlist=True)

        if result:
            for row in result:
                self._region_id_cache[system_id] = row
        else:
            return None

        return self._region_id_cache[system_id]

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

    async def character_name(self, character_id, allow_cache=True):
        if allow_cache:
            if character_id in self._char_name_cache:
                cached_name = self._char_name_cache[character_id]
                # log_testing.error(f"{character_id}: {cached_name}")
                if cached_name is not None and cached_name != "None":
                    return cached_name
                # return self._char_name_cache[character_id]

        if not character_id:
            return None

        data = await self.character_info(character_id)

        if data:
            self._char_name_cache[character_id] = data.get("name")
            if (
                self._char_name_cache[character_id] != "None"
                and self._char_name_cache[character_id] is not None
            ):
                sql = "INSERT IGNORE INTO `eve_charname_cache` (`character_id`, `char_name`) VALUES (:character_id, :char_name)"
                var = {
                    "character_id": character_id,
                    "char_name": self._char_name_cache[character_id],
                }
                await db.execute_sql(sql, var)

        if not data:
            return None

        return data.get("name")

    # Item Stuff

    async def item_id(self, item_name):
        url = f"{FUZZ_URL}/typeid.php?typename={item_name}"

        data = await self.get_data(url)

        if not data:
            return None
        return data.get("typeID")

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

        sql = f"SELECT * FROM invTypes where typeID = {item_id}"
        result = await db.select(sql, dictlist=True)

        if result:
            for row in result:
                self._item_name_cache[item_id] = row
        else:
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

    # Token Handling

    async def refresh_access_token(self, refresh_token, client_id, client_secret):
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        params = {"grant_type": "refresh_token", "refresh_token": refresh_token}

        # Encode the CLIENT_ID and CLIENT_SECRET in Base64
        auth = BasicAuth(login=client_id, password=client_secret)

        async with self.session.post(
            OTOKEN_URL, headers=headers, auth=auth, params=params
        ) as r:
            try:
                data = await r.json()
            except aiohttp.ContentTypeError:
                return None
            return data

    async def verify_token(self, access_token):
        header = {"Authorization": f"Bearer {access_token}"}
        async with self.session.get(OAUTH_URL, headers=header) as r:
            try:
                data = await r.json()
            except aiohttp.ContentTypeError:
                return None
            return data

    # Token Restricted

    async def esi_search(self, item, character_id, category, force_strict=False):
        strict = "true" if force_strict else "false"

        # ESI Search now needs a Token
        sql = f"SELECT * FROM access_tokens WHERE character_id = {character_id}"
        token = await db.select(sql, single=True, dictlist=True)

        if not token:
            return None

        url = (
            "{0}/characters/"
            f"{character_id}"
            "/search/?categories={1}&datasource=tranquility"
            "&language=en-us&search={2}&strict={3}"
        )

        data = await self.get_data(
            url.format(ESI_URL, category, item, strict), token["access_token"]
        )

        if category not in data:
            return None

        # if multiple, try stricter search
        if len(data[category]) > 1 and not force_strict:
            strict_data = await self.get_data(
                url.format(ESI_URL, category, item, "true")
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
