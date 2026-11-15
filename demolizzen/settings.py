# Minimal Django settings for ORM-only usage
# Standard Library
import os

# Django
from django.core.exceptions import ImproperlyConfigured

# Demolizzen
from demolizzen import config

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SECRET_KEY = config.SECRET_KEY
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "esi",
    "demolizzen",
]

SSL_MODES = ("DISABLED", "PREFERRED", "REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY")


def database_options(ssl_mode: str | None, ssl_ca: str | None) -> dict:
    """Driver options that encrypt the database connection.

    ``REQUIRED`` refuses a connection that is not encrypted; ``VERIFY_CA`` and
    ``VERIFY_IDENTITY`` also check the server's certificate. A certificate
    authority file alone means ``VERIFY_CA``. An unknown mode stops the start:
    running unencrypted by a typing mistake would go unnoticed.
    """
    mode = (ssl_mode or "").strip().upper()
    ca_file = (ssl_ca or "").strip()
    options = {}
    if ca_file:
        options["ssl"] = {"ca": ca_file}
        mode = mode or "VERIFY_CA"
    if mode:
        if mode not in SSL_MODES:
            raise ImproperlyConfigured(
                f"DATABASE_SSL_MODE must be one of {', '.join(SSL_MODES)}, not {mode!r}."
            )
        options["ssl_mode"] = mode
    return options


DATABASES = {
    "default": {
        # "ENGINE": "django.db.backends.mysql",
        "ENGINE": "demolizzen",
        "NAME": config.DATABASE_NAME,
        "USER": config.DATABASE_USER,
        "PASSWORD": config.DATABASE_PASSWORD,
        "HOST": config.DATABASE_HOST,
        "PORT": config.DATABASE_PORT,
        "OPTIONS": database_options(config.DATABASE_SSL_MODE, config.DATABASE_SSL_CA),
        "CONN_HEALTH_CHECKS": True,
        "CONN_MAX_AGE": 300,  # 5 Minutes
    }
}

USE_TZ = True
TIME_ZONE = "Europe/Berlin"

# Custom User Model
AUTH_USER_MODEL = "demolizzen.UserProfile"
ESI_USER_CONTACT_EMAIL = config.ESI_USER_CONTACT_EMAIL
