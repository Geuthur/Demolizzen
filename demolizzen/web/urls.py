"""URLs of the web panel."""

# Django
from django.urls import path

# Demolizzen
from demolizzen.web import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login", views.login, name="login"),
    path("callback", views.callback, name="callback"),
    path("logout", views.logout, name="logout"),
    path("guilds/<int:guild_id>/", views.guild, name="guild"),
    path(
        "guilds/<int:guild_id>/modules/<slug:key>",
        views.switch_module,
        name="switch_module",
    ),
    path("healthz", views.healthz, name="healthz"),
    path(
        "guilds/<int:guild_id>/settings/<slug:key>",
        views.module_settings,
        name="module_settings",
    ),
    path("panel.css", views.stylesheet, name="stylesheet"),
    path("exo2.woff2", views.font, name="font"),
]

handler404 = views.not_found
