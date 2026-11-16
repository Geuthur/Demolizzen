"""Keeps the database's tables in step with the code.

The bot applies pending Django migrations before it starts, so an update
needs no extra step. ``AUTO_MIGRATE=0`` in ``.env`` switches that off for
operators who run ``python manage.py migrate`` themselves.
"""

# Django
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

# The setting, see .env.example.
SETTING = "AUTO_MIGRATE"
_OFF = {"0", "false", "no", "off"}


def enabled(value: str | None) -> bool:
    """Whether migrations are applied at start: yes, unless switched off."""
    return (value or "").strip().lower() not in _OFF


def apply_pending() -> list[str]:
    """Apply the migrations the database is missing.

    Returns
    -------
    list[str]
        What was applied, as ``app.migration``; empty when the database was
        already up to date.
    """
    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    names = [f"{migration.app_label}.{migration.name}" for migration, _ in plan]
    if names:
        call_command("migrate", interactive=False, verbosity=0)
    return names
