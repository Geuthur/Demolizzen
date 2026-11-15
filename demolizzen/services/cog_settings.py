"""Which cogs are active in which guild.

A cog is active in a guild when it is enabled by default and not listed in
``GuildSettings.disabled_cogs``, or when it is listed in
``GuildSettings.enabled_cogs``. Empty or missing data therefore means
"everything the registry enables by default".
"""

# Standard Library
import time
from collections.abc import Iterable

# Third Party
from asgiref.sync import sync_to_async

# Django
from django.db import transaction

# Demolizzen
from demolizzen.core import registry
from demolizzen.models import GuildProfile, GuildSettings
from demolizzen.services.errors import (
    CogNotToggleable,
    DependencyConflict,
    GuildNotRegistered,
)

# Settings are cached per guild. The lifetime bounds how long a change made by
# another process (the web panel) takes to reach the bot.
CACHE_TTL_SECONDS = 60
# Guilds per query in fresh_states; stays below SQLite's variable limit.
_FRESH_CHUNK = 500

_clock = time.monotonic
_cache: dict[int, tuple[float, frozenset[str], frozenset[str]]] = {}


def invalidate(guild_id: int | None = None) -> None:
    """Forget cached settings of one guild, or of all guilds."""
    if guild_id is None:
        _cache.clear()
    else:
        _cache.pop(guild_id, None)


def _clean(value) -> frozenset[str]:
    """Reduce a stored JSON value to the known, toggleable cog keys in it."""
    if not isinstance(value, list):
        return frozenset()
    return frozenset(
        key
        for key in value
        if isinstance(key, str)
        and key in registry.REGISTRY
        and registry.REGISTRY[key].toggleable
    )


def _active(key: str, disabled: frozenset[str], enabled: frozenset[str]) -> bool:
    info = registry.get(key)
    if not info.toggleable:
        return True
    return (info.default_enabled and key not in disabled) or key in enabled


async def _lists(guild_id: int) -> tuple[frozenset[str], frozenset[str]]:
    cached = _cache.get(guild_id)
    now = _clock()
    if cached is not None and cached[0] > now:
        return cached[1], cached[2]

    settings = await GuildSettings.objects.filter(guild_id=guild_id).afirst()
    if settings is None:
        disabled, enabled = frozenset(), frozenset()
    else:
        disabled = _clean(settings.disabled_cogs)
        enabled = _clean(settings.enabled_cogs)
    _cache[guild_id] = (now + CACHE_TTL_SECONDS, disabled, enabled)
    return disabled, enabled


async def is_enabled(guild_id: int, key: str) -> bool:
    """Whether the cog is active in the guild. Reading never creates rows."""
    if not registry.get(key).toggleable:
        return True
    disabled, enabled = await _lists(guild_id)
    return _active(key, disabled, enabled)


async def get_states(guild_id: int) -> dict[str, bool]:
    """The state of every toggleable cog in the guild, in registry order."""
    disabled, enabled = await _lists(guild_id)
    return {
        info.key: _active(info.key, disabled, enabled) for info in registry.toggleable()
    }


async def fresh_states(guild_ids: Iterable[int]) -> dict[int, dict[str, bool]]:
    """The state of every toggleable cog in each guild, read from the database now.

    The bot uses this to decide which commands a server gets, so a change made
    by another process must not wait for the cache; the cache is renewed with
    what was read. Every asked guild is answered, known to the database or not.
    """
    wanted = list(dict.fromkeys(guild_ids))
    stored: dict[int, tuple[frozenset[str], frozenset[str]]] = {}
    for start in range(0, len(wanted), _FRESH_CHUNK):
        rows = GuildSettings.objects.filter(
            guild_id__in=wanted[start : start + _FRESH_CHUNK]
        ).values_list("guild_id", "disabled_cogs", "enabled_cogs")
        async for guild_id, disabled, enabled in rows:
            stored[guild_id] = (_clean(disabled), _clean(enabled))

    expires = _clock() + CACHE_TTL_SECONDS
    states: dict[int, dict[str, bool]] = {}
    for guild_id in wanted:
        disabled, enabled = stored.get(guild_id, (frozenset(), frozenset()))
        _cache[guild_id] = (expires, disabled, enabled)
        states[guild_id] = {
            info.key: _active(info.key, disabled, enabled)
            for info in registry.toggleable()
        }
    return states


async def enabled_guild_ids(key: str, guild_ids: Iterable[int]) -> set[int]:
    """The guilds out of ``guild_ids`` in which the cog is active."""
    return {guild_id for guild_id in guild_ids if await is_enabled(guild_id, key)}


def _set_enabled_sync(
    guild_id: int, key: str, enabled: bool, cascade: bool
) -> list[str]:
    if not registry.get(key).toggleable:
        raise CogNotToggleable(key)

    with transaction.atomic():
        if not GuildProfile.objects.filter(guild_id=guild_id).exists():
            raise GuildNotRegistered(guild_id)
        GuildSettings.objects.get_or_create(guild_id=guild_id)
        # Read the row fresh and locked so a concurrent change is not overwritten
        # with values from this process' cache.
        settings = GuildSettings.objects.select_for_update().get(guild_id=guild_id)
        disabled_now = _clean(settings.disabled_cogs)
        enabled_now = _clean(settings.enabled_cogs)

        if enabled:
            affected = [
                other
                for other in registry.requirements(key)
                if not _active(other, disabled_now, enabled_now)
            ]
        else:
            affected = [
                other
                for other in registry.dependents(key)
                if _active(other, disabled_now, enabled_now)
            ]
        if affected and not cascade:
            raise DependencyConflict(key, enabled, affected)

        changed = [key, *affected]
        disabled_set, enabled_set = set(disabled_now), set(enabled_now)
        for current in changed:
            default = registry.get(current).default_enabled
            disabled_set.discard(current)
            enabled_set.discard(current)
            if enabled and not default:
                enabled_set.add(current)
            elif not enabled and default:
                disabled_set.add(current)

        settings.disabled_cogs = [k for k in registry.REGISTRY if k in disabled_set]
        settings.enabled_cogs = [k for k in registry.REGISTRY if k in enabled_set]
        settings.save(update_fields=["disabled_cogs", "enabled_cogs"])
    return changed


async def set_enabled(
    guild_id: int, key: str, enabled: bool, *, cascade: bool = False
) -> list[str]:
    """Switch a cog for a guild and return every cog that was switched, ``key`` first.

    Disabling a cog that active cogs depend on, or enabling a cog whose
    requirements are off, raises :class:`DependencyConflict` and changes nothing
    unless ``cascade`` is set; then the affected cogs are switched along with it.
    """
    try:
        return await sync_to_async(_set_enabled_sync)(guild_id, key, enabled, cascade)
    finally:
        invalidate(guild_id)
