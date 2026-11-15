# Standard Library
from unittest.mock import AsyncMock, MagicMock

# Discord
import discord

# Django
from django.test import SimpleTestCase

# Demolizzen
from demolizzen.cogs.ticket._renamer import ChannelRenamer


class FakeTime:
    """A clock that only moves when someone sleeps."""

    def __init__(self):
        self.now = 1000.0
        self.sleeps = []
        self.on_sleep = None

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds
        if self.on_sleep is not None:
            callback, self.on_sleep = self.on_sleep, None
            callback()


def make_channel(name: str = "ticket-0001-max", channel_id: int = 100):
    channel = MagicMock()
    channel.id = channel_id
    channel.name = name

    async def edit(**kwargs):
        channel.name = kwargs["name"]

    channel.edit = AsyncMock(side_effect=edit)
    return channel


def names(channel) -> list[str]:
    return [call.kwargs["name"] for call in channel.edit.await_args_list]


class ChannelRenamerTest(SimpleTestCase):
    def setUp(self):
        self.time = FakeTime()
        self.renamer = ChannelRenamer(clock=self.time.clock, sleep=self.time.sleep)

    async def rename(self, channel, name):
        self.renamer.request(channel, name)
        await self.renamer.wait(channel.id)

    async def test_rename_happens_immediately(self):
        channel = make_channel()

        await self.rename(channel, "closed-0001-max")

        self.assertEqual(names(channel), ["closed-0001-max"])
        self.assertEqual(self.time.sleeps, [])

    async def test_same_name_is_not_sent(self):
        channel = make_channel()

        await self.rename(channel, "ticket-0001-max")

        channel.edit.assert_not_awaited()

    async def test_third_rename_within_window_waits(self):
        channel = make_channel()
        await self.rename(channel, "closed-0001-max")
        self.time.now += 100
        await self.rename(channel, "ticket-0001-max")
        self.time.now += 100

        await self.rename(channel, "closed-0001-max")

        self.assertEqual(self.time.sleeps, [400.0])
        self.assertEqual(
            names(channel), ["closed-0001-max", "ticket-0001-max", "closed-0001-max"]
        )

    async def test_latest_request_wins_while_waiting(self):
        channel = make_channel()
        await self.rename(channel, "closed-0001-max")
        await self.rename(channel, "ticket-0001-max")
        self.time.on_sleep = lambda: self.renamer.request(channel, "closed-0001-b")

        await self.rename(channel, "closed-0001-a")

        self.assertEqual(
            names(channel), ["closed-0001-max", "ticket-0001-max", "closed-0001-b"]
        )

    async def test_returning_to_the_current_name_while_waiting_sends_nothing(self):
        channel = make_channel()
        await self.rename(channel, "closed-0001-max")
        await self.rename(channel, "ticket-0001-max")
        self.time.on_sleep = lambda: self.renamer.request(channel, "ticket-0001-max")

        await self.rename(channel, "closed-0001-max")

        self.assertEqual(len(names(channel)), 2)

    async def test_window_expires(self):
        channel = make_channel()
        await self.rename(channel, "closed-0001-max")
        await self.rename(channel, "ticket-0001-max")
        self.time.now += 601

        await self.rename(channel, "closed-0001-max")

        self.assertEqual(self.time.sleeps, [])
        self.assertEqual(len(names(channel)), 3)

    async def test_channels_are_limited_separately(self):
        first, second = make_channel(channel_id=1), make_channel(channel_id=2)
        await self.rename(first, "closed-0001-max")
        await self.rename(first, "ticket-0001-max")

        await self.rename(second, "closed-0001-max")

        self.assertEqual(self.time.sleeps, [])

    async def test_http_error_is_logged_not_raised(self):
        channel = make_channel()
        response = MagicMock(status=403, reason="Forbidden")
        channel.edit = AsyncMock(side_effect=discord.Forbidden(response, "nope"))

        with self.assertLogs("demolizzen.cogs.ticket._renamer", level="WARNING"):
            await self.rename(channel, "closed-0001-max")

    async def test_cancel_all_stops_waiting_renames(self):
        channel = make_channel()
        renamer = ChannelRenamer(clock=self.time.clock, sleep=AsyncMock())
        renamer.request(channel, "closed-0001-max")

        renamer.cancel_all()
        await renamer.wait(channel.id)

        channel.edit.assert_not_awaited()
