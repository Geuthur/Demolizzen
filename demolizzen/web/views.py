"""Pages of the web panel."""

# Standard Library
import logging
import secrets

# Django
from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET, require_POST

# Demolizzen
from demolizzen.core import registry
from demolizzen.services import cog_settings, guilds
from demolizzen.services.errors import (
    DependencyConflict,
    GuildNotRegistered,
    UnknownCog,
)
from demolizzen.web import access, discord_api, session
from demolizzen.web.base_settings import WEB_DIR
from demolizzen.web.discord_api import DiscordError

STYLESHEET = (WEB_DIR / "static" / "panel.css").read_bytes()
FONT = (WEB_DIR / "static" / "exo2.woff2").read_bytes()

logger = logging.getLogger(__name__)


def message(request, title: str, text: str, status: int = 200) -> HttpResponse:
    """A page that says one thing and leads back to the start."""
    return render(
        request, "web/message.html", {"title": title, "text": text}, status=status
    )


def healthz(request) -> HttpResponse:  # pylint: disable=unused-argument
    """Tells the container's health check that the panel answers."""
    return HttpResponse("ok", content_type="text/plain")


@require_GET
@cache_control(public=True, max_age=3600)
def stylesheet(request) -> HttpResponse:  # pylint: disable=unused-argument
    return HttpResponse(STYLESHEET, content_type="text/css; charset=utf-8")


@require_GET
@cache_control(public=True, max_age=7 * 24 * 3600)
def font(request) -> HttpResponse:  # pylint: disable=unused-argument
    """The typeface of headings (Exo 2, SIL Open Font License)."""
    return HttpResponse(FONT, content_type="font/woff2")


def not_found(request, exception=None) -> HttpResponse:
    """The page for an address that does not exist."""
    del exception  # Django passes it; the page says the same for every cause.
    return message(request, "Not found", "This page does not exist.", status=404)


def csrf_failure(request, reason="") -> HttpResponse:  # pylint: disable=unused-argument
    """A form was sent without the token that proves it came from the panel."""
    return message(
        request,
        "Form expired",
        "This form could not be accepted. Please go back, reload the page and try again.",
        status=403,
    )


def _landing(request, notice: str | None = None) -> HttpResponse:
    return render(request, "web/landing.html", {"notice": notice})


def _tally(states: dict[str, bool]) -> dict[str, int]:
    """How many of the switchable modules are on."""
    return {"on": sum(states.values()), "total": len(states)}


async def _servers(guild_ids: list[int], current: int | None = None) -> list[dict]:
    """The user's servers for the navigation, the open one marked."""
    return [
        {"id": guild_id, "name": name, "current": guild_id == current}
        for guild_id, name in await guilds.known_guilds(guild_ids)
    ]


async def home(request) -> HttpResponse:
    """The start page: the user's servers, or the offer to sign in."""
    user = session.current_user(request)
    if user is None:
        return _landing(request)
    guild_ids = await session.current_guild_ids(request, discord_api.get_client())
    if guild_ids is None:
        return _landing(request, "Your sign-in has ended. Please sign in again.")
    servers = await _servers(guild_ids)
    for server in servers:
        server.update(_tally(await cog_settings.get_states(server["id"])))
    return render(request, "web/servers.html", {"user": user, "servers": servers})


def login(request) -> HttpResponse:
    """Send the visitor to Discord to sign in."""
    if not (settings.DISCORD_CLIENT_ID and settings.DISCORD_CLIENT_SECRET):
        return message(
            request,
            "Sign-in unavailable",
            "Sign-in is not set up yet. The operator has to configure the "
            "Discord application of this panel.",
            status=503,
        )
    # Discord sends this value back; only the browser that started here has it.
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    return HttpResponseRedirect(discord_api.get_client().authorize_url(state))


async def callback(request) -> HttpResponse:
    """Discord sends the visitor back here after the sign-in."""
    # A state is good for one answer only.
    expected = request.session.pop("oauth_state", None)
    if "error" in request.GET:
        return _landing(request, "Sign-in was not completed.")

    state = request.GET.get("state", "")
    code = request.GET.get("code", "")
    if (
        not expected
        or not code
        or not secrets.compare_digest(state.encode(), expected.encode())
    ):
        return message(
            request,
            "Sign-in failed",
            "The sign-in could not be verified. Please try again.",
            status=400,
        )

    client = discord_api.get_client()
    try:
        token = await client.exchange_code(code)
        user = await client.fetch_user(token)
        listed = await client.fetch_guilds(token)
    except DiscordError:
        return message(
            request,
            "Sign-in failed",
            "Discord did not answer. Please try again in a moment.",
            status=502,
        )
    session.sign_in(request, user, token, await access.manageable_guild_ids(listed))
    return redirect("home")


