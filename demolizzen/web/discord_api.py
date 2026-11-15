"""Talks to Discord for the web panel: sign-in and the user's servers."""

# Standard Library
import logging
from urllib.parse import urlencode

# Third Party
import aiohttp

# Django
from django.conf import settings

# Demolizzen
from demolizzen import USER_AGENT_TEXT

AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
TOKEN_URL = "https://discord.com/api/oauth2/token"
API_URL = "https://discord.com/api/v10"
# identify: who signs in. guilds: their servers and their rights there.
SCOPES = "identify guilds"
TIMEOUT = aiohttp.ClientTimeout(total=10)

logger = logging.getLogger(__name__)


class DiscordError(Exception):
    """Discord could not be asked or gave an answer that cannot be used."""


class DiscordUnauthorized(DiscordError):
    """Discord no longer accepts the user's token."""


class DiscordClient:
    """The few Discord requests the panel needs.

    Every failure is raised as :class:`DiscordError`; a token Discord rejects
    as :class:`DiscordUnauthorized`.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        session_factory=aiohttp.ClientSession,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._session_factory = session_factory

    def authorize_url(self, state: str) -> str:
        """Where to send the browser to sign in. ``state`` ties the answer to
        the visitor's session."""
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._client_id,
                "scope": SCOPES,
                "redirect_uri": self._redirect_uri,
                "state": state,
                # Skip the consent screen for someone who has agreed before.
                "prompt": "none",
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    async def exchange_code(self, code: str) -> str:
        """Trade the code Discord sent back for the user's access token."""
        data = await self._request(
            "post",
            TOKEN_URL,
            # Discord accepts this request form encoded only.
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._redirect_uri,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        token = data.get("access_token") if isinstance(data, dict) else None
        if not isinstance(token, str) or not token:
            raise DiscordError("Discord sent no access token")
        return token

    async def fetch_user(self, token: str) -> dict:
        """The signed-in user."""
        data = await self._request("get", f"{API_URL}/users/@me", token=token)
        if not isinstance(data, dict) or "id" not in data:
            raise DiscordError("Discord sent no user")
        return data

    async def fetch_guilds(self, token: str) -> list[dict]:
        """The user's servers, each with ``owner`` and ``permissions``."""
        data = await self._request("get", f"{API_URL}/users/@me/guilds", token=token)
        if not isinstance(data, list):
            raise DiscordError("Discord sent no server list")
        return data

    async def _request(self, method: str, url: str, token: str | None = None, **kwargs):
        headers = {"User-Agent": USER_AGENT_TEXT}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        return await _request(
            self._session_factory,
            method,
            url,
            headers,
            # Only a user's token can be "no longer accepted".
            unauthorized=DiscordUnauthorized if token is not None else None,
            **kwargs,
        )


async def _request(
    session_factory, method: str, url: str, headers: dict, unauthorized=None, **kwargs
):
    """Send one request to Discord and return the decoded answer.

    Error texts never contain a token: they are logged and may be shown.
    """
    try:
        async with session_factory(timeout=TIMEOUT) as session:
            async with getattr(session, method)(
                url, headers=headers, **kwargs
            ) as response:
                if response.status == 401 and unauthorized is not None:
                    raise unauthorized("Discord rejected the token")
                if response.status != 200:
                    raise DiscordError(f"Discord answered {response.status}")
                return await response.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, ValueError) as error:
        logger.warning("Discord request failed: %r", error)
        raise DiscordError("Discord could not be reached") from error


class BotTokenMissing(DiscordError):
    """The panel has no bot token, so it cannot ask for channels and roles."""


class DiscordBotClient:
    """What the panel asks Discord as the bot: a server's channels and roles.

    The token is only ever sent to Discord.
    """

    def __init__(self, token: str, session_factory=aiohttp.ClientSession):
        self._token = token
        self._session_factory = session_factory

    async def _list(self, path: str) -> list[dict]:
        data = await _request(
            self._session_factory,
            "get",
            f"{API_URL}{path}",
            {"User-Agent": USER_AGENT_TEXT, "Authorization": f"Bot {self._token}"},
        )
        if not isinstance(data, list):
            raise DiscordError("Discord sent no list")
        return data

    async def fetch_channels(self, guild_id: int) -> list[dict]:
        """The server's channels and categories, without threads."""
        return await self._list(f"/guilds/{int(guild_id)}/channels")

    async def fetch_roles(self, guild_id: int) -> list[dict]:
        """The server's roles, @everyone included."""
        return await self._list(f"/guilds/{int(guild_id)}/roles")


def get_client() -> DiscordClient:
    """The client for the configured Discord application."""
    return DiscordClient(
        settings.DISCORD_CLIENT_ID,
        settings.DISCORD_CLIENT_SECRET,
        f"{settings.WEB_BASE_URL}/callback",
    )


def get_bot_client() -> DiscordBotClient:
    """The client that asks Discord as the bot."""
    token = getattr(settings, "BOT_TOKEN", None)
    if not token:
        raise BotTokenMissing("No bot token is configured")
    return DiscordBotClient(token)
