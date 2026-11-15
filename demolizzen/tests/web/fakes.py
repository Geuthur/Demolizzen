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
