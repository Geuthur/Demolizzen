# Standard Library
import asyncio
import datetime
import logging
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Optional

# Discord
import discord

# Django
from django.utils import timezone

# Demolizzen
from demolizzen import __package_name__, models
from demolizzen.core.openapi import OpenAPI
from demolizzen.utils.functions import make_embed

if TYPE_CHECKING:
    # pylint: disable=import-outside-toplevel
    # Demolizzen
    from demolizzen.core.bot import Demolizzen

logger = logging.getLogger(f"{__package_name__}")


@dataclass
class _KillmailBase:
    """Base class for all Killmail."""

    def asdict(self) -> dict:
        """Return this object as dict."""
        return asdict(self)


@dataclass
class _KillmailCharacter(_KillmailBase):
    ENTITY_PROPS = [
        "character_id",
        "corporation_id",
        "alliance_id",
        "faction_id",
        "ship_type_id",
    ]

    character_id: int | None = None
    character_name: str | None = None
    corporation_id: int | None = None
    corporation_name: str | None = None
    alliance_id: int | None = None
    alliance_name: str | None = None
    faction_id: int | None = None
    ship_type_id: int | None = None
    ship_name: str | None = None

    async def fetch_name(self, esi: OpenAPI):
        """Fetch the name from ESI."""
        if self.character_id and not self.character_name:
            self.character_name = await esi.get_or_create_character_name(
                self.character_id
            )
        if self.corporation_id and not self.corporation_name:
            self.corporation_name = await esi.get_or_create_corporation_name(
                self.corporation_id
            )
        if self.alliance_id and not self.alliance_name:
            self.alliance_name = await esi.get_or_create_alliance_name(self.alliance_id)

    async def fetch_ship_name(self, esi: OpenAPI):
        """Fetch the ship name from ESI."""
        if self.ship_type_id and not self.ship_name:
            ship = await esi.item_info_db(self.ship_type_id)
            if ship:
                self.ship_name = ship.name


@dataclass
class KillmailVictim(_KillmailCharacter):
    """A victim on a killmail."""

    damage_taken: int | None = None


@dataclass
class KillmailAttacker(_KillmailCharacter):
    """An attacker on a killmail."""

    ENTITY_PROPS = _KillmailCharacter.ENTITY_PROPS + ["weapon_type_id"]

    damage_done: int | None = None
    is_final_blow: bool | None = None
    security_status: float | None = None
    weapon_type_id: int | None = None


@dataclass
class KillmailPosition(_KillmailBase):
    "A position for a killmail."

    x: float | None = None
    y: float | None = None
    z: float | None = None


@dataclass
class KillmailZkb(_KillmailBase):
    """A ZKB entry for a killmail."""

    location_id: int | None = None
    hash: str | None = None
    fitted_value: float | None = None
    dropped_value: float | None = None
    destroyed_value: float | None = None
    total_value: float | None = None
    points: int | None = None
    is_npc: bool | None = None
    is_solo: bool | None = None
    is_awox: bool | None = None
    attacker_count: int | None = None


