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
    path("healthz", views.healthz, name="healthz"),
    path("panel.css", views.stylesheet, name="stylesheet"),
]

handler404 = views.not_found
