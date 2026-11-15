# Minimal Django settings for ORM-only usage
# Standard Library
import os

# Demolizzen
from demolizzen import config

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SECRET_KEY = config.SECRET_KEY
DEBUG = True
ALLOWED_HOSTS = ["testserver"]

INSTALLED_APPS = [
    "esi",
    "demolizzen",
]


def use_mysql(value: str | None) -> bool:
    """Return True when the USE_MYSQL environment value asks for MySQL."""
    return (value or "").strip().lower() in ("1", "true", "yes")


# Tests run on in-memory SQLite by default. Set USE_MYSQL=1 (tox and CI do) to run against MySQL.
if use_mysql(os.environ.get("USE_MYSQL")):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": "temp_demolizzen",
            "USER": "root",
            "PASSWORD": "temp_password_tox",
            "HOST": "127.0.0.1",
            "PORT": "3306",
            "OPTIONS": {
                "charset": "utf8mb4",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

USE_TZ = True

# Custom User Model
AUTH_USER_MODEL = "demolizzen.UserProfile"
ESI_USER_CONTACT_EMAIL = config.ESI_USER_CONTACT_EMAIL

# Demolizzen
# The web panel shares these settings; its tests run with the rest of the suite.
from demolizzen.web.base_settings import *  # noqa: E402, F403  pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position

SECRET_KEY = SECRET_KEY or "only-for-tests"
DISCORD_CLIENT_ID = "123"
DISCORD_CLIENT_SECRET = "secret"
WEB_BASE_URL = "https://panel.example"
