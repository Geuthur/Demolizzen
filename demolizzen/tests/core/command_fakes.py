"""A stand-in for Discord's application command endpoints."""

# Standard Library
import copy
from unittest.mock import MagicMock

# Discord
import discord


class FakeCommandStore:
    """Keeps commands per scope the way Discord does.

    ``None`` is the global scope, a guild id a server. A bulk overwrite keeps
    the id of a command whose name was there before and gives new names new
    ids; a guild command has a different id in every server.
    """

    def __init__(self):
        self.commands: dict[int | None, list[dict]] = {None: []}
        self.requests: list[tuple[str, int | None]] = []
        self.refused: set[int] = set()
        # Scopes that answer with a server error; None is the global scope.
        self.broken: set[int | None] = set()
        self._next_id = 1000

    # --- what a test asks ---

    def names(self, guild_id: int | None = None) -> list[str]:
        return sorted(entry["name"] for entry in self.commands.get(guild_id, []))

    def writes(self) -> list[int | None]:
        return [scope for verb, scope in self.requests if verb == "put"]

    def command_id(self, name: str, guild_id: int | None = None) -> str:
        return next(
            entry["id"] for entry in self.commands[guild_id] if entry["name"] == name
        )

    # --- what py-cord calls ---

    async def get_global_commands(self, _application_id):
        self.requests.append(("get", None))
        return copy.deepcopy(self.commands[None])

    async def get_guild_commands(self, _application_id, guild_id):
        self._gate(guild_id)
        self.requests.append(("get", guild_id))
        return copy.deepcopy(self.commands.get(guild_id, []))

    async def bulk_upsert_global_commands(self, _application_id, payload):
        self._gate(None)
        return self._put(None, payload)

    async def bulk_upsert_guild_commands(self, _application_id, guild_id, payload):
        self._gate(guild_id)
        return self._put(guild_id, payload)

    async def _single_request(self, *_args, **_kwargs):
        raise AssertionError("commands are registered in bulk only")

    # py-cord looks these up even when it then registers in bulk.
    upsert_global_command = delete_global_command = edit_global_command = (
        _single_request
    )
    upsert_guild_command = delete_guild_command = edit_guild_command = _single_request

    def _gate(self, guild_id: int | None) -> None:
        if guild_id in self.refused:
            response = MagicMock(status=403, reason="Forbidden")
            raise discord.Forbidden(response, "Missing Access")
        if guild_id in self.broken:
            response = MagicMock(status=500, reason="Internal Server Error")
            raise discord.DiscordServerError(response, "Server error")

    def _put(self, scope: int | None, payload: list[dict]) -> list[dict]:
        self.requests.append(("put", scope))
        known = {entry["name"]: entry["id"] for entry in self.commands.get(scope, [])}
        stored = []
        for item in payload:
            entry = copy.deepcopy(item)
            entry["id"] = known.get(item["name"]) or self._new_id()
            entry.setdefault("type", 1)  # Discord always answers with the type
            if scope is not None:
                entry["guild_id"] = str(scope)
            stored.append(entry)
        self.commands[scope] = stored
        return copy.deepcopy(stored)

    def _new_id(self) -> str:
        self._next_id += 1
        return str(self._next_id)
