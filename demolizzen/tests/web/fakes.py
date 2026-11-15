"""Stand-ins for Discord in the web panel's tests."""

# Demolizzen
from demolizzen.web.discord_api import DiscordError


def listed(guild_id: int, permissions: str = "32", owner: bool = False) -> dict:
    """A server as Discord lists it for the signed-in user."""
    return {
        "id": str(guild_id),
        "name": f"G{guild_id}",
        "owner": owner,
        "permissions": permissions,
    }


class FakeDiscord:
    """Answers like the Discord client and remembers what it was asked."""

    def __init__(self):
        self.user = {"id": "10", "username": "alice", "global_name": "Alice"}
        self.guilds = []
        self.token = "tok"
        self.login_error: DiscordError | None = None
        self.guilds_error: DiscordError | None = None
        self.calls = []

    def authorize_url(self, state: str) -> str:
        return f"https://discord.com/oauth2/authorize?state={state}"

    async def exchange_code(self, code: str) -> str:
        self.calls.append(("code", code))
        if self.login_error is not None:
            raise self.login_error
        return self.token

    async def fetch_user(self, token: str) -> dict:
        self.calls.append(("user", token))
        return self.user

    async def fetch_guilds(self, token: str) -> list[dict]:
        self.calls.append(("guilds", token))
        if self.guilds_error is not None:
            raise self.guilds_error
        return self.guilds


def channel(channel_id: int, name: str, kind: int = 0, position: int = 0, parent=None):
    """A channel as Discord lists it for a server. Kinds: 0 text, 2 voice, 4 category."""
    return {
        "id": str(channel_id),
        "name": name,
        "type": kind,
        "position": position,
        "parent_id": str(parent) if parent else None,
    }


def role(role_id: int, name: str, position: int = 1) -> dict:
    return {"id": str(role_id), "name": name, "position": position, "managed": False}


class FakeBot:
    """Answers like the bot's Discord client: channels and roles per server."""

    def __init__(self):
        self.channels: dict[int, list] = {}
        self.roles: dict[int, list] = {}
        self.error: DiscordError | None = None
        self.calls = []

    async def fetch_channels(self, guild_id: int) -> list[dict]:
        self.calls.append(("channels", guild_id))
        if self.error is not None:
            raise self.error
        return self.channels.get(guild_id, [])

    async def fetch_roles(self, guild_id: int) -> list[dict]:
        self.calls.append(("roles", guild_id))
        if self.error is not None:
            raise self.error
        return self.roles.get(guild_id, [])
