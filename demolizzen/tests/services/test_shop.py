# Django
from django.test import TestCase

# Demolizzen
from demolizzen.models import EconomyShop, UserBagItems, UserBankAccount
from demolizzen.services import bank, guilds, shop
from demolizzen.services.errors import (
    InsufficientFunds,
    InvalidQuantity,
    ItemNotFound,
    ItemNotOwned,
    NotEnoughItems,
)

A = 10


class ShopTestCase(TestCase):
    async def asetup(self, wallet: int = 100):
        await guilds.ensure_guild(1, "Alpha")
        account = await bank.ensure_account(1, A, "alice")
        await UserBankAccount.objects.filter(pk=account.pk).aupdate(wallet=wallet)
        await EconomyShop.objects.acreate(
            name="Beer", price=30, description="Cold", shop_type="drinks"
        )
        await EconomyShop.objects.acreate(
            name="Retired", price=1, description="Gone", active=False
        )

    async def wallet(self, user_id: int = A) -> int:
        return (await UserBankAccount.objects.aget(user__user_id=user_id)).wallet

    async def owned(self, name: str = "Beer") -> int | None:
        entry = await UserBagItems.objects.filter(
            user_bag__user__user_id=A, item_name=name
        ).afirst()
        return entry.quantity if entry else None


class BuyTest(ShopTestCase):
    async def test_buy_pays_and_fills_the_bag(self):
        await self.asetup()

        purchase = await shop.buy(1, A, "alice", "Beer", 2)

        self.assertEqual(purchase, shop.Purchase("Beer", 2, 60, 2))
        self.assertEqual(await self.wallet(), 40)
        self.assertEqual(await self.owned(), 2)
        entry = await UserBagItems.objects.aget(item_name="Beer")
        self.assertEqual(entry.item_type, "drinks")

    async def test_second_purchase_adds_to_the_bag(self):
        await self.asetup()
        await shop.buy(1, A, "alice", "Beer", 1)

        purchase = await shop.buy(1, A, "alice", "Beer", 2)

        self.assertEqual(purchase.owned, 3)
        self.assertEqual(await UserBagItems.objects.acount(), 1)

    async def test_bad_quantities_change_nothing(self):
        await self.asetup()

        for quantity in (0, -5, shop.MAX_QUANTITY + 1, True, "2", 1.5):
            with self.subTest(quantity=quantity):
                with self.assertRaises(InvalidQuantity):
                    await shop.buy(1, A, "alice", "Beer", quantity)

        self.assertEqual(await self.wallet(), 100)
        self.assertIsNone(await self.owned())

    async def test_not_enough_money_changes_nothing(self):
        await self.asetup(wallet=59)

        with self.assertRaises(InsufficientFunds):
            await shop.buy(1, A, "alice", "Beer", 2)

        self.assertEqual(await self.wallet(), 59)
        self.assertIsNone(await self.owned())

    async def test_unknown_and_inactive_items(self):
        await self.asetup()

        for name in ("Wine", "Retired", ""):
            with self.subTest(name=name):
                with self.assertRaises(ItemNotFound):
                    await shop.buy(1, A, "alice", name, 1)

    async def test_item_name_ignores_case(self):
        await self.asetup()

        purchase = await shop.buy(1, A, "alice", "beer", 1)

        self.assertEqual(purchase.item_name, "Beer")
        self.assertEqual(await self.owned("Beer"), 1)

    async def test_member_without_profile(self):
        await self.asetup()

        with self.assertRaises(InsufficientFunds):
            await shop.buy(1, 77, "newcomer", "Beer", 1)

        self.assertEqual(await self.wallet(77), 0)


class UseItemTest(ShopTestCase):
    async def test_use_reduces_the_quantity(self):
        await self.asetup(wallet=1000)
        await shop.buy(1, A, "alice", "Beer", 3)

        used = await shop.use_item(1, A, "alice", "beer", 2)

        self.assertEqual(used, shop.ItemUse("Beer", "drinks", 1))
        self.assertEqual(await self.owned(), 1)

    async def test_using_more_than_owned(self):
        await self.asetup(wallet=1000)
        await shop.buy(1, A, "alice", "Beer", 3)

        with self.assertRaises(NotEnoughItems):
            await shop.use_item(1, A, "alice", "Beer", 4)

        self.assertEqual(await self.owned(), 3)

    async def test_using_an_item_that_is_not_owned(self):
        await self.asetup()

        with self.assertRaises(ItemNotOwned):
            await shop.use_item(1, A, "alice", "Beer", 1)

    async def test_used_up_item_counts_as_not_owned(self):
        await self.asetup(wallet=1000)
        await shop.buy(1, A, "alice", "Beer", 1)
        await shop.use_item(1, A, "alice", "Beer", 1)

        with self.assertRaises(ItemNotOwned):
            await shop.use_item(1, A, "alice", "Beer", 1)

    async def test_bad_quantities(self):
        await self.asetup(wallet=1000)
        await shop.buy(1, A, "alice", "Beer", 3)

        for quantity in (0, -1, True):
            with self.subTest(quantity=quantity):
                with self.assertRaises(InvalidQuantity):
                    await shop.use_item(1, A, "alice", "Beer", quantity)

        self.assertEqual(await self.owned(), 3)
