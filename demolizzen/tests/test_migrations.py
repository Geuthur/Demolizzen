# Standard Library
from io import StringIO
from unittest.mock import patch

# Django
from django.apps import apps
from django.core.management import call_command
from django.test import TestCase

# Demolizzen
from demolizzen.core.bot import Demolizzen


class SchemaTest(TestCase):
    def test_no_pending_model_changes(self):
        out = StringIO()

        call_command(
            "makemigrations", "demolizzen", check=True, dry_run=True, stdout=out
        )

        self.assertIn("No changes detected", out.getvalue())

    def test_ticket_task_model_is_gone(self):
        with self.assertRaises(LookupError):
            apps.get_model("demolizzen", "GuildTicketTask")


class TicketExtensionTest(TestCase):
    def setUp(self):
        with patch("discord.ext.tasks.Loop.start"):
            self.bot = Demolizzen()
            self.results = self.bot.load_preload_extensions()

    def test_ticket_extension_loads(self):
        self.assertIsNone(self.results["ticket"])

    def test_only_one_ticket_cog_is_loaded(self):
        self.assertIn("TicketSystem", self.bot.cogs)
        self.assertNotIn("TicketSystemConfig", self.bot.cogs)

    def test_no_ticket_config_command(self):
        # Commands are pending until the bot syncs them with Discord.
        names = {command.name for command in self.bot.pending_application_commands}

        self.assertIn("ticket", names)
        self.assertNotIn("ticket_config", names)
