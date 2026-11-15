"""ASGI entry point of the web panel: ``uvicorn demolizzen.web.asgi:application``."""

# Standard Library
import os

# Django
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "demolizzen.web.settings")

application = get_asgi_application()
