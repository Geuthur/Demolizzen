# Standard Library
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Discord
from discord.ext import commands

# Django
from django.test import SimpleTestCase, TestCase

# Demolizzen
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog, guild_listener, resolve_guild_id
from demolizzen.core.errors import CogDisabled
from demolizzen.services import cog_settings, guilds
from demolizzen.tests.helpers import make_ctx, make_guild, make_member


class Dummy(BaseCog):
    key = "games"

    def __init__(self, bot):
        super().__init__(bot)
        self.calls = []

    @guild_listener()
    async def on_message(self, message):
        self.calls.append(message)

    @guild_listener("on_guild_join")
    async def joined(self, guild):
        self.calls.append(guild)


class Fixed(BaseCog):
    key = "core"


def make_message(guild):
    return SimpleNamespace(guild=guild, content="hi")


class CogCheckTest(TestCase):
    def setUp(self):
        cog_settings.invalidate()

    async def test_check_passes_when_enabled(self):
        self.assertTrue(
            await Dummy(MagicMock()).cog_check(make_ctx(guild=make_guild(1)))
        )

    async def test_check_raises_when_disabled(self):
        await guilds.ensure_guild(1, "Alpha")
        await cog_settings.set_enabled(1, "games", False)

        with self.assertRaisesMessage(
            CogDisabled, "This module is disabled on this server."
        ):
            await Dummy(MagicMock()).cog_check(make_ctx(guild=make_guild(1)))

    async def test_check_passes_in_dm(self):
        await guilds.ensure_guild(1, "Alpha")
        await cog_settings.set_enabled(1, "games", False)

        self.assertTrue(await Dummy(MagicMock()).cog_check(make_ctx(guild=None)))

    async def test_fixed_cog_always_passes(self):
        self.assertTrue(
            await Fixed(MagicMock()).cog_check(make_ctx(guild=make_guild(1)))
        )

    async def test_is_enabled_without_guild(self):
        self.assertTrue(await Dummy(MagicMock()).is_enabled(None))


class GuildListenerTest(TestCase):
    def setUp(self):
        cog_settings.invalidate()

    async def test_listener_runs_when_enabled(self):
        cog = Dummy(MagicMock())
        message = make_message(make_guild(1))

        await cog.on_message(message)

        self.assertEqual(cog.calls, [message])

    async def test_listener_skipped_when_disabled(self):
        await guilds.ensure_guild(1, "Alpha")
        await cog_settings.set_enabled(1, "games", False)
        cog = Dummy(MagicMock())

        await cog.on_message(make_message(make_guild(1)))

        self.assertEqual(cog.calls, [])

    async def test_listener_runs_without_guild(self):
        await guilds.ensure_guild(1, "Alpha")
        await cog_settings.set_enabled(1, "games", False)
        cog = Dummy(MagicMock())

        await cog.on_message(make_message(None))

        self.assertEqual(len(cog.calls), 1)

    async def test_listener_receiving_guild_directly(self):
        await guilds.ensure_guild(1, "Alpha")
        await cog_settings.set_enabled(1, "games", False)
        cog = Dummy(MagicMock())

        await cog.joined(make_guild(1))
        await cog.joined(make_guild(2))

        self.assertEqual([guild.id for guild in cog.calls], [2])


class BaseCogDefinitionTest(SimpleTestCase):
    def test_listener_is_registered(self):
        self.assertIn(("on_message", "on_message"), Dummy.__cog_listeners__)
        self.assertIn(("on_guild_join", "joined"), Dummy.__cog_listeners__)

    def test_cog_disabled_is_shown_to_user(self):
        # The bot's error handler only answers ext.commands.CheckFailure.
        self.assertTrue(issubclass(CogDisabled, commands.CheckFailure))
        self.assertEqual(CogDisabled("games").key, "games")

    def test_missing_key_raises(self):
        with self.assertRaises(TypeError):

            class NoKey(BaseCog):  # pylint: disable=unused-variable
                pass

    def test_unknown_key_raises(self):
        with self.assertRaises(TypeError):

            class BadKey(BaseCog):  # pylint: disable=unused-variable
                key = "nope"

    def test_resolve_guild_id(self):
        guild = make_guild(7)
        self.assertEqual(resolve_guild_id((guild,)), 7)
        self.assertEqual(resolve_guild_id((make_member(1, guild=guild),)), 7)
        self.assertEqual(resolve_guild_id((make_message(guild),)), 7)
        self.assertIsNone(resolve_guild_id((make_message(None),)))
        self.assertEqual(resolve_guild_id((SimpleNamespace(guild_id=9),)), 9)
        self.assertIsNone(resolve_guild_id(()))
        self.assertIsNone(resolve_guild_id((object(),)))


class LoadedCogsTest(TestCase):
    def setUp(self):
        cog_settings.invalidate()
        with patch("discord.ext.tasks.Loop.start"):
            self.bot = Demolizzen()
            self.results = self.bot.load_preload_extensions()

    def test_every_extension_loads(self):
        self.assertEqual({k: v for k, v in self.results.items() if v}, {})

    def test_every_loaded_cog_uses_basecog(self):
        self.assertTrue(self.bot.cogs)
        for cog in self.bot.cogs.values():
            self.assertIsInstance(cog, BaseCog, cog.qualified_name)
            self.assertEqual(cog.key, cog.__module__.split(".")[2])

    async def test_pycord_runs_the_switch_for_slash_subcommands(self):
        await guilds.ensure_guild(1, "Alpha")
        await cog_settings.set_enabled(1, "ticket", False)
        command = next(
            cmd
            for cmd in self.bot.get_cog("TicketSystem").walk_commands()
            if cmd.name == "open"
        )
        ctx = make_ctx(guild=make_guild(1))
        ctx.bot = self.bot

        with self.assertRaises(CogDisabled):
            await command.can_run(ctx)
