"""The cogs Demolizzen offers to guilds.

This is the single place that says which cogs exist, which of them a guild may
switch off and which cogs need each other. The per-guild switch and the panel
only read from here; adding a cog means adding one entry.

This module must not import ``discord``.
"""

# Standard Library
from dataclasses import dataclass

# Demolizzen
from demolizzen.services.errors import UnknownCog


@dataclass(frozen=True)
class CogInfo:
    """Describes one cog. ``key`` is the name of its folder under ``demolizzen/cogs``."""

    key: str
    title: str
    description: str
    toggleable: bool = True
    default_enabled: bool = True
    requires: tuple[str, ...] = ()


_COGS = (
    # Always active
    CogInfo(
        "core", "Core", "Bot basics such as uptime and changelog.", toggleable=False
    ),
    CogInfo(
        "owner", "Owner", "Maintenance commands for the bot owner.", toggleable=False
    ),
    CogInfo("guild", "Guild", "Keeps servers and members in sync.", toggleable=False),
    CogInfo(
        "panel",
        "Panel",
        "Lets admins manage the modules of a server.",
        toggleable=False,
    ),
    # Offered to guilds
    CogInfo("admin", "Admin", "Administration and moderation commands."),
    CogInfo("general", "General", "General purpose features."),
    CogInfo("commands", "Commands", "Standard commands and help."),
    CogInfo("levelsystem", "Levelsystem", "Experience, levels and rank cards."),
    CogInfo("banksystem", "Banksystem", "Wallets, bank accounts and interest."),
    CogInfo("economy", "Economy", "Missions and rewards.", requires=("banksystem",)),
    CogInfo("shop", "Shop", "Buy items and ships.", requires=("banksystem",)),
    CogInfo(
        "games", "Games", "Mini games to win or lose money.", requires=("banksystem",)
    ),
    CogInfo("eveonline", "EVEOnline", "EVE Online information and prices."),
    CogInfo("killmail", "zKillboard", "Posts killmails from zKillboard."),
    CogInfo("ticket", "Ticket System", "Private help tickets for members."),
)

REGISTRY: dict[str, CogInfo] = {info.key: info for info in _COGS}


def get(key: str) -> CogInfo:
    """Return the entry for ``key`` or raise :class:`UnknownCog`."""
    try:
        return REGISTRY[key]
    except (KeyError, TypeError) as exc:
        raise UnknownCog(str(key)) from exc


def toggleable() -> list[CogInfo]:
    """All cogs a guild may switch, in registry order."""
    return [info for info in REGISTRY.values() if info.toggleable]


def requirements(key: str) -> list[str]:
    """All cogs ``key`` needs, directly or indirectly, in registry order."""
    found: set[str] = set()
    pending = list(get(key).requires)
    while pending:
        current = pending.pop()
        if current not in found:
            found.add(current)
            pending.extend(get(current).requires)
    return [k for k in REGISTRY if k in found]


def dependents(key: str) -> list[str]:
    """All cogs that need ``key``, directly or indirectly, in registry order."""
    get(key)
    return [k for k in REGISTRY if k != key and key in requirements(k)]
