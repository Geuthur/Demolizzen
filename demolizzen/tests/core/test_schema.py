# Standard Library
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# Django
from django.test import SimpleTestCase, TestCase

# Demolizzen
from demolizzen.core import schema
from demolizzen.core.bot import Demolizzen

ROOT = Path(schema.__file__).resolve().parents[2]
MODULE = "demolizzen.core.bot"


def pending(*names):
    """A migration plan as Django reports it: (migration, backwards)."""
    return [
        (SimpleNamespace(app_label="demolizzen", name=name), False) for name in names
    ]


class SettingTest(SimpleTestCase):
    def test_migrations_are_applied_unless_switched_off(self):
        for value in (None, "", "1", "true", "yes", "on", "anything"):
            with self.subTest(value=value):
                self.assertTrue(schema.enabled(value))

    def test_setting_switches_it_off(self):
        for value in ("0", "false", "False", " no ", "OFF"):
            with self.subTest(value=value):
                self.assertFalse(schema.enabled(value))

    def test_setting_is_documented(self):
        self.assertIn("AUTO_MIGRATE=", (ROOT / ".env.example").read_text())


class ApplyPendingTest(TestCase):
    def test_database_that_is_up_to_date_is_left_alone(self):
        # The test database has every migration applied.
        with patch.object(schema, "call_command") as migrate:
            applied = schema.apply_pending()

        self.assertEqual(applied, [])
        migrate.assert_not_called()

    def test_pending_migrations_are_applied_without_questions(self):
        plan = pending("0015_something", "0016_more")
        with (
            patch.object(schema.MigrationExecutor, "migration_plan", return_value=plan),
            patch.object(schema, "call_command") as migrate,
        ):
            applied = schema.apply_pending()

        self.assertEqual(applied, ["demolizzen.0015_something", "demolizzen.0016_more"])
        migrate.assert_called_once()
        self.assertEqual(migrate.call_args.args, ("migrate",))
        self.assertFalse(migrate.call_args.kwargs["interactive"])


class BotStartTest(SimpleTestCase):
    """However the bot is started, its tables match its code first."""

    def make_bot(self, auto_migrate=True) -> Demolizzen:
        bot = Demolizzen()
        bot.preload_ext = ["core"]
        bot.auto_migrate = auto_migrate
        return bot

    def run_bot(self, bot, apply):
        order: list[str] = []
        apply.side_effect = apply.side_effect or (
            lambda: order.append("migrate") or ["demolizzen.0015_something"]
        )
        with (
            patch("discord.ext.tasks.Loop.start"),
            patch.object(
                Demolizzen,
                "load_extension",
                side_effect=lambda name: order.append("modules"),
            ),
            patch(
                "discord.ext.commands.Bot.run",
                side_effect=lambda *a, **k: order.append("connect"),
            ),
            patch("builtins.print"),
        ):
            bot.run()
        return order

    def test_run_migrates_before_modules_load_and_before_connecting(self):
        with patch.object(schema, "apply_pending") as apply:
            order = self.run_bot(self.make_bot(), apply)

        self.assertEqual(order, ["migrate", "modules", "connect"])

    def test_bot_reads_the_setting(self):
        with patch.dict("os.environ", {"AUTO_MIGRATE": "1"}):
            self.assertTrue(Demolizzen().auto_migrate)
        with patch.dict("os.environ", {"AUTO_MIGRATE": "0"}):
            self.assertFalse(Demolizzen().auto_migrate)

    def test_switched_off_nothing_is_migrated(self):
        with patch.object(schema, "apply_pending") as apply:
            order = self.run_bot(self.make_bot(auto_migrate=False), apply)

        apply.assert_not_called()
        self.assertEqual(order, ["modules", "connect"])

    def test_failed_migration_stops_the_start(self):
        # A bot on half-changed tables does damage; better not to start.
        bot = self.make_bot()
        with (
            patch.object(schema, "apply_pending", side_effect=RuntimeError("boom")),
            patch.object(Demolizzen, "load_extension") as load,
            patch("discord.ext.commands.Bot.run") as connect,
            patch("builtins.print"),
            self.assertLogs(level="CRITICAL") as logs,
            self.assertRaises(RuntimeError),
        ):
            bot.run()

        load.assert_not_called()
        connect.assert_not_called()
        self.assertIn("migrat", " ".join(logs.output).lower())

    async def test_start_migrates_too_and_only_once(self):
        bot = self.make_bot()
        session = MagicMock()
        session.close = AsyncMock()
        with (
            patch.object(schema, "apply_pending", return_value=[]) as apply,
            patch("discord.ext.tasks.Loop.start"),
            patch(f"{MODULE}.aiohttp.ClientSession", return_value=session),
            patch(f"{MODULE}.OpenAPI", return_value=MagicMock()),
            patch("discord.ext.commands.Bot.start", new_callable=AsyncMock),
            patch("builtins.print"),
        ):
            await bot.start("tok")
            await bot.start("tok")
            await bot.close()

        apply.assert_called_once_with()

    def test_connection_used_for_migrating_is_given_back(self):
        # The bot's own work uses other connections; this one would sit idle.
        bot = self.make_bot()
        with (
            patch.object(schema, "apply_pending", return_value=[]),
            patch.object(schema, "connection") as connection,
            patch("discord.ext.tasks.Loop.start"),
            patch.object(Demolizzen, "load_extension"),
            patch("discord.ext.commands.Bot.run"),
            patch("builtins.print"),
        ):
            bot.run()

        connection.close.assert_called_once_with()

    def test_console_says_what_was_applied(self):
        bot = self.make_bot()
        with (
            patch.object(
                schema, "apply_pending", return_value=["demolizzen.0015_something"]
            ),
            patch("discord.ext.tasks.Loop.start"),
            patch.object(Demolizzen, "load_extension"),
            patch("discord.ext.commands.Bot.run"),
            patch("builtins.print") as printed,
        ):
            bot.run()

        text = " ".join(
            str(call.args[0]) for call in printed.call_args_list if call.args
        )
        self.assertIn("1 database migration", text)
        self.assertIn("0015_something", text)
