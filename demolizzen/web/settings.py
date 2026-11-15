"""Settings of the deployed web panel: the bot's database plus the web parts."""

# pylint: disable=wildcard-import,unused-wildcard-import
# Demolizzen
from demolizzen import config
from demolizzen.settings import *  # noqa: F401,F403
from demolizzen.web.base_settings import *  # noqa: F401,F403
from demolizzen.web.base_settings import WEB_BASE_URL, allowed_hosts

DEBUG = (config.WEB_DEBUG or "").strip().lower() in ("1", "true", "yes")

ALLOWED_HOSTS = allowed_hosts(WEB_BASE_URL, config.WEB_ALLOWED_HOSTS)
CSRF_TRUSTED_ORIGINS = [WEB_BASE_URL] if WEB_BASE_URL else []

# Cookies travel over HTTPS only, except while developing locally.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
