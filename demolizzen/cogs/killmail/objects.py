import asyncio
import logging
from collections import Counter
from typing import NamedTuple

import discord
from dateutil.parser import parse
from settings.functions import make_embed

log = logging.getLogger("testing")


class Position(NamedTuple):
    x: float
    y: float
    z: float


class Item:
    __slots__ = (
        "_data",
        "_esi",
        "flag",
        "item_type_id",
        "qty_dropped",
        "qty_destroyed",
        "singleton",
        "name",
    )

    def __init__(self, data, esi):
        self._data = data
        self._esi = esi
        self.flag = data.get("flag")
        self.item_type_id = data.get("item_type_id")
        self.qty_dropped = data.get("quantity_dropped", 0)
        self.qty_destroyed = data.get("quantity_destroyed", 0)
        self.singleton = data.get("singleton")
        self.name = None

    # Get Item Name from Database - Reduce ESI Fetch
    async def fetch_name(self):
        item = await self._esi.item_info_db(self.item_type_id)
        if item:
            self.name = item.get("typeName")


class Character:
    __slots__ = (
        "_data",
        "_esi",
        "id",
        "corp_id",
        "alliance_id",
        "ship_type_id",
        "name",
        "corp",
        "alliance",
        "ship",
    )

    def __init__(self, data, esi):
        self._data = data
        self._esi = esi
        self.id = data.get("character_id")
        self.corp_id = data.get("corporation_id")
        self.alliance_id = data.get("alliance_id", None)
        self.ship_type_id = data.get("ship_type_id", None)
        self.name = None
        self.corp = None
        self.alliance = None
        self.ship = None

    async def fetch_name(self):
        if not self.name:
            self.name = await self._esi.character_name(self.id)

    async def fetch_corp(self):
        if not self.corp:
            corp = await self._esi.corporation_info(self.corp_id)
            if corp:
                self.corp = corp.get("name")

    async def fetch_alliance(self):
        if not self.alliance and self.alliance_id:
            alliance = await self._esi.alliance_info(self.alliance_id)
            if alliance:
                self.alliance = alliance.get("name")

    # Fetch Ship name from Database
    async def fetch_ship(self):
        if not self.ship_type_id:
            return
        if not self.ship:
            ship = await self._esi.item_info_db(self.ship_type_id)
            if ship:
                self.ship = ship.get("typeName")

    def fetch_all(self):
        return asyncio.gather(
            self.fetch_name(),
            self.fetch_corp(),
            self.fetch_alliance(),
            self.fetch_ship(),
        )


class Attacker(Character):
    # pylint: disable=redefined-slots-in-subclass
    __slots__ = (
        "weapon_type_id",
        "damage",
        "final_blow",
        "security",
        *Character.__slots__,
    )

    def __init__(self, data, esi):
        super().__init__(data, esi)
        self.weapon_type_id = data.get("weapon_type_id")
        self.damage = data.get("damage_done")
        self.final_blow = data.get("final_blow")
        self.security = data.get("security_status")


class Victim(Character):
    # pylint: disable=redefined-slots-in-subclass
    __slots__ = ("damage_taken", "items", "position", *Character.__slots__)

    def __init__(self, data, esi):
        super().__init__(data, esi)
        self.damage_taken = data.get("damage_taken")
        self.items = [Item(i, esi) for i in data.get("items", [])]
        pos = data.get("position")
        if pos:
            self.position = Position(**pos)


