# Standard Library
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

# Discord
import discord

# Django
from django.test import SimpleTestCase

# Demolizzen
from demolizzen.cogs.admin.admin import Admin
from demolizzen.tests.helpers import make_ctx, make_guild


def http_error(cls=discord.HTTPException, status=400, code=0):
    return cls(MagicMock(status=status, reason="nope"), {"code": code, "message": "x"})


class ClearTest(SimpleTestCase):
    def setUp(self):
        self.cog = Admin(MagicMock())
        self.ctx = make_ctx(make_guild())
        self.channel = MagicMock(spec=discord.TextChannel)
        self.channel.delete_messages = AsyncMock()
        self.history = MagicMock()
        self.history.flatten = AsyncMock(return_value=[])
        self.channel.history.return_value = self.history
        self.ctx.channel = self.channel

    def found(self, count: int) -> list:
        messages = [MagicMock(spec=discord.Message) for _ in range(count)]
        self.history.flatten.return_value = messages
        return messages

    async def clear(self, limit: int = 5) -> str:
        await self.cog.clear.callback(self.cog, self.ctx, limit)
        self.ctx.respond.assert_awaited_once()
        call = self.ctx.respond.await_args
        self.assertTrue(call.kwargs["ephemeral"])
        return call.kwargs["embed"].description

    async def test_clear_deletes_recent_messages_and_reports_the_count(self):
        messages = self.found(3)

        self.assertEqual(await self.clear(), "✅ Deleted 3 message(s).")

        self.ctx.defer.assert_awaited_once_with(ephemeral=True)
        self.channel.delete_messages.assert_awaited_once_with(messages)

    async def test_clear_without_messages_says_so(self):
        self.assertEqual(
            await self.clear(), "❌ No messages from the last 14 days to delete."
        )
        self.channel.delete_messages.assert_not_awaited()

    async def test_clear_answers_when_reading_is_forbidden(self):
        self.history.flatten.side_effect = http_error(discord.Forbidden, 403, 50001)

        self.assertEqual(await self.clear(), "❌ I have no permission to do that...")

    async def test_clear_answers_when_reading_fails(self):
        self.history.flatten.side_effect = http_error(status=500)

        with self.assertLogs("demolizzen.cogs.admin.admin", "ERROR"):
            self.assertEqual(await self.clear(), "❌ Something went wrong try later.")

    async def test_clear_answers_when_deleting_fails(self):
        cases = [
            (
                http_error(discord.Forbidden, 403, 50013),
                "❌ I have no permission to do that...",
            ),
            (
                http_error(code=50034),
                "❌ You can only bulk delete messages that are under 14 days old.",
            ),
        ]
        for error, expected in cases:
            with self.subTest(expected=expected):
                self.ctx.respond.reset_mock()
                self.found(2)
                self.channel.delete_messages.side_effect = error

                self.assertEqual(await self.clear(), expected)

    async def test_clear_answers_when_deleting_fails_unexpectedly(self):
        self.found(2)
        self.channel.delete_messages.side_effect = http_error(status=500)

        with self.assertLogs("demolizzen.cogs.admin.admin", "ERROR"):
            self.assertEqual(await self.clear(), "❌ Something went wrong try later.")

    async def test_clear_only_looks_at_the_last_14_days(self):
        await self.clear(limit=7)

        call = self.channel.history.call_args.kwargs
        self.assertEqual(call["limit"], 7)
        self.assertFalse(call["oldest_first"])
        age = discord.utils.utcnow() - call["after"]
        self.assertLess(abs(age - timedelta(days=14)), timedelta(seconds=5))

    async def test_clear_limit_is_between_1_and_100(self):
        for limit in (0, -3, 101):
            with self.subTest(limit=limit):
                self.ctx.respond.reset_mock()

                self.assertEqual(
                    await self.clear(limit),
                    "❌ Between 1 and 100 messages can be deleted at a time.",
                )
        self.channel.history.assert_not_called()

        option = next(o for o in Admin.clear.options if o.name == "limit")
        self.assertEqual((option.min_value, option.max_value), (1, 100))
