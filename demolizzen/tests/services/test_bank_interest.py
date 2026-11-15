# Standard Library
import importlib
from datetime import timedelta

# Django
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

# Demolizzen
from demolizzen.models import GuildBankSettings, UserBankAccount
from demolizzen.services import bank, guilds
from demolizzen.services.bank import Balance
from demolizzen.services.errors import GuildNotRegistered, InvalidBankSetting

migration = importlib.import_module(
    "demolizzen.migrations.0011_bank_interest_rate_fraction"
)


class InterestTestCase(TestCase):
    async def fund(self, guild_id: int, user_id: int, wallet=0, balance=0):
        await guilds.ensure_guild(guild_id, f"G{guild_id}")
        account = await bank.ensure_account(guild_id, user_id, f"u{user_id}")
        await UserBankAccount.objects.filter(pk=account.pk).aupdate(
            wallet=wallet, bank=balance
        )

    async def balance(self, guild_id: int, user_id: int) -> Balance:
        account = await UserBankAccount.objects.aget(
            user__user_id=user_id, user__guild_id=guild_id
        )
        return Balance(account.wallet, account.bank)

    async def settings(self, guild_id: int = 1) -> GuildBankSettings:
        return await GuildBankSettings.objects.aget(guild_id=guild_id)


class SettingsTest(InterestTestCase):
    async def test_defaults(self):
        await guilds.ensure_guild(1, "Alpha")

        settings = await bank.get_settings(1)

        self.assertEqual(settings.interest_rate, 0.001)
        self.assertTrue(settings.allow_deposits)
        self.assertTrue(settings.allow_withdrawals)

    async def test_get_settings_creates_missing_row(self):
        await guilds.ensure_guild(1, "Alpha")
        await GuildBankSettings.objects.filter(guild_id=1).adelete()

        await bank.get_settings(1)

        self.assertEqual(await GuildBankSettings.objects.acount(), 1)

    async def test_unregistered_guild_raises(self):
        with self.assertRaises(GuildNotRegistered):
            await bank.get_settings(99)

    async def test_each_setting_can_be_changed(self):
        await guilds.ensure_guild(1, "Alpha")
        for name, value in (
            ("interest_rate", 0.05),
            ("interest_rate", 0),
            ("interest_rate", 0.10),
            ("allow_deposits", False),
            ("allow_withdrawals", False),
        ):
            with self.subTest(setting=name, value=value):
                returned = await bank.update_settings(1, **{name: value})

                self.assertEqual(getattr(returned, name), value)
                self.assertEqual(getattr(await self.settings(), name), value)

    async def test_invalid_settings_are_refused(self):
        await guilds.ensure_guild(1, "Alpha")
        bad = [
            {"interest_rate": -0.1},
            {"interest_rate": 0.11},
            {"interest_rate": "x"},
            {"interest_rate": True},
            {"allow_deposits": "yes"},
            {"allow_withdrawals": 1},
            {"last_interest_update": None},
        ]
        for fields in bad:
            with self.subTest(fields=fields):
                with self.assertRaises(InvalidBankSetting):
                    await bank.update_settings(1, **fields)

        self.assertEqual((await self.settings()).interest_rate, 0.001)


