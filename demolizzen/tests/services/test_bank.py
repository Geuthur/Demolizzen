# Third Party
from asgiref.sync import sync_to_async

# Django
from django.test import TestCase

# Demolizzen
from demolizzen.models import (
    GuildBankSettings,
    UserBankAccount,
    UserProfile,
    UserSettings,
)
from demolizzen.services import bank, guilds
from demolizzen.services.bank import Balance
from demolizzen.services.errors import (
    BankActionDisabled,
    GuildNotRegistered,
    InsufficientFunds,
    InvalidAmount,
    InvalidTransfer,
)

A, B = 10, 11
BAD_AMOUNTS = (0, -5, bank.MAX_AMOUNT + 1, True, "5", 2.5, None)


class BankTestCase(TestCase):
    async def fund(self, user_id: int, wallet: int = 0, balance: int = 0):
        await guilds.ensure_guild(1, "Alpha")
        account = await bank.ensure_account(1, user_id, f"u{user_id}")
        await UserBankAccount.objects.filter(pk=account.pk).aupdate(
            wallet=wallet, bank=balance
        )
        return account

    async def balance(self, user_id: int) -> Balance:
        account = await UserBankAccount.objects.aget(user__user_id=user_id)
        return Balance(account.wallet, account.bank)


class AccountTest(BankTestCase):
    async def test_ensure_account_creates_profile_settings_and_account(self):
        await guilds.ensure_guild(1, "Alpha")

        account = await bank.ensure_account(1, A, "alice")

        self.assertEqual((account.wallet, account.bank), (0, 0))
        profile = await UserProfile.objects.aget(user_id=A, guild_id=1)
        self.assertEqual(profile.user_name, "alice")
        self.assertTrue(await UserSettings.objects.filter(user=profile).aexists())

    async def test_ensure_account_is_idempotent(self):
        await guilds.ensure_guild(1, "Alpha")
        first = await bank.ensure_account(1, A, "alice")

        second = await bank.ensure_account(1, A, "alice")

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(await UserProfile.objects.acount(), 1)
        self.assertEqual(await UserBankAccount.objects.acount(), 1)

    async def test_accounts_are_per_guild(self):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.ensure_guild(2, "Beta")
        await bank.credit(1, A, "alice", 50)

        self.assertEqual(await bank.get_balance(2, A, "alice"), Balance(0, 0))

    async def test_unregistered_guild_raises(self):
        with self.assertRaises(GuildNotRegistered):
            await bank.ensure_account(99, A, "alice")

    async def test_balance_of_new_member(self):
        await guilds.ensure_guild(1, "Alpha")

        self.assertEqual(await bank.get_balance(1, A, "alice"), Balance(0, 0))


class AmountTest(BankTestCase):
    async def test_bad_amounts_are_refused_everywhere(self):
        await self.fund(A, wallet=100, balance=100)
        await self.fund(B)
        calls = {
            "deposit": lambda amount: bank.deposit(1, A, "a", amount),
            "withdraw": lambda amount: bank.withdraw(1, A, "a", amount),
            "transfer": lambda amount: bank.transfer(1, A, "a", B, "b", amount),
            "credit": lambda amount: bank.credit(1, A, "a", amount),
            "debit": lambda amount: bank.debit(1, A, "a", amount),
        }
        for name, call in calls.items():
            for amount in BAD_AMOUNTS:
                with self.subTest(call=name, amount=amount):
                    with self.assertRaises(InvalidAmount):
                        await call(amount)

        self.assertEqual(await self.balance(A), Balance(100, 100))
        self.assertEqual(await self.balance(B), Balance(0, 0))

    async def test_messages(self):
        await self.fund(A, wallet=100)

        with self.assertRaisesMessage(InvalidAmount, "Amount must be at least 1."):
            await bank.deposit(1, A, "a", 0)
        with self.assertRaisesMessage(InvalidAmount, "Amount is too large."):
            await bank.deposit(1, A, "a", bank.MAX_AMOUNT + 1)

    async def test_largest_amount_is_accepted(self):
        await self.fund(A)

        result = await bank.credit(1, A, "a", bank.MAX_AMOUNT)

        self.assertEqual(result.wallet, bank.MAX_AMOUNT)


class DepositWithdrawTest(BankTestCase):
    async def test_deposit_moves_wallet_to_bank(self):
        await self.fund(A, wallet=100)

        self.assertEqual(await bank.deposit(1, A, "a", 60), Balance(40, 60))
        self.assertEqual(await self.balance(A), Balance(40, 60))

    async def test_deposit_more_than_wallet(self):
        await self.fund(A, wallet=100)

        with self.assertRaisesMessage(
            InsufficientFunds, "You don't have that much money!"
        ):
            await bank.deposit(1, A, "a", 101)

        self.assertEqual(await self.balance(A), Balance(100, 0))

    async def test_deposit_everything(self):
        await self.fund(A, wallet=100)

        self.assertEqual(await bank.deposit(1, A, "a", 100), Balance(0, 100))

    async def test_deposit_when_disabled(self):
        await self.fund(A, wallet=100)
        await GuildBankSettings.objects.filter(guild_id=1).aupdate(allow_deposits=False)

        with self.assertRaisesMessage(
            BankActionDisabled, "Deposits are disabled on this server."
        ):
            await bank.deposit(1, A, "a", 10)

        self.assertEqual(await self.balance(A), Balance(100, 0))

    async def test_withdraw_moves_bank_to_wallet(self):
        await self.fund(A, balance=100)

        self.assertEqual(await bank.withdraw(1, A, "a", 30), Balance(30, 70))

    async def test_withdraw_more_than_bank(self):
        await self.fund(A, wallet=500, balance=100)

        with self.assertRaises(InsufficientFunds):
            await bank.withdraw(1, A, "a", 101)

        self.assertEqual(await self.balance(A), Balance(500, 100))

    async def test_withdraw_when_disabled(self):
        await self.fund(A, balance=100)
        await GuildBankSettings.objects.filter(guild_id=1).aupdate(
            allow_withdrawals=False
        )

        with self.assertRaisesMessage(
            BankActionDisabled, "Withdrawals are disabled on this server."
        ):
            await bank.withdraw(1, A, "a", 10)

    async def test_disabled_deposits_do_not_block_withdrawals(self):
        await self.fund(A, balance=100)
        await GuildBankSettings.objects.filter(guild_id=1).aupdate(allow_deposits=False)

        self.assertEqual(await bank.withdraw(1, A, "a", 10), Balance(10, 90))


