# Standard Library
from unittest.mock import AsyncMock, MagicMock, patch

# Discord
import discord

# Django
from django.db import OperationalError
from django.test import TestCase

# Demolizzen
from demolizzen.cogs.general.general import General


class StatusDisplayTest(TestCase):
    def setUp(self):
        self.bot = MagicMock()
        self.bot.guilds = [object(), object()]
        self.bot.change_presence = AsyncMock()
        with patch("discord.ext.tasks.Loop.start"):
            self.cog = General(self.bot)

    def shown(self):
        call = self.bot.change_presence.await_args.kwargs
        return call["status"], call["activity"].state, call["activity"].name

    async def test_status_is_green_when_the_database_answers(self):
        await self.cog.status_checker()

        self.assertEqual(
            self.shown(),
            (discord.Status.online, "Status: 🟢 No Issues", "2 Servers"),
        )

    async def test_status_turns_red_on_database_failure(self):
        self.cog.db_health_check = AsyncMock(return_value=False)

        await self.cog.status_checker()

        self.assertEqual(
            self.shown(),
            (discord.Status.dnd, "Status: 🔴 Database Issues", "2 Servers"),
        )
        self.bot.change_presence.assert_awaited_once()

    async def test_status_recovers_when_the_database_is_back(self):
        self.cog.db_health_check = AsyncMock(side_effect=[False, True])

        await self.cog.status_checker()
        await self.cog.status_checker()

        self.assertEqual(self.shown()[0], discord.Status.online)
        self.assertTrue(self.cog.is_okay)

    async def test_health_check_reports_a_broken_connection(self):
        self.assertTrue(await self.cog.db_health_check())

        with patch("demolizzen.cogs.general.general.connection") as connection:
            connection.cursor.side_effect = OperationalError("gone away")

            self.assertFalse(await self.cog.db_health_check())
