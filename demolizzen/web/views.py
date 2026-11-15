"""Pages of the web panel."""

# Standard Library
import secrets

# Django
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

# Demolizzen
from demolizzen.web import discord_api
from demolizzen.web.base_settings import WEB_DIR

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


def not_found(
    request, exception=None
) -> HttpResponse:  # pylint: disable=unused-argument
    return message(request, "Not found", "This page does not exist.", status=404)


def home(request) -> HttpResponse:
    """The start page: the offer to sign in."""
    return render(request, "web/landing.html")


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