class TransferTest(BankTestCase):
    async def test_transfer_moves_wallet_to_wallet(self):
        await self.fund(A, wallet=100, balance=7)
        await self.fund(B, wallet=5)

        self.assertEqual(await bank.transfer(1, A, "a", B, "b", 30), Balance(70, 7))
        self.assertEqual(await self.balance(B), Balance(35, 0))

    async def test_transfer_to_self(self):
        await self.fund(A, wallet=100)

        with self.assertRaisesMessage(InvalidTransfer, "You can't send to yourself..."):
            await bank.transfer(1, A, "a", A, "a", 30)

    async def test_receiver_without_profile_gets_an_account(self):
        await self.fund(A, wallet=100)

        await bank.transfer(1, A, "a", 77, "newcomer", 30)

        self.assertEqual(await self.balance(77), Balance(30, 0))
        self.assertEqual(
            (await UserProfile.objects.aget(user_id=77)).user_name, "newcomer"
        )

    async def test_transfer_without_enough_money_changes_nothing(self):
        await self.fund(A, wallet=10)
        await self.fund(B, wallet=5)

        with self.assertRaises(InsufficientFunds):
            await bank.transfer(1, A, "a", B, "b", 30)

        self.assertEqual(await self.balance(A), Balance(10, 0))
        self.assertEqual(await self.balance(B), Balance(5, 0))

    async def test_opposite_transfers_keep_the_total(self):
        await self.fund(A, wallet=100)
        await self.fund(B, wallet=100)

        await bank.transfer(1, A, "a", B, "b", 30)
        await bank.transfer(1, B, "b", A, "a", 80)

        first, second = await self.balance(A), await self.balance(B)
        self.assertEqual((first.wallet, second.wallet), (150, 50))

    async def test_accounts_are_locked_in_primary_key_order(self):
        first = await self.fund(A)
        second = await self.fund(B)

        forward = await sync_to_async(bank._lock_accounts)(first.pk, second.pk)
        backward = await sync_to_async(bank._lock_accounts)(second.pk, first.pk)

        expected = sorted([first.pk, second.pk])
        self.assertEqual([account.pk for account in forward], expected)
        self.assertEqual([account.pk for account in backward], expected)


class FreshStateTest(BankTestCase):
    async def test_bookings_use_the_stored_balance(self):
        account = await self.fund(A, wallet=100)
        self.assertEqual(account.wallet, 0)  # the loaded object is already stale
        await UserBankAccount.objects.filter(pk=account.pk).aupdate(wallet=20)

        with self.assertRaises(InsufficientFunds):
            await bank.deposit(1, A, "a", 50)
        self.assertEqual(await bank.deposit(1, A, "a", 20), Balance(0, 20))


class CreditDebitTest(BankTestCase):
    async def test_credit_wallet_and_bank(self):
        await self.fund(A)

        self.assertEqual(await bank.credit(1, A, "a", 50), Balance(50, 0))
        self.assertEqual(await bank.credit(1, A, "a", 20, "bank"), Balance(50, 20))

    async def test_credit_creates_the_account(self):
        await guilds.ensure_guild(1, "Alpha")

        self.assertEqual(await bank.credit(1, 77, "newcomer", 50), Balance(50, 0))

    async def test_debit_returns_the_removed_amount(self):
        await self.fund(A, wallet=100, balance=40)

        self.assertEqual(await bank.debit(1, A, "a", 30), 30)
        self.assertEqual(await bank.debit(1, A, "a", 40, "bank"), 40)
        self.assertEqual(await self.balance(A), Balance(70, 0))

    async def test_debit_without_enough_money(self):
        await self.fund(A, wallet=10)

        with self.assertRaises(InsufficientFunds):
            await bank.debit(1, A, "a", 30)

        self.assertEqual(await self.balance(A), Balance(10, 0))

    async def test_clamped_debit_takes_what_is_there(self):
        await self.fund(A, wallet=10)

        self.assertEqual(await bank.debit(1, A, "a", 30, clamp=True), 10)
        self.assertEqual(await self.balance(A), Balance(0, 0))

    async def test_unknown_account_kind(self):
        await self.fund(A, wallet=10)

        with self.assertRaises(ValueError):
            await bank.credit(1, A, "a", 5, "savings")
        with self.assertRaises(ValueError):
            await bank.debit(1, A, "a", 5, "savings")

    async def test_reset(self):
        await self.fund(A, wallet=10, balance=20)

        await bank.reset(1, A, "a")

        self.assertEqual(await self.balance(A), Balance(0, 0))
