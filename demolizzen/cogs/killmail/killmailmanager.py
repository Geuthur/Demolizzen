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
from demolizzen.core.openapi import OpenAPI
from demolizzen.services.killmails import KillFacts
from demolizzen.utils.functions import make_embed

if TYPE_CHECKING:
    # pylint: disable=import-outside-toplevel
    # Demolizzen
    from demolizzen.core.bot import Demolizzen

logger = logging.getLogger(__name__)

UNKNOWN = "Unknown"


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

    def entity_ids(self) -> list[int]:
        """The ids whose names the killmail message shows."""
        return [
            entity_id
            for entity_id in (self.character_id, self.corporation_id, self.alliance_id)
            if entity_id
        ]

    def apply_names(self, names: dict[int, str]) -> None:
        if self.character_id:
            self.character_name = names.get(self.character_id, UNKNOWN)
        if self.corporation_id:
            self.corporation_name = names.get(self.corporation_id, UNKNOWN)
        if self.alliance_id:
            self.alliance_name = names.get(self.alliance_id, UNKNOWN)


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

    def __repr__(self):
        return f"<Killmail {self.id} at {self.time} in system {self.solar_system_id}>"

    def facts(self, region_id: int | None) -> KillFacts:
        """What the subscription rules need to know about this killmail."""
        return KillFacts(
            killmail_id=self.id,
            total_value=self.zkb.total_value or 0,
            solar_system_id=self.solar_system_id,
            region_id=region_id,
            victim_corporation_id=self.victim.corporation_id,
            victim_alliance_id=self.victim.alliance_id,
            attacker_corporation_ids=frozenset(
                a.corporation_id for a in self.attackers if a.corporation_id
            ),
            attacker_alliance_ids=frozenset(
                a.alliance_id for a in self.attackers if a.alliance_id
            ),
            attacker_character_ids=frozenset(
                a.character_id for a in self.attackers if a.character_id
            ),
        )

    async def _lookup(self, what: str, awaitable):
        """Await a lookup; a failure is logged and leaves the value unknown."""
        try:
            return await awaitable
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.warning("Killmail %s: %s lookup failed: %r", self.id, what, error)
            return None

    async def _ship_name(self, type_id: int | None) -> str:
        ship = await self._lookup("ship", self._esi.item_info_db(type_id))
        return getattr(ship, "name", None) or UNKNOWN

    async def _system_name(self) -> str:
        if not self.solar_system_id:
            return UNKNOWN
        system = await self._lookup(
            "solar system", self._esi.get_or_create_solar_system(self.solar_system_id)
        )
        return getattr(system, "solarSystemName", None) or UNKNOWN

    async def _celestial_name(self) -> str | None:
        if not self.zkb.location_id:
            return None
        celestial = await self._lookup(
            "celestial", self._esi.get_celestial_info(self.zkb.location_id)
        )
        return getattr(celestial, "name", None) or UNKNOWN

    async def enrich(self) -> None:
        """Look up everything the message shows. Runs once per killmail.

        All names of the victim and of the final attacker are resolved in a
        single request.
        """
        self.final_attacker = next(
            (attacker for attacker in self.attackers if attacker.is_final_blow), None
        )
        shown = [self.victim] + ([self.final_attacker] if self.final_attacker else [])
        ids = sorted(
            {entity_id for person in shown for entity_id in person.entity_ids()}
        )

        names, self.solar_system_name, self.celestial, *ships = await asyncio.gather(
            self._lookup("name", self._esi.resolve_names(ids)),
            self._system_name(),
            self._celestial_name(),
            *(self._ship_name(person.ship_type_id) for person in shown),
        )
        for person, ship_name in zip(shown, ships):
            person.apply_names(names or {})
            person.ship_name = ship_name

    def content_info(self):
        info = [
            f"{self.solar_system_name} • System: "
            f"[Map](http://evemaps.dotlan.net/search?q={self.solar_system_id}) | "
            f"[Killboard](https://zkillboard.com/system/{self.solar_system_id}/)",
        ]
        if self.celestial:
            info.append(f"Nearest Celestial: `{self.celestial}`")

        return "\n".join(info)

    def info_victim(self) -> str:
        """Describe victim, final blow and number of attackers."""
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

    def build_embed(self, is_loss: bool = False) -> discord.Embed:
        """The message for an enriched killmail."""
        if self.victim.alliance_id:
            title = self.victim.alliance_name
            title_icon = f"https://images.evetech.net/alliances/{self.victim.alliance_id}/logo?size=64"
            url = f"https://zkillboard.com/alliance/{self.victim.alliance_id}/"
        else:
            title = self.victim.corporation_name
            title_icon = f"https://images.evetech.net/corporations/{self.victim.corporation_id}/logo?size=64"
            url = f"https://zkillboard.com/corporation/{self.victim.corporation_id}/"

        return make_embed(
            title=f"{title}",
            msg_colour="red" if is_loss else "green",
            title_url=url,
            subtitle=f"{self.victim.ship_name} destroyed in {self.solar_system_name}",
            subtitle_url=f"https://zkillboard.com/kill/{self.id}/",
            content=self.content_info(),
            icon=title_icon,
            fields={"Information": self.info_victim()},
            thumbnail=f"https://image.eveonline.com/Type/{self.victim.ship_type_id}_128.png",
            footer=f"zKillboard • {self.time.strftime('%Y-%m-%d %H:%M EVE')}",
            footer_icon="https://zkillboard.com/img/wreck.png",
        )

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
            ).replace(tzinfo=datetime.UTC),
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