# pylint: disable=too-many-instance-attributes
class Mail:
    __slots__ = (
        "_data",
        "_esi",
        "id",
        "time",
        "system_id",
        "final_attacker",
        "attackers",
        "victim",
        "corp_id",
        "alliance_id",
        "location_id",
        "hash",
        "fitted_value",
        "value",
        "points",
        "npc",
        "solo",
        "awox",
        "eve_url",
        "url",
        "system",
        "celestial",
        "constellation",
        "constellation_id",
        "region_id",
        "region",
    )

    def __init__(self, payload, esi):
        self._data = payload
        self._esi = esi
        self.id = payload.get("killmail_id")
        self.time = parse(payload.get("killmail_time"))
        self.system_id = payload.get("solar_system_id")

        self.final_attacker = None
        self.attackers = {}
        for attacker_data in payload.get("attackers", []):
            attacker = Attacker(attacker_data, esi)
            self.attackers[attacker.id] = attacker

            if attacker.final_blow:
                self.final_attacker = attacker

        self.victim = Victim(payload.get("victim"), esi)
        self.corp_id = self.victim.corp_id
        self.alliance_id = self.victim.alliance_id

        zkb = payload.get("zkb", {})
        self.location_id = zkb.get("locationID")
        self.hash = zkb.get("hash")
        self.fitted_value = zkb.get("fittedValue")
        self.value = zkb.get("totalValue")
        self.points = zkb.get("points")
        self.npc = zkb.get("npc")
        self.solo = zkb.get("solo")
        self.awox = zkb.get("awox")
        self.eve_url = zkb.get("esi")
        self.url = f"https://zkillboard.com/kill/{self.id}/"

        self.system = None
        self.celestial = None
        self.constellation = None
        self.constellation_id = None
        self.region_id = None
        self.region = None

    def __repr__(self):
        sys = self.system_id
        victim = self.victim.id
        ship = self.victim.ship
        value = self.value
        npc = " NPC" if self.npc else ""
        return f"<Mail {self.id}{npc} system={sys} victim={victim} ship={ship} value={value}>"

    async def fetch_region(self):
        if not self.region:
            if not self.region_id:
                region_id = await self._esi.region_id_info(self.system_id)
                if region_id:
                    self.region_id = region_id.get("regionID")
            region = await self._esi.region_info(self.region_id)
            if region:
                self.region = region.get("name")

    async def fetch_region_id(self):
        if not self.region_id:
            region = await self._esi.region_id_info(self.system_id)
            if region:
                self.region_id = region.get("regionID")
                return self.region_id
            return None

    # Not Active
    async def fetch_constellation(self):
        if not self.constellation:
            await self.fetch_system()
            constellation = await self._esi.constellation_info(self.constellation_id)
            self.constellation = constellation.get("name")
            self.region_id = constellation.get("region_id")

    # Fetch System name from Database
    async def fetch_system(self):
        if not self.system:
            if not self.system_id:
                return "Unknown"
            system = await self._esi.system_info_db(self.system_id)
            if not system:
                return "Unknown"
            self.constellation_id = system.get("constellationID")
            self.system = system.get("solarSystemName")

    async def fetch_celestial(self):
        if not self.celestial:
            if not self.location_id:
                return "Unknown"
            celestial = await self._esi.celestial_info(self.location_id)
            if celestial:
                self.celestial = celestial.get("name", "Unknown")
            else:
                self.celestial = "Unknown"

    def count_attackers(self):
        try:
            attacker_count = len(self.attackers)
            return attacker_count
        # pylint: disable=broad-except
        except Exception as e:
            log.error(f"Fehler beim Zählen der Angreifer: {e}")
            return 0

    async def most_involved(self):
        ship = None
        corp_or_alliance = None

        try:
            # Count attackers Ship ID, Corp ID, and Alliance ID in a single pass
            counters = {"ship": Counter(), "corp": Counter(), "alliance": Counter()}

            for attacker in self.attackers.values():
                counters["ship"][attacker.ship_type_id] += 1
                counters["corp"][attacker.corp_id] += 1
                counters["alliance"][attacker.alliance_id] += 1

            most_common_ship = counters["ship"].most_common(1)
            most_common_corp = counters["corp"].most_common(1)
            most_common_alliance = counters["alliance"].most_common(1)

            # Get Info from the Most Ship ID
            if most_common_ship[0][0] and most_common_ship[0][1] > 3:
                ship = await self._esi.item_info_db(most_common_ship[0][0])

            # Get Info from the Most Corp or Alliance
            if most_common_corp[0][0] and most_common_alliance[0][0]:
                # Compare the count of corp_id and alliance_id
                if most_common_corp[0][1] == most_common_alliance[0][1]:
                    if most_common_alliance[0][1] > 3:
                        corp_or_alliance = await self._esi.alliance_info(
                            most_common_alliance[0][0]
                        )
                elif most_common_corp[0][1] >= most_common_alliance[0][1]:
                    if most_common_corp[0][1] > 3:
                        corp_or_alliance = await self._esi.corporation_info(
                            most_common_corp[0][0]
                        )
                elif most_common_alliance[0][1] > 3:
                    corp_or_alliance = await self._esi.alliance_info(
                        most_common_alliance[0][0]
                    )
                else:
                    if most_common_corp[0][1] > 3:
                        corp_or_alliance = await self._esi.corporation_info(
                            most_common_corp[0][0]
                        )
            elif most_common_alliance[0][0] and most_common_alliance[0][1] > 3:
                # Get Info from the Most Alliance ID
                corp_or_alliance = await self._esi.alliance_info(
                    most_common_alliance[0][0]
                )
            elif most_common_corp[0][0] and most_common_corp[0][1] > 3:
                # Get Info from the Most Corp ID
                corp_or_alliance = await self._esi.corporation_info(
                    most_common_corp[0][0]
                )

            # Return Ship if more than 1
            if ship and corp_or_alliance:
                ship_name = ship.get("typeName")
                corp_or_alliance_name = corp_or_alliance.get("name")
                return ship_name, corp_or_alliance_name
            if corp_or_alliance:
                ship_name = None
                corp_or_alliance_name = corp_or_alliance.get("name")
                return ship_name, corp_or_alliance_name
            if ship:
                ship_name = ship.get("typeName")
                corp_or_alliance_name = None
                return ship_name, corp_or_alliance_name

            ship_name = None
            corp_or_alliance_name = None
            return ship_name, corp_or_alliance_name

        # pylint: disable=broad-except
        except Exception as e:
            ship_name = None
            corp_or_alliance_name = None
            log.error(f"Fehler beim Most Involved: {e}")
            return ship_name, corp_or_alliance_name

    def fetch_all(self):
        return asyncio.gather(
            self.victim.fetch_all(),
            self.fetch_celestial(),
            self.fetch_system(),
            self.fetch_region(),
        )

    # Main Information
    def info_output(self):
        info = [
            f"{self.system} • System: "
            f"[Map](http://evemaps.dotlan.net/search?q={self.system_id}) | "
            f"[Killboard](https://zkillboard.com/system/{self.system_id}/)",
        ]
        if self.celestial:
            info.append(f"Nearest Celestial: `{self.celestial}`")

        return "\n".join(info)

    # Collect additional information
    async def info_victim(self):
        ship, corp = await self.most_involved()
        count = self.count_attackers()
        info = [
            f"**[{self.victim.name}](https://zkillboard.com/character/{self.victim.id}/)** ([{self.victim.corp}](https://zkillboard.com/corporation/{self.victim.corp_id}/)) lost their **`{self.victim.ship}`** in **`{self.system}`** worth **`{self.value:,}`** ISK",
            f"Final Blow by **[{self.final_attacker.name}](https://zkillboard.com/character/{self.final_attacker.id}/)** ([{self.final_attacker.corp}](https://zkillboard.com/corporation/{self.final_attacker.corp_id}/)) in a `{self.final_attacker.ship}`",
        ]
        if self.solo:
            info.insert(0, "**SOLO KILL**")
        if count > 1:
            if ship is not None and corp is None:
                info.append(
                    f"Attackers: **`{self.count_attackers()}`** • Most Involved: `{ship}`"
                )
            elif ship is None and corp is not None:
                info.append(
                    f"Attackers: **`{self.count_attackers()}`** • Most Involved: `{corp}`"
                )
            elif ship is not None and corp is not None:
                info.append(
                    f"Attackers: **`{self.count_attackers()}`** • Most Involved: `{ship}` | `{corp}`"
                )
            else:
                info.append(f"Attackers: **`{self.count_attackers()}`**")
        return "\n".join(info)

    async def send_embed(self, channel, is_loss=False):
        try:
            await asyncio.gather(
                self.fetch_all(),
                self.victim.fetch_all(),
                self.final_attacker.fetch_all(),
            )
            color = "red" if is_loss else "green"
            if self.alliance_id:
                title = self.victim.alliance
                title_icon = f"https://images.evetech.net/alliances/{self.victim.alliance_id}/logo?size=64"
                url = f"https://zkillboard.com/alliance/{self.victim.alliance_id}/"
            else:
                title = self.victim.corp
                title_icon = f"https://images.evetech.net/corporations/{self.victim.corp_id}/logo?size=64"
                url = f"https://zkillboard.com/corporation/{self.victim.corp_id}/"
            embed = make_embed(
                title=f"{title}",
                msg_colour=color,
                title_url=url,
                subtitle=f"{self.victim.ship} destroyed in {self.system} ({self.region})",
                subtitle_url=self.url,
                content=self.info_output(),
                icon=title_icon,
                fields={"Information": await self.info_victim()},
                thumbnail=f"https://image.eveonline.com/Type/{self.victim.ship_type_id}_128.png",
                footer=f"zKillboard • {self.time.strftime('%Y-%m-%d %H:%M EVE')}",
                footer_icon="https://zkillboard.com/img/wreck.png",
            )
            # Send Message
            await channel.send(embed=embed)
        # pylint: disable=broad-except
        except Exception as e:
            if "Missing Access" in str(e):
                allowed_channels = [
                    c
                    for c in channel.guild.channels
                    if isinstance(c, discord.TextChannel)
                    and c.permissions_for(channel.guild.me).send_messages
                ]
                if allowed_channels:
                    alternative_channel = allowed_channels[0]
                    try:
                        await alternative_channel.send(embed=embed)
                        await alternative_channel.send(
                            f"❌ Permission ERROR: The killmail couldn't be sent to the channel - **<#{channel.id}>**"
                        )
                        log.info(f"Berechtigungsfehler: {e}", exc_info=True)
                        return
                    # pylint: disable=broad-except
                    except Exception as exc:
                        log.info(
                            f"Berechtigungsfehler Für Alle Channels: {exc}",
                            exc_info=True,
                        )
            log.error(f"Fehler bei Send Embed: {e}", exc_info=True)