@dataclass
class KillmailManager(_KillmailBase):
    """Killmail"""

    id: int
    time: timezone.datetime
    victim: KillmailVictim
    attackers: list[KillmailAttacker]
    position: KillmailPosition
    zkb: KillmailZkb
    final_attacker: KillmailAttacker | None = None
    solar_system_id: int | None = None
    solar_system_name: str | None = None
    region_id: int | None = None
    region_name: str | None = None
    celestial: str | None = None
    _esi: OpenAPI = field(default=None, init=False, repr=False)
    _celestial_lock: asyncio.Lock = field(
        default_factory=asyncio.Lock, init=False, repr=False
    )

    def __repr__(self):
        return f"<Killmail {self.id} at {self.time} in system {self.solar_system_id}>"

    async def attackers_final_attacker(self):
        """Get the final attacker from the list of attackers."""
        if not self.attackers:
            return None
        for attacker in self.attackers:
            if attacker.is_final_blow:
                self.final_attacker = attacker
                return attacker

    async def attackers_corporation_ids(self):
        """Get a list of unique corporation IDs from the attackers."""
        corp_ids = set()
        for attacker in self.attackers:
            if attacker.corporation_id:
                corp_ids.add(attacker.corporation_id)
        return list(corp_ids)

    async def attackers_alliance_ids(self):
        """Get a list of unique alliance IDs from the attackers."""
        alliance_ids = set()
        for attacker in self.attackers:
            if attacker.alliance_id:
                alliance_ids.add(attacker.alliance_id)
        return list(alliance_ids)

    async def attackers_character_ids(self):
        """Get a list of unique character IDs from the attackers."""
        char_ids = set()
        for attacker in self.attackers:
            if attacker.character_id:
                char_ids.add(attacker.character_id)
        return list(char_ids)

    async def killmail_region_id(self):
        """Get the unique region ID from the solar system."""
        if self.region_id:
            return self.region_id

        self.region_id = await self.fetch_region_id()

        if self.region_id is None:
            return False
        return self.region_id

    async def fetch_celestial(self):
        async with self._celestial_lock:
            if not self.celestial:
                if not self.zkb.location_id:
                    return "Unknown"
                celestial = await self._esi.get_celestial_info(self.zkb.location_id)
                if celestial:
                    self.celestial = celestial.name
                else:
                    self.celestial = "Unknown"

    async def fetch_solar_system_name(self):
        """Fetch the solar system name from ESI."""
        if not self.solar_system_name:

            if not self.solar_system_id:
                return "Unknown"

            system = await self._esi.get_or_create_solar_system(self.solar_system_id)

            if system is not None:
                self.solar_system_name = system.solarSystemName
            else:
                self.solar_system_name = "Unknown"

    async def fetch_region_id(self):
        """Fetch the region ID from the solar system ID."""
        if not self.region_id:
            region = await self._esi.get_region_info(self.solar_system_id)
            if region:
                self.region_id = region.regionID
                return self.region_id
            return None

    async def fetch_esi_data(self):
        """Fetch all necessary data from ESI."""
        await asyncio.gather(
            self.attackers_final_attacker(),
            self.fetch_region_id(),
            self.fetch_solar_system_name(),
            self.fetch_celestial(),
            self.victim.fetch_name(self._esi),
            self.victim.fetch_ship_name(self._esi),
        )

    def content_info(self):
        info = [
            f"{self.solar_system_name} • System: "
            f"[Map](http://evemaps.dotlan.net/search?q={self.solar_system_id}) | "
            f"[Killboard](https://zkillboard.com/system/{self.solar_system_id}/)",
        ]
        if self.celestial:
            info.append(f"Nearest Celestial: `{self.celestial}`")

        return "\n".join(info)

    async def info_victim(self):
        """Collect additional information about the victim."""
        info = [
            f"**[{self.victim.character_name}](https://zkillboard.com/character/{self.victim.character_id}/)** ([{self.victim.corporation_name}](https://zkillboard.com/corporation/{self.victim.corporation_id}/)) lost their **`{self.victim.ship_name}`** in **`{self.solar_system_name}`** worth **`{self.zkb.total_value or 0:,}`** ISK",
        ]
        if self.final_attacker:
            info.append(
                f"Final Blow by **[{self.final_attacker.character_name}](https://zkillboard.com/character/{self.final_attacker.character_id}/)** ([{self.final_attacker.corporation_name}](https://zkillboard.com/corporation/{self.final_attacker.corporation_id}/)) in a `{self.final_attacker.ship_name}`"
            )
        if self.attackers:
            if self.zkb.attacker_count == 1:
                info.append("**SOLO KILL**")
            else:
                info.append(f"**Attackers: `{self.zkb.attacker_count}`**")
        return "\n".join(info)

    async def send_embed(self, channel: discord.TextChannel, is_loss=False):
        try:
            await self.fetch_esi_data()

            if self.final_attacker:
                await asyncio.gather(
                    self.final_attacker.fetch_name(self._esi),
                    self.final_attacker.fetch_ship_name(self._esi),
                )

            color = "red" if is_loss else "green"
            if self.victim.alliance_id:
                title = self.victim.alliance_name
                title_icon = f"https://images.evetech.net/alliances/{self.victim.alliance_id}/logo?size=64"
                url = f"https://zkillboard.com/alliance/{self.victim.alliance_id}/"
            else:
                title = self.victim.corporation_name
                title_icon = f"https://images.evetech.net/corporations/{self.victim.corporation_id}/logo?size=64"
                url = (
                    f"https://zkillboard.com/corporation/{self.victim.corporation_id}/"
                )

            embed = make_embed(
                title=f"{title}",
                msg_colour=color,
                title_url=url,
                subtitle=f"{self.victim.ship_name} destroyed in {self.solar_system_name}",
                subtitle_url=f"https://zkillboard.com/kill/{self.id}/",
                content=self.content_info(),
                icon=title_icon,
                fields={"Information": await self.info_victim()},
                thumbnail=f"https://image.eveonline.com/Type/{self.victim.ship_type_id}_128.png",
                footer=f"zKillboard • {self.time.strftime('%Y-%m-%d %H:%M EVE')}",
                footer_icon="https://zkillboard.com/img/wreck.png",
            )
            await channel.send(embed=embed)
        except discord.errors.Forbidden:
            logger.info(
                f"Bot in {channel.guild.name} has no permission to send messages in channel {channel.name} ({channel.id})"
            )
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
                    return
                except Exception as exc:  # pylint: disable=broad-except
                    logger.info(
                        f"Berechtigungsfehler Für Alle Channels: {exc}",
                        exc_info=True,
                    )
        except discord.errors.NotFound:
            logger.info(f"Channel {channel.name} ({channel.id}) was deleted.")
            await models.ZKillboard.objects.filter(channel_id=channel.id).adelete()
            logger.info(f"Removed Subscription for deleted channel {channel.id}.")
            raise
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Failed to send killmail embed: {e}", exc_info=True)
            return

    @classmethod
    def _extract_victim_and_position(cls, killmail_data: dict):
        victim = KillmailVictim()
        position = KillmailPosition()
        if "victim" in killmail_data:
            victim_data = killmail_data["victim"]
            params = {}
            for prop in KillmailVictim.ENTITY_PROPS + ["damage_taken"]:
                if prop in victim_data:
                    params[prop] = victim_data[prop]

            victim = KillmailVictim(**params)

            if "position" in victim_data:
                position_data = victim_data["position"]
                params = {}
                for prop in ["x", "y", "z"]:
                    if prop in position_data:
                        params[prop] = position_data[prop]

                position = KillmailPosition(**params)

        return victim, position

    @classmethod
    def _extract_attackers(cls, killmail_data: dict) -> list[KillmailAttacker]:
        attackers = []
        for attacker_data in killmail_data.get("attackers", []):
            params = {}
            for prop in KillmailAttacker.ENTITY_PROPS + [
                "damage_done",
                "security_status",
            ]:
                if prop in attacker_data:
                    params[prop] = attacker_data[prop]

            if "final_blow" in attacker_data:
                params["is_final_blow"] = attacker_data["final_blow"]

            attackers.append(KillmailAttacker(**params))
        return attackers

    @classmethod
    def _extract_zkb(cls, zkb_data):
        params = {}
        for prop, mapping in (
            ("locationID", "location_id"),
            ("hash", None),
            ("fittedValue", "fitted_value"),
            ("droppedValue", "dropped_value"),
            ("destroyedValue", "destroyed_value"),
            ("totalValue", "total_value"),
            ("points", None),
            ("npc", "is_npc"),
            ("solo", "is_solo"),
            ("awox", "is_awox"),
            ("attackerCount", "attacker_count"),
        ):
            if prop in zkb_data:
                if mapping:
                    params[mapping] = zkb_data[prop]
                else:
                    params[prop] = zkb_data[prop]

        return KillmailZkb(**params)

    @classmethod
    def _create_from_zkb(
        cls, zkb_package: dict, bot: "Demolizzen"
    ) -> Optional["KillmailManager"]:
        """Create a Killmail from zKillboard data."""
        if not zkb_package:
            return None

        killmail = None
        try:
            killmail_id = zkb_package["killmail_id"]
            esi_data = zkb_package["esi"]
            zkb = zkb_package["zkb"]
            killmail_time = esi_data["killmail_time"]
        except KeyError:
            logger.warning("Incomplete Response: %s", zkb_package)
            return None

        victim, position = cls._extract_victim_and_position(esi_data)
        attackers = cls._extract_attackers(esi_data)
        zkb = cls._extract_zkb(zkb)

        params = {
            "id": killmail_id,
            "time": timezone.datetime.strptime(
                killmail_time, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=datetime.timezone.utc),
            "victim": victim,
            "attackers": attackers,
            "position": position,
            "zkb": zkb,
        }
        if "solar_system_id" in esi_data:
            params["solar_system_id"] = esi_data["solar_system_id"]

        killmail = KillmailManager(**params)
        killmail._esi = bot.esi_data
        return killmail


