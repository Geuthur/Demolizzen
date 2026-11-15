"""The channels and roles of a server, as choices for the panel's forms."""

# Standard Library
import asyncio
import time
from dataclasses import dataclass

# Demolizzen
from demolizzen.web import discord_api

# Discord's channel types.
TEXT = 0
CATEGORY = 4

# Discord is asked again after this long. Forms are loaded and then saved
# within moments, and Discord limits how often it may be asked.
CACHE_SECONDS = 60


@dataclass(frozen=True)
class Choice:
    id: int
    name: str


@dataclass(frozen=True)
class Directory:
    """What a server offers to choose from."""

    categories: list[Choice]
    # Named "#name", with the category in brackets where there is one.
    text_channels: list[Choice]
    # Highest role first, without @everyone.
    roles: list[Choice]


_cache: dict[int, tuple[float, Directory]] = {}


def _now() -> float:
    return time.monotonic()


def clear() -> None:
    """Forget everything that was fetched."""
    _cache.clear()


def _entries(listed) -> list[tuple[int, dict]]:
    """The entries of a Discord list that have a usable id and name."""
    entries = []
    for entry in listed:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            continue
        entry_id = entry.get("id")
        if isinstance(entry_id, str) and entry_id.isdecimal():
            entries.append((int(entry_id), entry))
    return entries


def _position(entry: dict) -> int:
    position = entry.get("position")
    return position if isinstance(position, int) else 0


def _build(guild_id: int, channels, roles) -> Directory:
    channel_entries = _entries(channels)
    categories = sorted(
        (
            (_position(entry), entry["name"], channel_id)
            for channel_id, entry in channel_entries
            if entry.get("type") == CATEGORY
        ),
    )
    category_order = {
        channel_id: index for index, (_, _, channel_id) in enumerate(categories)
    }
    category_names = {channel_id: name for _, name, channel_id in categories}

    text_channels = []
    for channel_id, entry in channel_entries:
        if entry.get("type") != TEXT:
            continue
        parent = entry.get("parent_id")
        parent_id = (
            int(parent) if isinstance(parent, str) and parent.isdecimal() else None
        )
        name = f"#{entry['name']}"
        if parent_id in category_names:
            name += f" ({category_names[parent_id]})"
        # Channels outside a category first, then category by category.
        order = (category_order.get(parent_id, -1), _position(entry), entry["name"])
        text_channels.append((order, Choice(channel_id, name)))

    role_entries = sorted(
        (
            (-_position(entry), entry["name"], role_id)
            for role_id, entry in _entries(roles)
            # The role with the server's own id is @everyone.
            if role_id != guild_id
        ),
    )
    return Directory(
        categories=[Choice(channel_id, name) for _, name, channel_id in categories],
        text_channels=[
            choice for _, choice in sorted(text_channels, key=lambda item: item[0])
        ],
        roles=[Choice(role_id, name) for _, name, role_id in role_entries],
    )


async def load(guild_id: int) -> Directory:
    """The channels and roles of a server.

    Raises :class:`~demolizzen.web.discord_api.DiscordError` when Discord
    cannot be asked; ``BotTokenMissing`` when the panel has no bot token.
    """
    cached = _cache.get(guild_id)
    if cached is not None and _now() - cached[0] < CACHE_SECONDS:
        return cached[1]

    client = discord_api.get_bot_client()
    channels, roles = await asyncio.gather(
        client.fetch_channels(guild_id), client.fetch_roles(guild_id)
    )
    found = _build(guild_id, channels, roles)
    _cache[guild_id] = (_now(), found)
    return found
