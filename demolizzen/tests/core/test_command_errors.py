# Standard Library
from unittest.mock import MagicMock, patch

# Discord
import discord
from discord.ext import commands

# Django
from django.test import SimpleTestCase

# Demolizzen
from demolizzen.cogs.token.token import Token
from demolizzen.core.bot import Demolizzen
from demolizzen.tests.helpers import make_ctx, make_guild


def all_commands(found):
    """Yield commands and, for groups, everything below them."""
    for command in found:
        yield command
        if isinstance(command, discord.SlashCommandGroup):
            yield from all_commands(command.subcommands)


class CommandErrorTest(SimpleTestCase):
    """The bot answers command errors itself. A command with a handler of its
    own would answer the same error a second time."""

    def test_no_loaded_command_answers_errors_itself(self):
        with patch("discord.ext.tasks.Loop.start"):
            bot = Demolizzen()
            bot.load_preload_extensions()

        own_handlers = [
            command.qualified_name
            for command in all_commands(bot.pending_application_commands)
            if command.has_error_handler()
        ]

        self.assertEqual(own_handlers, [])

    def test_token_commands_do_not_answer_errors_themselves(self):
        own_handlers = [
            command.qualified_name
            for command in all_commands([Token.token])
            if command.has_error_handler()
        ]

        self.assertEqual(own_handlers, [])

    async def test_cooldown_is_answered_once_and_privately(self):
        bot = Demolizzen()
        ctx = make_ctx(make_guild())
        ctx.interaction.is_expired = MagicMock(return_value=False)
        ctx.interaction.response.is_done = MagicMock(return_value=False)
        error = commands.CommandOnCooldown(
            commands.Cooldown(3, 600), 42.5, commands.BucketType.user
        )

        await bot.on_application_command_error(ctx, error)

        ctx.respond.assert_awaited_once_with(
            content="You are on cooldown. Try again in 42.50s", ephemeral=True
        )