class Subscription:
    killmail_sent_per_channel = {}

    def __init__(
        self,
        id_: int,
        channel: discord.TextChannel,
        threshold: int = None,
        losses: bool = True,
        group_id: int = None,
    ):
        self.id = id_
        self.channel = channel

        self.losses = losses
        self.threshold = threshold

        self.group_id = group_id if group_id != 6 else None
        self.disabled = False

    def __repr__(self):
        id_ = self.id
        chan = self.channel
        th = self.threshold
        loss = f" losses={self.losses}" if self.losses else ""
        grp = f"group_id={self.group_id}" if self.group_id else ""
        return f"<Subscription {id_} channel={chan} threshold={th}{loss}{grp}>"

    async def mail(self, killmail: KillmailManager):
        if self.disabled:
            return

        if await self.valid(killmail):
            if self.group_id:
                is_loss = self.group_id in [
                    killmail.victim.corporation_id,
                    killmail.victim.alliance_id,
                ]
            else:
                is_loss = False

            # Check if Killmail is already sent on current Channel
            if self.channel.id not in Subscription.killmail_sent_per_channel:
                Subscription.killmail_sent_per_channel[self.channel.id] = set()

            if (
                killmail.id
                not in Subscription.killmail_sent_per_channel[self.channel.id]
            ):
                Subscription.killmail_sent_per_channel[self.channel.id].add(killmail.id)
                asyncio.create_task(self._send_embed(killmail, is_loss))

    async def _send_embed(self, killmail: KillmailManager, is_loss: bool):
        """Send embed and disable this subscription permanently if the channel was deleted."""
        try:
            await killmail.send_embed(self.channel, is_loss)
        except discord.errors.NotFound:
            await self._disable_deleted_channel()

    async def _disable_deleted_channel(self):
        if self.disabled:
            return

        self.disabled = True
        await models.ZKillboard.objects.filter(id=self.id).adelete()
        Subscription.killmail_sent_per_channel.pop(self.channel.id, None)
        logger.info(
            "Disabled stale subscription %s because channel %s no longer exists.",
            self.id,
            self.channel.id,
        )

    async def valid(self, killmail: KillmailManager):
        if killmail.zkb.total_value:
            if self.threshold and killmail.zkb.total_value < self.threshold:
                return False

        # Get Global Killmail if group ID is none
        if not self.group_id:
            return True

        # Get System ID Killmail
        if self.group_id == killmail.solar_system_id:
            return True

        # Check if is Loss
        if self.losses and self.group_id in [
            killmail.victim.corporation_id,
            killmail.victim.alliance_id,
        ]:
            return True

        # Get Corporation Killmail
        if self.group_id in await killmail.attackers_corporation_ids():
            return True

        # Get Alliance Killmail
        if self.group_id in await killmail.attackers_alliance_ids():
            return True

        # Get Region Killmail
        if self.group_id == await killmail.killmail_region_id():
            return True

        # Get Character Killmail - Only Kills possible no Losses
        if self.group_id in await killmail.attackers_character_ids():
            return True

        return False