class Subscription:
    __slots__ = ("id", "channel", "losses", "threshold", "group_id", "killmail_sent")

    killmail_sent_per_channel = {}

    def __init__(
        self,
        id_: int,
        channel,
        threshold: int = None,
        losses: bool = True,
        group_id: int = None,
    ):
        self.id = id_
        self.channel = channel

        self.losses = losses
        self.threshold = threshold

        self.group_id = group_id if group_id != 6 else None

    def __repr__(self):
        id_ = self.id
        chan = self.channel
        th = self.threshold
        loss = f" losses={self.losses}" if self.losses else ""
        grp = f"group_id={self.group_id}" if self.group_id else ""
        return f"<Subscription {id_} channel={chan} threshold={th}{loss}{grp}>"

    async def mail(self, killmail: Mail):
        if await self.valid(killmail):
            if self.group_id:
                is_loss = self.group_id in [killmail.corp_id, killmail.alliance_id]
            else:
                is_loss = False

            # Ckeck if Killmail is already sent on current Channel
            if self.channel.id not in Subscription.killmail_sent_per_channel:
                Subscription.killmail_sent_per_channel[self.channel.id] = set()

            if (
                killmail.id
                not in Subscription.killmail_sent_per_channel[self.channel.id]
            ):
                Subscription.killmail_sent_per_channel[self.channel.id].add(killmail.id)

                asyncio.create_task(killmail.send_embed(self.channel, is_loss))

    async def valid(self, killmail: Mail):
        if killmail.value:
            if self.threshold and killmail.value < self.threshold:
                return False

        # Get Global Killmail if group ID is none
        if not self.group_id:
            return True

        # Get System ID Killmail
        if self.group_id == killmail.system_id:
            return True

        # Check if is Loose
        if self.losses and self.group_id in [killmail.corp_id, killmail.alliance_id]:
            return True

        # Get Corporation Killmail
        if any(a.corp_id == self.group_id for a in killmail.attackers.values()):
            return True

        # Get Alliance Killmail
        if any(a.alliance_id == self.group_id for a in killmail.attackers.values()):
            return True

        # Check if Region ID exist otherwise fetch information from System ID
        if not killmail.region_id:
            await killmail.fetch_celestial()
            killmail.region_id = await killmail.fetch_region_id()

        # Get Region Killmail
        if self.group_id == (killmail.region_id):
            return True

        # Get Character Killmail - Only Kills possible no Loses
        if any(
            (hasattr(a, "id") and a.id == self.group_id)
            for a in killmail.attackers.values()
        ):
            return True

        return False
