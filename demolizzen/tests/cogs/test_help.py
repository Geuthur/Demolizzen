# Standard Library
from unittest.mock import MagicMock

# Django
from django.test import TestCase

# Demolizzen
from demolizzen.cogs.commands.commands import Commands
from demolizzen.core.cog import BaseCog
from demolizzen.services import cog_settings, guilds
from demolizzen.tests.helpers import make_ctx, make_guild


class FakeGames(BaseCog):
    key = "games"
    alias = "games"

    def get_commands(self):
        return [MagicMock(name="play")]


class FakeTicket(BaseCog):
    key = "ticket"
    alias = "ticket"

    def get_commands(self):
        return [MagicMock(name="open")]


class HelpTest(TestCase):
    def setUp(self):
        cog_settings.invalidate()

    async def help_labels(self) -> list[str]:
        bot = MagicMock()
        bot.cogs = {"Games": FakeGames(bot), "Ticket": FakeTicket(bot)}
        cog = Commands(bot)
        ctx = make_ctx(guild=make_guild(1))
        ctx.bot = bot

        await cog.help.callback(cog, ctx)

        view = ctx.respond.await_args.kwargs["view"]
        return [option.label for option in view.children[0].options]

    async def test_help_lists_enabled_modules(self):
        self.assertEqual(await self.help_labels(), ["Games", "Ticket"])

    async def test_help_hides_modules_disabled_on_this_server(self):
        await guilds.ensure_guild(1, "Alpha")
        await cog_settings.set_enabled(1, "games", False)

        self.assertEqual(await self.help_labels(), ["Ticket"])
