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
    "esi",
    "demolizzen",
]

DATABASES = {
    "default": {
        # "ENGINE": "django.db.backends.mysql",
        "ENGINE": "demolizzen",
        "NAME": config.DATABASE_NAME,
        "USER": config.DATABASE_USER,
        "PASSWORD": config.DATABASE_PASSWORD,
        "HOST": config.DATABASE_HOST,
        "PORT": config.DATABASE_PORT,
        "CONN_HEALTH_CHECKS": True,
        "CONN_MAX_AGE": 300,  # 5 Minutes
    }
}

USE_TZ = True

# Custom User Model
AUTH_USER_MODEL = "demolizzen.UserProfile"
ESI_USER_CONTACT_EMAIL = config.ESI_USER_CONTACT_EMAIL
