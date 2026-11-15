# Standard Library
import asyncio
import subprocess
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# Discord
import discord

# Django
from django.test import SimpleTestCase

# Demolizzen
from demolizzen.cogs.owner.owner import Owner
from demolizzen.tests.helpers import make_ctx


class OwnerTest(SimpleTestCase):
    def setUp(self):
        self.bot = MagicMock()
        self.bot.change_presence = AsyncMock()
        self.cog = Owner(self.bot)
        # Owner commands are used in direct messages: there is no guild.
        self.ctx = make_ctx(None)
        self.ctx.me = MagicMock(spec=discord.ClientUser)

    def said(self) -> str:
        return self.ctx.respond.await_args.args[0]

    async def test_loading_modules_registers_their_commands_with_discord(self):
        self.bot.sync_commands = AsyncMock()
        actions = [
            (self.cog.load, self.bot.load_extension),
            (self.cog.unload, self.bot.unload_extension),
            (self.cog.reload, self.bot.reload_extension),
        ]
        for command, action in actions:
            with self.subTest(command=command.name):
                self.bot.sync_commands.reset_mock()

                await command.callback(self.cog, self.ctx, "games")

                action.assert_called_once_with("demolizzen.cogs.games")
                self.bot.sync_commands.assert_awaited_once_with()

    async def test_discord_is_answered_before_the_registration_starts(self):
        # Every server is registered on its own; that takes longer than the
        # three seconds Discord waits for an answer.
        for command in (self.cog.load, self.cog.unload, self.cog.reload):
            with self.subTest(command=command.name):
                order: list[str] = []
                self.ctx.defer = AsyncMock(
                    side_effect=lambda **_: order.append("defer")
                )
                self.bot.sync_commands = AsyncMock(
                    side_effect=lambda: order.append("register")
                )

                await command.callback(self.cog, self.ctx, "games")

                self.assertEqual(order, ["defer", "register"])

    async def test_failed_load_registers_nothing(self):
        self.bot.sync_commands = AsyncMock()
        self.bot.load_extension.side_effect = RuntimeError("broken")

        await self.cog.load.callback(self.cog, self.ctx, "games")

        self.bot.sync_commands.assert_not_awaited()
        embed = self.ctx.respond.await_args.kwargs["embed"]
        self.assertEqual(embed.description, "Could not load the `games` cog.")

    async def test_force_deposits_update_runs_the_interest(self):
        bank = SimpleNamespace(run_interest=AsyncMock(return_value=3))
        self.bot.get_cog.return_value = bank

        await self.cog.trigger_deposit_update.callback(self.cog, self.ctx)

        self.bot.get_cog.assert_called_once_with("Bank")
        bank.run_interest.assert_awaited_once_with()
        self.assertEqual(self.said(), "Interest paid in 3 server(s).")

    async def test_force_deposits_update_without_bank_module(self):
        self.bot.get_cog.return_value = None

        await self.cog.trigger_deposit_update.callback(self.cog, self.ctx)

        self.assertEqual(self.said(), "The bank module is not loaded.")

    def test_force_ship_update_is_gone(self):
        names = [command.name for command in Owner.owner.subcommands]

        self.assertNotIn("force-ship-update", names)
        self.assertIn("force-deposits-update", names)

    async def test_migrate_does_not_block_the_event_loop(self):
        ticks = 0

        async def ticker():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.01)
                ticks += 1

        def slow_migrate(*args, **kwargs):
            time.sleep(0.2)
            return SimpleNamespace(stdout="No migrations to apply.", stderr="")

        task = asyncio.ensure_future(ticker())
        with patch("demolizzen.cogs.owner.owner.subprocess.run", slow_migrate):
            await self.cog.trigger_migrations.callback(self.cog, self.ctx)
        task.cancel()

        self.assertGreater(ticks, 5)
        self.assertEqual(self.said(), "```\nNo migrations to apply.\n```")

    async def test_migrate_reports_a_failure(self):
        def failing(*args, **kwargs):
            raise subprocess.CalledProcessError(1, "migrate")

        with patch("demolizzen.cogs.owner.owner.subprocess.run", failing):
            await self.cog.trigger_migrations.callback(self.cog, self.ctx)

        self.assertEqual(self.said(), "Something went wrong while running migrations")

    async def test_status_keeps_the_activity_in_direct_messages(self):
        game = discord.Game("EVE Online")
        self.bot.guilds = [SimpleNamespace(me=SimpleNamespace(activity=game))]

        await self.cog.status.callback(self.cog, self.ctx, status="idle")

        self.bot.change_presence.assert_awaited_once_with(
            status=discord.Status.idle, activity=game
        )
        self.assertEqual(self.said(), "Status changed to `idle`.")

    async def test_status_without_any_guild(self):
        self.bot.guilds = []

        await self.cog.status.callback(self.cog, self.ctx, status="dnd")

        self.bot.change_presence.assert_awaited_once_with(
            status=discord.Status.dnd, activity=None
        )

    async def test_unknown_status_is_refused(self):
        await self.cog.status.callback(self.cog, self.ctx, status="asleep")

        self.bot.change_presence.assert_not_awaited()
        self.assertEqual(
            self.said(), "Only `online`, `idle` or `dnd` statuses are available."
        )
