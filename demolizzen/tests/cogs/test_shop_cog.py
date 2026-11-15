# Standard Library
from unittest.mock import MagicMock, patch

# Django
from django.test import TestCase

# Demolizzen
from demolizzen.cogs.commands.commands import Commands
from demolizzen.cogs.shop.shop import Shop
from demolizzen.models import EconomyShop, UserBagItems, UserBankAccount
from demolizzen.services import bank, guilds
from demolizzen.services import shop as shop_service
from demolizzen.tests.helpers import make_ctx, make_guild, make_member


class ShopCogTestCase(TestCase):
    def setUp(self):
        self.guild = make_guild(1, "Alpha")
        self.alice = make_member(10, "alice", guild=self.guild)
        with patch("discord.ext.tasks.Loop.start"):
            self.cog = Shop(MagicMock())

    def ctx(self, author=None):
        return make_ctx(guild=self.guild, author=author or self.alice)

    async def stock(self, wallet: int = 100):
        await guilds.ensure_guild(1, "Alpha")
        account = await bank.ensure_account(1, 10, "alice")
        await UserBankAccount.objects.filter(pk=account.pk).aupdate(wallet=wallet)
        await EconomyShop.objects.acreate(
            name="Beer", price=30, description="Cold", shop_type="drinks"
        )

    async def wallet(self, user_id: int = 10) -> int:
        return (await UserBankAccount.objects.aget(user__user_id=user_id)).wallet

    async def owned(self) -> int:
        entry = await UserBagItems.objects.filter(item_name="Beer").afirst()
        return entry.quantity if entry else 0

    @staticmethod
    def said(ctx) -> str:
        return ctx.respond.await_args.kwargs["embed"].description


class ShopBuyTest(ShopCogTestCase):
    async def test_buy_pays_and_fills_the_bag(self):
        await self.stock()
        ctx = self.ctx()

        await self.cog.shopbuy.callback(self.cog, ctx, "Beer", 2)

        self.assertEqual(await self.wallet(), 40)
        self.assertEqual(await self.owned(), 2)
        self.assertIn("Buy 2 x **`Beer`**", self.said(ctx))

    async def test_negative_quantity_is_refused(self):
        await self.stock()
        ctx = self.ctx()

        await self.cog.shopbuy.callback(self.cog, ctx, "Beer", -5)

        self.assertEqual(await self.wallet(), 100)
        self.assertEqual(await self.owned(), 0)
        self.assertIn("must be between 1 and 1000", self.said(ctx))

    async def test_not_enough_money(self):
        await self.stock(wallet=10)
        ctx = self.ctx()

        await self.cog.shopbuy.callback(self.cog, ctx, "Beer", 1)

        self.assertEqual(await self.wallet(), 10)
        self.assertIn("You have not enough :coin:", self.said(ctx))

    async def test_unknown_item(self):
        await self.stock()
        ctx = self.ctx()

        await self.cog.shopbuy.callback(self.cog, ctx, "Wine", 1)

        self.assertIn("The Item `Wine` was not found!", self.said(ctx))

    async def test_member_without_profile_can_use_the_shop(self):
        await self.stock()
        newcomer = make_member(77, "newcomer", guild=self.guild)
        ctx = self.ctx(newcomer)

        await self.cog.cog_before_invoke(ctx)
        await self.cog.shopbuy.callback(self.cog, ctx, "Beer", 1)

        self.assertEqual(await self.wallet(77), 0)
        self.assertIn("You have not enough :coin:", self.said(ctx))


class UseItemCommandTest(ShopCogTestCase):
    async def test_use_consumes_items(self):
        await self.stock(wallet=1000)
        await shop_service.buy(1, 10, "alice", "Beer", 3)
        commands = Commands(MagicMock())
        ctx = self.ctx()

        await commands.use.callback(commands, ctx, "Beer", 2)

        self.assertEqual(await self.owned(), 1)
        self.assertIn("Beer", self.said(ctx))

    async def test_use_more_than_owned_is_refused(self):
        await self.stock(wallet=1000)
        await shop_service.buy(1, 10, "alice", "Beer", 1)
        commands = Commands(MagicMock())
        ctx = self.ctx()

        await commands.use.callback(commands, ctx, "Beer", 5)

        self.assertEqual(await self.owned(), 1)
        self.assertIn("don't have enough", self.said(ctx))

    async def test_use_item_that_is_not_owned(self):
        await self.stock()
        commands = Commands(MagicMock())
        ctx = self.ctx()

        await commands.use.callback(commands, ctx, "Beer", 1)

        self.assertIn("You don't have `Beer` in your bag", self.said(ctx))

    async def test_use_negative_quantity_is_refused(self):
        await self.stock(wallet=1000)
        await shop_service.buy(1, 10, "alice", "Beer", 1)
        commands = Commands(MagicMock())
        ctx = self.ctx()

        await commands.use.callback(commands, ctx, "Beer", -3)

        self.assertEqual(await self.owned(), 1)
        self.assertIn("must be positive", self.said(ctx))

    async def test_use_shows_drink_text_for_drinks(self):
        await self.stock(wallet=1000)
        await shop_service.buy(1, 10, "alice", "Beer", 1)
        commands = Commands(MagicMock())
        ctx = self.ctx()

        await commands.use.callback(commands, ctx, "Beer", 1)

        self.assertNotIn("benutzt 1 x Beer", self.said(ctx))
