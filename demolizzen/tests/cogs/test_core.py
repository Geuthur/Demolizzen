# Standard Library
from unittest.mock import MagicMock, patch

# Django
from django.test import SimpleTestCase

# Demolizzen
from demolizzen.cogs.core.core import Core
from demolizzen.core.bot import Demolizzen
from demolizzen.tests.helpers import make_ctx, make_guild, make_member


class CoreTest(SimpleTestCase):
    def test_auth_register_is_gone(self):
        with patch("discord.ext.tasks.Loop.start"):
            bot = Demolizzen()
            bot.preload_ext = ["core"]
            bot.load_preload_extensions()

        names = {command.name for command in bot.pending_application_commands}

        self.assertNotIn("auth", names)
        self.assertIn("bot", names)

    def test_unused_changelog_download_is_gone(self):
        self.assertFalse(hasattr(Core, "get_data"))

    async def test_uptime_does_not_log_guilds(self):
        bot = MagicMock()
        bot.uptime_str = "1 hour"
        bot.guilds = [make_guild(1)]
        bot.get_all_members.return_value = [make_member(1), make_member(2)]
        ctx = make_ctx(make_guild(1), make_member(240850566002114561))
        ctx.user.id = 240850566002114561

        await Core(bot).uptime.callback(Core(bot), ctx)

        bot.logger.error.assert_not_called()
        embed = ctx.respond.await_args.kwargs["embed"]
        self.assertEqual(embed.description, "1 hour")
        self.assertEqual(embed.fields[0].value, "Servers: 1 - Members: 2")