@require_POST
def logout(request) -> HttpResponse:
    session.sign_out(request)
    return redirect("home")


async def _guild_access(request, guild_id: int):
    """Check that the signed-in user may manage the server.

    Returns the user, the server's name and the user's servers for the
    navigation; a redirect to the start when nobody is signed in. A server the
    user may not manage raises 404, exactly like one that does not exist.
    """
    user = session.current_user(request)
    guild_ids = await session.current_guild_ids(request, discord_api.get_client())
    if user is None or guild_ids is None:
        return redirect("home")
    servers = await _servers(guild_ids, current=guild_id)
    name = next((server["name"] for server in servers if server["current"]), None)
    if name is None:
        raise Http404
    return user, name, servers


async def guild(request, guild_id: int) -> HttpResponse:
    """One server: its modules and their state."""
    access_result = await _guild_access(request, guild_id)
    if isinstance(access_result, HttpResponse):
        return access_result
    user, name, servers = access_result

    states = await cog_settings.get_states(guild_id)
    modules = [
        {
            "key": info.key,
            "title": info.title,
            "description": info.description,
            "fixed": not info.toggleable,
            "on": states.get(info.key, True),
            # The modules this one cannot run without.
            "needs": _titles(list(info.requires)) if info.requires else "",
        }
        for info in registry.REGISTRY.values()
    ]
    return render(
        request,
        "web/guild.html",
        {
            "user": user,
            "servers": servers,
            "guild": {"id": guild_id, "name": name},
            "modules": modules,
            "tally": _tally(states),
            # Shown once: what the last switch did.
            "notice": request.session.pop("notice", None),
        },
    )


def _titles(keys: list[str]) -> str:
    """Module titles as a phrase: "A", "A and B", "A, B and C"."""
    titles = [registry.get(key).title for key in keys]
    if len(titles) == 1:
        return titles[0]
    return f"{', '.join(titles[:-1])} and {titles[-1]}"


def _dependency_question(title: str, enabled: bool, affected: list[str]) -> str:
    one = len(affected) == 1
    names = _titles(affected)
    it = "It" if one else "They"
    if enabled:
        return (
            f"{title} needs {names}, which {'is' if one else 'are'} off. "
            f"{it} will be switched on as well."
        )
    return (
        f"{names} need{'s' if one else ''} {title}. "
        f"{it} will be switched off as well."
    )


@require_POST
async def switch_module(request, guild_id: int, key: str) -> HttpResponse:
    """Switch a module of a server on or off."""
    access_result = await _guild_access(request, guild_id)
    if isinstance(access_result, HttpResponse):
        return access_result
    user, name, servers = access_result

    try:
        info = registry.get(key)
    except UnknownCog as error:
        raise Http404 from error
    if not info.toggleable:
        return message(
            request,
            "Not possible",
            f"{info.title} is always on and cannot be switched.",
            status=400,
        )
    if request.POST.get("enabled") not in ("0", "1"):
        return message(
            request, "Not possible", "This request could not be understood.", status=400
        )
    enabled = request.POST["enabled"] == "1"
    word = "on" if enabled else "off"

    try:
        changed = await cog_settings.set_enabled(
            guild_id, key, enabled, cascade=request.POST.get("confirm") == "1"
        )
    except DependencyConflict as conflict:
        # Nothing was changed. Ask, and repeat the request with the confirmation.
        return render(
            request,
            "web/confirm.html",
            {
                "user": user,
                "servers": servers,
                "guild": {"id": guild_id, "name": name},
                "module": info,
                "enabled": enabled,
                "word": word,
                "question": _dependency_question(
                    info.title, enabled, conflict.affected
                ),
            },
        )
    except GuildNotRegistered as error:
        raise Http404 from error

    logger.info(
        "user %s switched %s %s in guild %s",
        user["id"],
        ", ".join(changed),
        word,
        guild_id,
    )
    notice = f"{info.title} switched {word}"
    if len(changed) > 1:
        notice += f", together with {_titles(changed[1:])}"
    request.session["notice"] = f"{notice}."
    return redirect("guild", guild_id)
