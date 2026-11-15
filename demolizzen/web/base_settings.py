"""Web panel settings shared by the deployed panel and the tests.

Everything but the database: that comes from the settings module importing this.
"""

# Standard Library
from pathlib import Path
from urllib.parse import urlsplit

# Demolizzen
from demolizzen import config

WEB_DIR = Path(__file__).resolve().parent


def allowed_hosts(base_url: str | None, extra: str | None) -> list[str]:
    """Host names the panel answers to: the one of its address plus a
    comma-separated list of further names."""
    hosts = []
    base_host = urlsplit(base_url or "").hostname
    if base_host:
        hosts.append(base_host)
    hosts += [name.strip() for name in (extra or "").split(",") if name.strip()]
    return hosts


# The Discord application members sign in with.
DISCORD_CLIENT_ID = config.DISCORD_CLIENT_ID or ""
DISCORD_CLIENT_SECRET = config.DISCORD_CLIENT_SECRET or ""
# The bot's token: the panel asks Discord for a server's channels and roles with it.
BOT_TOKEN = config.BOT_TOKEN or ""
# Where browsers reach the panel, e.g. https://panel.example.com
WEB_BASE_URL = (config.WEB_BASE_URL or "").rstrip("/")

ROOT_URLCONF = "demolizzen.web.urls"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "demolizzen.web.middleware.ContentSecurityPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [WEB_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": ["django.template.context_processors.request"],
        },
    },
]

# The session is a cookie: no table and no account in the database.
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
# Signed and encrypted: the cookie holds the user's Discord token.
SESSION_SERIALIZER = "demolizzen.web.crypto.EncryptedJSONSerializer"
SESSION_COOKIE_NAME = "panel_session"
SESSION_COOKIE_AGE = 7 * 24 * 3600
SESSION_COOKIE_HTTPONLY = True
# Lax: the cookie must come along when Discord sends the browser back.
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "demolizzen.web.views.csrf_failure"

X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
# The panel runs behind a proxy that ends TLS and says so in this header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
