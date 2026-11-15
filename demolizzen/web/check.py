"""Checks whether the panel is set up: ``python -m demolizzen.web.check``.

In the container::

    docker compose run --rm panel python -m demolizzen.web.check

Prints one line per check and ends with status 1 if something has to be fixed.
Secrets are never printed.
"""

# Standard Library
import os
import sys

# Django
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import Error as DatabaseError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

OK, WARN, FAIL = "OK", "WARN", "FAIL"

# What usually is the matter, by the database's error number.
_HINTS = {
    2002: "The server does not answer. Check DATABASE_HOST and DATABASE_PORT, the "
    "database's bind-address and the firewall.",
    2003: "The server does not answer. Check DATABASE_HOST and DATABASE_PORT, the "
    "database's bind-address and the firewall.",
    1045: "User or password is wrong, or the user is not allowed to connect from "
    "this address.",
    1044: "The user may not use this database. Check DATABASE_NAME and the user's grants.",
    1049: "There is no such database. Check DATABASE_NAME.",
    2026: "The encrypted connection failed. Check DATABASE_SSL_MODE and "
    "DATABASE_SSL_CA, and that the database offers TLS.",
}


def _settings_findings() -> list[tuple[str, str]]:
    findings = []

    try:
        secret_key = settings.SECRET_KEY or ""
    except ImproperlyConfigured:  # Django refuses to hand out an empty key
        secret_key = ""
    if len(secret_key) < 32:
        findings.append((FAIL, "SECRET_KEY is missing or shorter than 32 characters."))

    if settings.DISCORD_CLIENT_ID and settings.DISCORD_CLIENT_SECRET:
        findings.append((OK, "Sign-in with Discord is configured."))
    else:
        findings.append(
            (FAIL, "DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET are not both set.")
        )

    address = settings.WEB_BASE_URL or ""
    if address.startswith("https://") or (
        settings.DEBUG and address.startswith("http://")
    ):
        findings.append(
            (OK, f"Address {address}; redirect to register: {address}/callback")
        )
    else:
        findings.append((FAIL, "WEB_BASE_URL must be the panel's https:// address."))

    if not getattr(settings, "BOT_TOKEN", ""):
        findings.append(
            (
                WARN,
                "BOT_TOKEN is not set: channels and roles cannot be offered in "
                "the ticket and level settings.",
            )
        )
    return findings


def _pending_migrations() -> list[str]:
    """The names of migrations the code has but the database lacks."""
    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    return [f"{migration.app_label}.{migration.name}" for migration, _ in plan]


def _cipher() -> str | None:
    """The cipher of the database connection; None where that cannot be asked."""
    if connection.vendor != "mysql":
        return None
    with connection.cursor() as cursor:
        cursor.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
        row = cursor.fetchone()
    return row[1] if row else ""


def _encryption_finding(cipher: str | None) -> tuple[str, str] | None:
    if cipher is None:
        return None
    if cipher:
        return OK, f"Database connection is encrypted ({cipher})."
    return (
        WARN,
        "Database connection is not encrypted. Set DATABASE_SSL_MODE=REQUIRED "
        "unless the database runs on this machine.",
    )


def _database_findings() -> list[tuple[str, str]]:
    try:
        connection.ensure_connection()
    except DatabaseError as error:
        number = (
            error.args[0] if error.args and isinstance(error.args[0], int) else None
        )
        text = f"Database not reachable: {error}"
        if number in _HINTS:
            text += f"\n      {_HINTS[number]}"
        return [(FAIL, text)]

    findings = [(OK, "Database reachable.")]
    encryption = _encryption_finding(_cipher())
    if encryption is not None:
        findings.append(encryption)

    pending = _pending_migrations()
    if pending:
        findings.append(
            (
                FAIL,
                f"{len(pending)} database migrations are missing: {', '.join(pending)}"
                "\n      Run `python manage.py migrate` where the bot is installed.",
            )
        )
    else:
        findings.append((OK, "Database is up to date."))
    return findings


def main() -> int:
    """Print the findings; return 1 if one of them has to be fixed."""
    findings = _settings_findings() + _database_findings()
    for level, text in findings:
        print(f"{level:<5} {text}")
    return 1 if any(level == FAIL for level, _ in findings) else 0


if __name__ == "__main__":
    # Django
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "demolizzen.web.settings")
    django.setup()
    sys.exit(main())
