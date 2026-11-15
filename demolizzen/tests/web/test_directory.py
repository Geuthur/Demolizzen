# Standard Library
from unittest.mock import patch

# Third Party
import aiohttp

# Django
from django.test import SimpleTestCase, override_settings

# Demolizzen
from demolizzen.tests.web.fakes import FakeBot, channel, role
from demolizzen.tests.web.test_discord_api import Answer, FakeSession
from demolizzen.web import directory, discord_api
from demolizzen.web.directory import Choice
from demolizzen.web.discord_api import (
    BotTokenMissing,
    DiscordBotClient,
    DiscordError,
    DiscordUnauthorized,
)


class BotClientTest(SimpleTestCase):
    def make(self, answer) -> DiscordBotClient:
        self.http = FakeSession(answer)
        return DiscordBotClient("bot-token-xyz", session_factory=self.http)

    async def test_bot_requests_carry_the_bot_token(self):
        client = self.make(Answer(data=[{"id": "5"}]))

        self.assertEqual(await client.fetch_channels(1), [{"id": "5"}])
        self.assertEqual(await client.fetch_roles(1), [{"id": "5"}])

        urls = [url for _, url, _ in self.http.requests]
        self.assertEqual(
            urls,
            [
                "https://discord.com/api/v10/guilds/1/channels",
                "https://discord.com/api/v10/guilds/1/roles",
            ],
        )
        for method, _, kwargs in self.http.requests:
            self.assertEqual(method, "GET")
            self.assertEqual(kwargs["headers"]["Authorization"], "Bot bot-token-xyz")
        self.assertEqual(self.http.session_options["timeout"].total, 10)

    async def test_bot_request_failures_are_discord_errors(self):
        answers = {
            "wrong token": Answer(status=401),
            "bot not in the server": Answer(status=403),
            "unknown server": Answer(status=404),
            "rate limited": Answer(status=429),
            "server error": Answer(status=500),
            "timeout": Answer(error=TimeoutError()),
            "connection": Answer(error=aiohttp.ClientConnectionError("down")),
            "not a list": Answer(data={"message": "x"}),
            "broken json": Answer(broken=True),
        }
        for name, answer in answers.items():
            with self.subTest(case=name):
                with self.assertRaises(DiscordError) as raised:
                    await self.make(answer).fetch_roles(1)
                # The token must never end up in an error text or a log line.
                self.assertNotIn("bot-token-xyz", str(raised.exception))
                # A problem with the bot's token must not sign visitors out.
                self.assertNotIsInstance(raised.exception, DiscordUnauthorized)

    def test_missing_token_is_reported(self):
        for token in ("", None):
            with self.subTest(token=token), override_settings(BOT_TOKEN=token):
                with self.assertRaises(BotTokenMissing):
                    discord_api.get_bot_client()

        with override_settings(BOT_TOKEN="abc"):
            self.assertIsInstance(discord_api.get_bot_client(), DiscordBotClient)

    def test_missing_token_is_a_discord_error(self):
        self.assertTrue(issubclass(BotTokenMissing, DiscordError))


class DirectoryTest(SimpleTestCase):
    def setUp(self):
        directory.clear()
        self.bot = FakeBot()
        patcher = patch(
            "demolizzen.web.discord_api.get_bot_client", return_value=self.bot
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.now = 5000.0
        clock = patch("demolizzen.web.directory._now", side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)

    async def test_channels_are_split_and_sorted(self):
        self.bot.channels[1] = [
            channel(12, "general", position=1, parent=20),
            channel(20, "Lobby", kind=4, position=0),
            channel(11, "rules", position=0, parent=20),
            channel(30, "Voice", kind=2),
            channel(21, "Tickets", kind=4, position=1),
            channel(13, "announcements", kind=5),
            channel(14, "logs", position=0, parent=21),
            channel(15, "loose", position=0),
        ]

        found = await directory.load(1)

        self.assertEqual(found.categories, [Choice(20, "Lobby"), Choice(21, "Tickets")])
        self.assertEqual(
            found.text_channels,
            [
                Choice(15, "#loose"),
                Choice(11, "#rules (Lobby)"),
                Choice(12, "#general (Lobby)"),
                Choice(14, "#logs (Tickets)"),
            ],
        )

    async def test_everyone_role_is_not_offered(self):
        self.bot.roles[1] = [
            role(1, "@everyone", position=0),
            role(51, "Member", position=1),
            role(52, "Admin", position=5),
            role(53, "Moderator", position=3),
        ]

        found = await directory.load(1)

        self.assertEqual(
            found.roles,
            [Choice(52, "Admin"), Choice(53, "Moderator"), Choice(51, "Member")],
        )

    async def test_unreadable_entries_are_skipped(self):
        self.bot.channels[1] = [
            channel(10, "ok"),
            {"name": "no id", "type": 0},
            {"id": "abc", "name": "bad id", "type": 0},
            {"id": "11", "type": 0},
            "garbage",
            None,
        ]
        self.bot.roles[1] = [role(50, "Staff"), {"id": "x"}, 7]

        found = await directory.load(1)

        self.assertEqual(found.text_channels, [Choice(10, "#ok")])
        self.assertEqual(found.roles, [Choice(50, "Staff")])

    async def test_directory_is_cached_per_server_for_a_minute(self):
        self.bot.channels[1] = [channel(10, "one")]
        self.bot.channels[2] = [channel(20, "two")]

        first = await directory.load(1)
        again = await directory.load(1)
        other = await directory.load(2)

        self.assertIs(first, again)
        self.assertEqual(other.text_channels, [Choice(20, "#two")])
        self.assertEqual(self.bot.calls.count(("channels", 1)), 1)

        self.now += 61
        self.bot.channels[1] = [channel(10, "renamed")]
        self.assertEqual(
            (await directory.load(1)).text_channels, [Choice(10, "#renamed")]
        )
        self.assertEqual(directory.CACHE_SECONDS, 60)

    async def test_failures_are_not_cached(self):
        self.bot.error = DiscordError("down")
        with self.assertRaises(DiscordError):
            await directory.load(1)

        self.bot.error = None
        self.bot.channels[1] = [channel(10, "back")]

        self.assertEqual((await directory.load(1)).text_channels, [Choice(10, "#back")])

    async def test_missing_token_is_passed_on(self):
        with patch(
            "demolizzen.web.discord_api.get_bot_client", side_effect=BotTokenMissing()
        ):
            with self.assertRaises(BotTokenMissing):
                await directory.load(1)
