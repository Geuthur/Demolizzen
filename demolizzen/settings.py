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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": config.DATABASE_NAME,
        "USER": config.DATABASE_USER,
        "PASSWORD": config.DATABASE_PASSWORD,
        "HOST": config.DATABASE_HOST,
        "PORT": config.DATABASE_PORT,
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    }
}

USE_TZ = True
