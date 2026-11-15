"""Which slash commands a server is offered.

Commands of the always-on modules are global. Commands of the modules a server
can switch are registered per server, in exactly the servers where their
module is on, so a switched-off module disappears from the command list
instead of answering "switched off".

A command is *managed* here when its cog belongs to a toggleable entry of
:mod:`demolizzen.core.registry`. Everything else is registered the way it is
declared: globally, or in the servers its own ``guild_ids`` name.
"""

# Standard Library
import asyncio
import logging
import time

# Discord
import discord

# Demolizzen
from demolizzen.core import registry
from demolizzen.services import cog_settings

logger = logging.getLogger(__name__)

# A server that refuses guild commands is asked again after this long.
REFUSED_RETRY_SECONDS = 3600

# One bulk overwrite per scope. py-cord's comparison with what Discord has
# reports a difference for every command that sets ``contexts``, so asking
# first would only add a request.
_OVERWRITE = {"method": "bulk", "force": True, "delete_existing": True}

_clock = time.monotonic


def module_key(command) -> str | None:
    """The switchable module a top-level command belongs to, or ``None``."""
    key = getattr(getattr(command, "cog", None), "key", None)
    if not isinstance(key, str):
        return None
    info = registry.REGISTRY.get(key)
    return key if info is not None and info.toggleable else None


class CommandScope:
    """Registers each server's commands and remembers what was registered."""

    def __init__(self, bot):
        self.bot = bot
        self._lock = asyncio.Lock()
        # refresh() only follows changes; the first full sync comes from on_ready.
        self._started = False
        # False while the global list still has to reach Discord.
        self._global_registered = False
        # guild id -> switchable modules whose commands are registered there
        self._synced: dict[int, frozenset[str]] = {}
        # guild id -> time from which a refusing server is asked again
        self._refused: dict[int, float] = {}
        # guild id -> (command name, type) -> the id Discord gave it there
        self._ids: dict[int, dict[tuple[str, int], int]] = {}

    async def sync_all(self) -> list[int]:
        """Register every server's commands, then the global ones.

        Used at start and whenever the loaded modules changed. Servers come
        first: a command that moves from global to per-server is then shown
        twice for a moment instead of not at all.

        Returns
        -------
        list[int]
            The servers that could not be registered.
        """
        async with self._lock:
            if not self.bot.pending_application_commands:
                # Registering "nothing" would delete every command at Discord.
                logger.error(
                    "No commands are loaded; the commands registered with "
                    "Discord are left untouched."
                )
                return []
            wanted = await self._wanted()
            self._forget_left(wanted)
            self._assign(wanted)
            failed = [
                guild_id
                for guild_id, keys in wanted.items()
                if not await self._register(guild_id, keys)
            ]
            await self._register_global()
            self._drop_stale_routes()
            self._started = True
            return failed

    async def refresh(self) -> list[int]:
        """Register the servers whose active modules changed.

        Cheap when nothing changed: one database query and no request to
        Discord. Does nothing before the first :meth:`sync_all`.

        Returns
        -------
        list[int]
            The servers that were registered again.
        """
        async with self._lock:
            if not self._started:
                return []
            if not self._global_registered:
                await self._register_global()
            wanted = await self._wanted()
            self._forget_left(wanted)
            now = _clock()
            due = [
                guild_id
                for guild_id, keys in wanted.items()
                if self._synced.get(guild_id) != keys
                and self._refused.get(guild_id, 0) <= now
            ]
            if not due:
                return []
            self._assign(wanted)
            return [
                guild_id
                for guild_id in due
                if await self._register(guild_id, wanted[guild_id])
            ]

    async def sync_guild(self, guild_id: int) -> bool:
        """Register one server again, whether or not anything changed."""
        async with self._lock:
            wanted = await self._wanted()
            if guild_id not in wanted:
                return False
            self._assign(wanted)
            return await self._register(guild_id, wanted[guild_id])

    def command_id(self, command, guild_id: int | None) -> int | None:
        """The id of a top-level command as the given server knows it.

        Discord gives a guild command a different id in every server, so a
        command link has to carry the id of the server it is shown in.
        ``None`` when the command is not registered there.
        """
        if command.guild_ids is None:
            return int(command.id) if command.id is not None else None
        return self._ids.get(guild_id, {}).get((command.name, command.type))

    async def _wanted(self) -> dict[int, frozenset[str]]:
        """Every server of the bot with the switchable modules active there."""
        states = await cog_settings.fresh_states(guild.id for guild in self.bot.guilds)
        return {
            guild_id: frozenset(key for key, active in keys.items() if active)
            for guild_id, keys in states.items()
        }

    def _assign(self, wanted: dict[int, frozenset[str]]) -> None:
        """Point every managed command at the servers its module is on in."""
        for command in self.bot.pending_application_commands:
            key = module_key(command)
            if key is not None:
                command.guild_ids = [
                    guild_id for guild_id, keys in wanted.items() if key in keys
                ]

    async def _register(self, guild_id: int, keys: frozenset[str]) -> bool:
        commands = [
            command
            for command in self.bot.pending_application_commands
            if command.guild_ids is not None and guild_id in command.guild_ids
        ]
        try:
            registered = await self.bot.register_commands(
                commands, guild_id=guild_id, **_OVERWRITE
            )
        except discord.Forbidden:
            self._synced.pop(guild_id, None)
            self._refused[guild_id] = _clock() + REFUSED_RETRY_SECONDS
            logger.warning(
                "Server %s does not accept slash commands from this bot, so the "
                "commands of its modules are missing there. It has to invite "
                "the bot again with the applications.commands scope: %s",
                guild_id,
                self.bot.invite_url,
            )
            return False
        # One server must never cost another its commands.
        except Exception:  # pylint: disable=broad-exception-caught
            self._synced.pop(guild_id, None)
            logger.exception(
                "Slash commands of server %s could not be registered", guild_id
            )
            return False
        self._refused.pop(guild_id, None)
        self._synced[guild_id] = keys
        self._ids[guild_id] = {
            (entry["name"], entry.get("type", 1)): int(entry["id"])
            for entry in registered
        }
        return True

    async def _register_global(self) -> None:
        commands = [
            command
            for command in self.bot.pending_application_commands
            if command.guild_ids is None
        ]
        # Nothing to repeat unless Discord fails below.
        self._global_registered = True
        if not commands:
            logger.error(
                "No global commands are loaded; the global commands registered "
                "with Discord are left untouched."
            )
            return
        try:
            await self.bot.register_commands(commands, **_OVERWRITE)
        except Exception:  # pylint: disable=broad-exception-caught
            self._global_registered = False
            logger.exception("The global slash commands could not be registered")

    def _forget_left(self, wanted: dict[int, frozenset[str]]) -> None:
        """Drop what is remembered about servers the bot is no longer in."""
        for known in (self._synced, self._refused, self._ids):
            for guild_id in [guild_id for guild_id in known if guild_id not in wanted]:
                del known[guild_id]

    def _drop_stale_routes(self) -> None:
        """Forget command ids that lead to commands which are no longer loaded.

        py-cord files a command under every id it was registered with but
        removes only one of them when the command goes away. A module that was
        reloaded would otherwise still be reachable through its old objects.
        """
        # pylint: disable=protected-access
        routes = self.bot._application_commands
        loaded = {id(command) for command in self.bot.pending_application_commands}
        for command_id in [
            command_id
            for command_id, command in routes.items()
            if id(command) not in loaded
        ]:
            del routes[command_id]
