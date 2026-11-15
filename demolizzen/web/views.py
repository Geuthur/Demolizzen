"""Pages of the web panel."""

# Standard Library
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
from demolizzen.web import access, discord_api, session
from demolizzen.web.base_settings import WEB_DIR
from demolizzen.web.discord_api import DiscordError

STYLESHEET = (WEB_DIR / "static" / "panel.css").read_bytes()


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


async def home(request) -> HttpResponse:
    """The start page: the user's servers, or the offer to sign in."""
    user = session.current_user(request)
    if user is None:
        return _landing(request)
    guild_ids = await session.current_guild_ids(request, discord_api.get_client())
    if guild_ids is None:
        return _landing(request, "Your sign-in has ended. Please sign in again.")
    servers = [
        {"id": guild_id, "name": name}
        for guild_id, name in await guilds.known_guilds(guild_ids)
    ]
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


async def guild(request, guild_id: int) -> HttpResponse:
    """One server: its modules and their state."""
    user = session.current_user(request)
    guild_ids = await session.current_guild_ids(request, discord_api.get_client())
    if user is None or guild_ids is None:
        return redirect("home")
    # A server the user may not manage looks exactly like one that does not exist.
    known = await guilds.known_guilds([guild_id]) if guild_id in guild_ids else []
    if not known:
        raise Http404

    states = await cog_settings.get_states(guild_id)
    modules = [
        {
            "key": info.key,
            "title": info.title,
            "description": info.description,
            "fixed": not info.toggleable,
            "on": states.get(info.key, True),
        }
        for info in registry.REGISTRY.values()
    ]
    return render(
        request,
        "web/guild.html",
        {
            "user": user,
            "guild": {"id": guild_id, "name": known[0][1]},
            "modules": modules,
        },
    )
