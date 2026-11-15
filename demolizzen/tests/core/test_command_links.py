# Standard Library
from unittest.mock import MagicMock, PropertyMock, patch

# Django
from django.test import SimpleTestCase

# Demolizzen
from demolizzen.cogs.commands._help import CategorySelect
from demolizzen.core.bot import Demolizzen
from demolizzen.tests.helpers import make_interaction
from demolizzen.utils.functions import get_command_mention

ALPHA, BRAVO = 1000, 2000


def loaded_bot() -> Demolizzen:
    bot = Demolizzen()
    bot.preload_ext = ["eveonline"]
    with patch("discord.ext.tasks.Loop.start"), patch("builtins.print"):
        bot.load_preload_extensions()
    return bot


def ids_per_server(bot: Demolizzen, ids: dict[int, int]) -> None:
    """Discord gave the command a different id in every server."""
    bot.command_scope.command_id = MagicMock(
        side_effect=lambda _command, guild_id: ids.get(guild_id)
    )


class CommandMentionTest(SimpleTestCase):
    def mention(self, bot, guild_id):
        return get_command_mention(
            bot,
            cog="EveOnline",
            slash_command="eve",
            slash_command_group="price",
            guild_id=guild_id,
        )

    def test_link_carries_the_id_of_the_server_it_is_shown_in(self):
        bot = loaded_bot()
        ids_per_server(bot, {ALPHA: 11, BRAVO: 22})

        self.assertEqual(self.mention(bot, ALPHA), "</eve price:11>")
        self.assertEqual(self.mention(bot, BRAVO), "</eve price:22>")

    def test_plain_text_where_the_command_is_not_registered(self):
        bot = loaded_bot()
        ids_per_server(bot, {ALPHA: 11})

        self.assertEqual(self.mention(bot, BRAVO), "/eve price")

    def test_plain_text_for_an_unknown_module(self):
        bot = loaded_bot()

        self.assertEqual(
            get_command_mention(bot, cog="Nope", slash_command="x", guild_id=ALPHA),
            "/x",
        )


class HelpLinkTest(SimpleTestCase):
    async def module_help(self, bot, guild_id) -> str:
        select = CategorySelect(bot, [])
        interaction = make_interaction()
        interaction.guild_id = guild_id
        with patch.object(
            CategorySelect,
            "values",
            new_callable=PropertyMock,
            return_value=["EveOnline"],
        ):
            await select.callback(interaction)
        embed = interaction.response.edit_message.await_args.kwargs["embed"]
        return "\n".join(field.value for field in embed.fields)

    async def test_help_links_carry_the_id_of_this_server(self):
        bot = loaded_bot()
        ids_per_server(bot, {ALPHA: 11, BRAVO: 22})

        text = await self.module_help(bot, BRAVO)

        self.assertIn("</eve price:22>", text)
        self.assertNotIn(":11>", text)

    async def test_help_names_the_command_plainly_without_an_id(self):
        bot = loaded_bot()
        ids_per_server(bot, {})

        text = await self.module_help(bot, BRAVO)

        self.assertIn("/eve price", text)
        self.assertNotIn("</", text)
        self.assertNotIn("None", text)
