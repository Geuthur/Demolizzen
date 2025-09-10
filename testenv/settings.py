# Minimal Django settings for ORM-only usage
# Standard Library
import os

# Demolizzen
from demolizzen import config

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SECRET_KEY = config.SECRET_KEY
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "demolizzen",
]

# Use the USE_MYSQL environment variable to select the database backend (MySQL or Memcached).
# NOTE: On Windows, set this variable in the system/user environment variables.
if os.environ.get("USE_MYSQL", True) is True:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": "test_demolizzen",
            "USER": "root",
            "PASSWORD": "test_password_tox",
            "HOST": "localhost",
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
