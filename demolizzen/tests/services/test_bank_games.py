# Django
from django.test import TestCase

# Demolizzen
from demolizzen.models import UserBankAccount
from demolizzen.services import bank, guilds
from demolizzen.services.bank import Balance
from demolizzen.services.errors import InsufficientFunds, InvalidAmount

A = 10


class BookingTestCase(TestCase):
    async def fund(self, wallet: int = 0, balance: int = 0):
        await guilds.ensure_guild(1, "Alpha")
        account = await bank.ensure_account(1, A, "alice")
        await UserBankAccount.objects.filter(pk=account.pk).aupdate(
            wallet=wallet, bank=balance
        )

    async def balance(self) -> Balance:
        account = await UserBankAccount.objects.aget(user__user_id=A)
        return Balance(account.wallet, account.bank)


class WagerTest(BookingTestCase):
    async def test_win_adds_twice_the_stake(self):
        await self.fund(wallet=100, balance=5)

        self.assertEqual(await bank.wager(1, A, "a", 30, True), Balance(160, 5))

    async def test_loss_takes_the_stake(self):
        await self.fund(wallet=100, balance=5)

        self.assertEqual(await bank.wager(1, A, "a", 30, False), Balance(70, 5))

    async def test_stake_above_wallet_is_refused_even_when_won(self):
        await self.fund(wallet=100)

        for won in (True, False):
            with self.subTest(won=won):
                with self.assertRaises(InsufficientFunds):
                    await bank.wager(1, A, "a", 101, won)

        self.assertEqual(await self.balance(), Balance(100, 0))

    async def test_whole_wallet_can_be_staked(self):
        await self.fund(wallet=100)

        self.assertEqual(await bank.wager(1, A, "a", 100, False), Balance(0, 0))

    async def test_bad_stakes(self):
        await self.fund(wallet=100)

        for stake in (0, -1, True, "5", bank.MAX_AMOUNT + 1):
            with self.subTest(stake=stake):
                with self.assertRaises(InvalidAmount):
                    await bank.wager(1, A, "a", stake, True)

        self.assertEqual(await self.balance(), Balance(100, 0))


class AdjustTest(BookingTestCase):
    async def test_positive_delta_is_credited(self):
        await self.fund()

        self.assertEqual(await bank.adjust(1, A, "a", 50), 50)
        self.assertEqual(await self.balance(), Balance(50, 0))

    async def test_negative_delta_is_taken(self):
        await self.fund(wallet=50)

        self.assertEqual(await bank.adjust(1, A, "a", -30), -30)
        self.assertEqual(await self.balance(), Balance(20, 0))

    async def test_negative_delta_never_goes_below_zero(self):
        await self.fund(wallet=20, balance=500)

        self.assertEqual(await bank.adjust(1, A, "a", -80), -20)
        self.assertEqual(await self.balance(), Balance(0, 500))

    async def test_zero_changes_nothing(self):
        await self.fund(wallet=20)

        self.assertEqual(await bank.adjust(1, A, "a", 0), 0)
        self.assertEqual(await self.balance(), Balance(20, 0))

    async def test_bad_deltas(self):
        await self.fund(wallet=20)

        for delta in (bank.MAX_AMOUNT + 1, -bank.MAX_AMOUNT - 1, True, "5", 2.5):
            with self.subTest(delta=delta):
                with self.assertRaises(InvalidAmount):
                    await bank.adjust(1, A, "a", delta)

    async def test_account_is_created_when_missing(self):
        await guilds.ensure_guild(1, "Alpha")

        self.assertEqual(await bank.adjust(1, 77, "newcomer", 5), 5)
