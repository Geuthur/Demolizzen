# Standard Library
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# Django
from django.test import TestCase

# Demolizzen
from demolizzen.cogs.commands._economy import get_bag_data
from demolizzen.cogs.commands.commands import Commands
from demolizzen.models import (
    UserBag,
    UserBagItems,
    UserBankAccount,
    UserProfile,
)
from demolizzen.services import bank, guilds
from demolizzen.tests.helpers import make_ctx, make_guild, make_member


class CommandsTestCase(TestCase):
    def setUp(self):
        self.guild = make_guild(1, "Alpha")
        self.guild.icon = None
        self.alice = make_member(10, "McAlice", guild=self.guild)
        self.alice.mention = "<@10>"
        self.cog = Commands(MagicMock())

    async def ctx(self):
        ctx = make_ctx(guild=self.guild, author=self.alice)
        await self.cog.cog_before_invoke(ctx)
        return ctx

    async def fill_bag(self, count: int):
        profile = await UserProfile.objects.aget(user_id=10, guild_id=1)
        bag, _ = await UserBag.objects.aget_or_create(user=profile)
        await UserBagItems.objects.abulk_create(
            [
                UserBagItems(
                    user_bag=bag,
                    item_name=f"Item {number:02}",
                    item_type="drinks",
                    quantity=number + 1,
                )
                for number in range(count)
            ]
        )


class RegistrationTest(CommandsTestCase):
    async def test_commands_need_no_registration(self):
        ctx = await self.ctx()

        self.assertTrue(
            await UserProfile.objects.filter(user_id=10, guild_id=1).aexists()
        )
        self.assertTrue(
            await UserBankAccount.objects.filter(user__user_id=10).aexists()
        )
        ctx.respond.assert_not_awaited()

    async def test_second_command_keeps_the_profile(self):
        await self.ctx()
        await self.ctx()

        self.assertEqual(await UserProfile.objects.acount(), 1)


class BagTest(CommandsTestCase):
    async def test_bag_empty_message(self):
        ctx = await self.ctx()
        with patch(
            "demolizzen.cogs.commands._base.get_command_mention",
            return_value="</shop buy:1>",
        ):
            await self.cog.bag.callback(self.cog, ctx)

        embed = ctx.respond.await_args.kwargs["embed"]
        self.assertEqual(
            embed.description,
            "<@10>, Your Bag is empty... Buy something with </shop buy:1>",
        )
        self.assertEqual(embed.fields, [])

    async def test_bag_lists_items(self):
        ctx = await self.ctx()
        await self.fill_bag(2)

        await self.cog.bag.callback(self.cog, ctx)

        embed = ctx.respond.await_args.kwargs["embed"]
        self.assertEqual(embed.title, "McAlice's Bag")
        self.assertEqual(
            [(field.name, field.value) for field in embed.fields],
            [("Item 00", "Anzahl: 1"), ("Item 01", "Anzahl: 2")],
        )
        self.assertFalse(embed.footer)

    async def test_bag_shows_at_most_25_items(self):
        ctx = await self.ctx()
        await self.fill_bag(30)

        await self.cog.bag.callback(self.cog, ctx)

        embed = ctx.respond.await_args.kwargs["embed"]
        self.assertEqual(len(embed.fields), 25)
        self.assertEqual(embed.footer.text, "… and 5 more")

    async def test_item_suggestions_are_limited_and_filtered(self):
        await self.ctx()
        await self.fill_bag(30)
        interaction = SimpleNamespace(user=self.alice, guild=self.guild)

        everything = await get_bag_data(
            SimpleNamespace(interaction=interaction, value="")
        )
        some = await get_bag_data(
            SimpleNamespace(interaction=interaction, value="item 1")
        )
        nobody = await get_bag_data(
            SimpleNamespace(
                interaction=SimpleNamespace(user=make_member(99), guild=self.guild),
                value="",
            )
        )

        self.assertEqual(len(everything), 25)
        self.assertEqual(some, [f"Item {number}" for number in range(10, 20)])
        self.assertEqual(nobody, [])


class RichestTest(CommandsTestCase):
    async def test_richest_keeps_names_as_they_are(self):
        ctx = await self.ctx()
        await UserBankAccount.objects.filter(user__user_id=10).aupdate(wallet=70)
        account = await bank.ensure_account(1, 11, "bob")
        await UserBankAccount.objects.filter(pk=account.pk).aupdate(wallet=90)

        with patch(
            "demolizzen.cogs.commands._base.CommandsBase.LeaderboardPaginator"
        ) as paginator:
            paginator.return_value.respond = AsyncMock()
            await self.cog.richest.callback(self.cog, ctx)

        (embed,) = paginator.call_args.kwargs["pages"]
        self.assertEqual(embed.title, "Alpha Richest Players")
        self.assertEqual(
            embed.description,
            ":bank: Server Total :coin: 160\n\n"
            ":first_place: bob :coin: 90\n"
            ":second_place: McAlice :coin: 70\n",
        )
        paginator.return_value.respond.assert_awaited_once_with(ctx.interaction)

    async def test_richest_without_accounts(self):
        await guilds.ensure_guild(1, "Alpha")
        ctx = make_ctx(guild=self.guild, author=self.alice)

        await self.cog.richest.callback(self.cog, ctx)

        self.assertEqual(
            ctx.respond.await_args.args[0],
            "No users found in the database. Please try again later.",
        )
