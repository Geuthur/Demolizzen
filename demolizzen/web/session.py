"""Who is signed in, kept in the session cookie."""

# Standard Library
import time

# Demolizzen
from demolizzen.web import access
from demolizzen.web.discord_api import DiscordError, DiscordUnauthorized

# The list of manageable servers is asked from Discord again after this long.
# Discord limits how often it may be asked, so it is not fetched on every page.
REFRESH_SECONDS = 300
# While Discord cannot be asked, the last list stays valid this long at most.
# Without the limit, rights withdrawn in Discord would live on for as long as
# the check keeps failing.
MAX_STALE_SECONDS = 1800


def _now() -> float:
    return time.time()


def current_user(request) -> dict | None:
    """The signed-in user as ``{"id", "name"}``, or None."""
    return request.session.get("user")


def sign_in(request, user: dict, token: str, guild_ids: list[int]) -> None:
    """Start a fresh session for a user Discord has just vouched for."""
    request.session.flush()
    request.session["user"] = {
        "id": int(user["id"]),
        "name": user.get("global_name") or user.get("username") or str(user["id"]),
    }
    request.session["token"] = token
    request.session["guild_ids"] = guild_ids
    request.session["checked_at"] = _now()


def sign_out(request) -> None:
    request.session.flush()


async def current_guild_ids(request, client) -> list[int] | None:
    """The servers the signed-in user may manage, or None if nobody is signed in.

    A list older than :data:`REFRESH_SECONDS` is fetched again. A token Discord
    rejects signs the user out; so does a list that could not be checked for
    :data:`MAX_STALE_SECONDS`.
    """
    if current_user(request) is None:
        return None
    age = _now() - request.session.get("checked_at", 0)
    if age < REFRESH_SECONDS:
        return request.session.get("guild_ids", [])

    try:
        listed = await client.fetch_guilds(request.session.get("token", ""))
    except DiscordUnauthorized:
        sign_out(request)
        return None
    except DiscordError:
        if age > MAX_STALE_SECONDS:
            sign_out(request)
            return None
        return request.session.get("guild_ids", [])

    guild_ids = await access.manageable_guild_ids(listed)
    request.session["guild_ids"] = guild_ids
    request.session["checked_at"] = _now()
    return guild_ids
