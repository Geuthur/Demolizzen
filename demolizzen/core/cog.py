"""Common base for all Demolizzen cogs."""

# Standard Library
import functools

# Discord
import discord
from discord.ext import commands

# Demolizzen
from demolizzen.core import registry
from demolizzen.core.errors import CogDisabled
from demolizzen.services import cog_settings


def resolve_guild_id(args: tuple) -> int | None:
    """Find the guild an event belongs to from the event's first argument."""
    if not args:
        return None
    first = args[0]
    if isinstance(first, discord.Guild):
        return first.id
    guild = getattr(first, "guild", None)
    if guild is not None:
        return guild.id
    return getattr(first, "guild_id", None)


def guild_listener(name: str | None = None):
    """Mark a cog method as an event listener that respects the guild's cog switch.

    Use it in place of ``commands.Cog.listener()`` on a :class:`BaseCog`. The
    listener is not called for events of a guild in which the cog is switched
    off. Events without a guild (direct messages, ``on_ready``) always run.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            if not await self.is_enabled(resolve_guild_id(args)):
                return None
            return await func(self, *args, **kwargs)

        return commands.Cog.listener(name or func.__name__)(wrapper)

    return decorator


class BaseCog(commands.Cog):
    """Base class for cogs.

    Subclasses set ``key`` to their entry in :mod:`demolizzen.core.registry`.
    Commands of the cog are then refused, and listeners declared with
    :func:`guild_listener` skipped, in guilds that switched the cog off.

    A subclass that overrides ``cog_check`` must call ``super().cog_check(ctx)``.
    """

    key: str

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        key = getattr(cls, "key", None)
        if not isinstance(key, str) or key not in registry.REGISTRY:
            raise TypeError(
                f"{cls.__name__} must set 'key' to an entry of "
                f"demolizzen.core.registry (got {key!r})."
            )

    def __init__(self, bot):
        self.bot = bot

    async def is_enabled(self, guild_id: int | None) -> bool:
        """Whether this cog is active in the guild. No guild means active."""
        if guild_id is None:
            return True
        return await cog_settings.is_enabled(guild_id, self.key)

    async def cog_check(self, ctx) -> bool:
        """Refuse the command when the cog is switched off in the guild."""
        guild = getattr(ctx, "guild", None)
        if guild is not None and not await self.is_enabled(guild.id):
            raise CogDisabled(self.key)
        return True