class InterestTest(InterestTestCase):
    async def test_interest_is_added_to_the_bank_only(self):
        await self.fund(1, 10, wallet=5000, balance=100_000)

        paid = await bank.pay_interest(1)

        self.assertEqual(paid, 1)
        self.assertEqual(await self.balance(1, 10), Balance(5000, 100_100))
        self.assertIsNotNone((await self.settings()).last_interest_update)

    async def test_interest_is_rounded_down(self):
        await self.fund(1, 10, balance=999)
        await self.fund(1, 11, balance=1999)

        await bank.pay_interest(1)

        self.assertEqual((await self.balance(1, 10)).bank, 999)
        self.assertEqual((await self.balance(1, 11)).bank, 2000)

    async def test_only_accounts_of_the_guild_are_paid(self):
        await self.fund(1, 10, balance=100_000)
        await self.fund(2, 10, balance=100_000)

        await bank.pay_interest(1)

        self.assertEqual((await self.balance(2, 10)).bank, 100_000)

    async def test_returns_the_number_of_accounts_holding_money(self):
        await self.fund(1, 10, balance=100_000)
        await self.fund(1, 11, balance=0)
        await self.fund(1, 12, wallet=500)

        self.assertEqual(await bank.pay_interest(1), 1)

    async def test_second_payout_in_the_same_week_does_nothing(self):
        await self.fund(1, 10, balance=100_000)
        now = timezone.now()
        await bank.pay_interest(1, now)

        self.assertEqual(await bank.pay_interest(1, now + timedelta(days=6)), 0)
        self.assertEqual((await self.balance(1, 10)).bank, 100_100)

    async def test_payout_is_due_again_after_a_week(self):
        await self.fund(1, 10, balance=100_000)
        now = timezone.now()
        await bank.pay_interest(1, now)

        self.assertEqual(await bank.pay_interest(1, now + timedelta(days=7)), 1)
        self.assertEqual((await self.balance(1, 10)).bank, 100_200)

    async def test_guild_without_accounts(self):
        await guilds.ensure_guild(1, "Alpha")

        self.assertEqual(await bank.pay_interest(1), 0)
        self.assertIsNotNone((await self.settings()).last_interest_update)

    async def test_rate_zero_pays_nothing(self):
        await self.fund(1, 10, balance=100_000)
        await bank.update_settings(1, interest_rate=0)

        await bank.pay_interest(1)

        self.assertEqual((await self.balance(1, 10)).bank, 100_000)

    async def test_configured_rate_is_used(self):
        await self.fund(1, 10, balance=1000)
        await bank.update_settings(1, interest_rate=0.05)

        await bank.pay_interest(1)

        self.assertEqual((await self.balance(1, 10)).bank, 1050)

    async def test_due_guild_ids(self):
        now = timezone.now()
        for guild_id in (1, 2, 3):
            await guilds.ensure_guild(guild_id, f"G{guild_id}")
        await GuildBankSettings.objects.filter(guild_id=2).aupdate(
            last_interest_update=now - timedelta(days=8)
        )
        await GuildBankSettings.objects.filter(guild_id=3).aupdate(
            last_interest_update=now - timedelta(days=6)
        )
        await guilds.ensure_guild(4, "No settings")
        await GuildBankSettings.objects.filter(guild_id=4).adelete()

        due = await bank.due_guild_ids([1, 2, 3, 4, 99], now)

        self.assertEqual(due, [1, 2, 4])


class RateMigrationTest(SimpleTestCase):
    def test_convert_rate(self):
        cases = [(5, 0.05), (1, 0.01), (50, 0.10), (0.001, 0.001), (0.5, 0.5), (0, 0)]
        for stored, expected in cases:
            with self.subTest(stored=stored):
                self.assertAlmostEqual(migration.convert_rate(stored), expected)


class RateMigrationDataTest(InterestTestCase):
    def test_stored_rates_are_converted(self):
        # Django
        from django.apps import apps

        # Demolizzen
        from demolizzen.models import GuildProfile

        expected = {1: 0.05, 2: 0.5, 3: 0.001, 4: 0.10}
        stored = {1: 5, 2: 0.5, 3: 0.001, 4: 50}
        for guild_id, rate in stored.items():
            profile = GuildProfile.objects.create(guild_id=guild_id, guild_name="G")
            GuildBankSettings.objects.create(guild=profile, interest_rate=rate)

        migration.convert_rates(apps, None)

        for guild_id, rate in expected.items():
            with self.subTest(guild_id=guild_id):
                self.assertAlmostEqual(
                    GuildBankSettings.objects.get(guild_id=guild_id).interest_rate, rate
                )
