# Standard Library
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

# Django
from django.test import TestCase

# Demolizzen
from demolizzen.cogs.banksystem._settings_page import (
    INTEREST_CHOICES,
    BankSettingsView,
    bank_settings_page,
    build_bank_settings_embed,
)
from demolizzen.cogs.banksystem.banksystem import Bank
from demolizzen.core import settings_pages
from demolizzen.core.bot import Demolizzen
from demolizzen.models import GuildBankSettings, UserBankAccount
from demolizzen.services import bank, cog_settings, guilds
from demolizzen.tests.helpers import make_guild, make_interaction, make_member


def labels(view) -> list[str]:
    return [
        getattr(item, "label", None) or getattr(item, "placeholder", None)
        for item in view.children
    ]


def field(embed, name: str) -> str:
    return next(f.value for f in embed.fields if f.name == name)


class InterestLoopTest(TestCase):
    def setUp(self):
        cog_settings.invalidate()
        self.bot = MagicMock()
        self.bot.guilds = [make_guild(1, "Alpha"), make_guild(2, "Beta")]
        with patch("discord.ext.tasks.Loop.start"):
            self.cog = Bank(self.bot)

    async def fund(self, guild_id: int, balance: int):
        await guilds.ensure_guild(guild_id, f"G{guild_id}")
        account = await bank.ensure_account(guild_id, 10, "u")
        await UserBankAccount.objects.filter(pk=account.pk).aupdate(bank=balance)

    async def bank_of(self, guild_id: int) -> int:
        return (await UserBankAccount.objects.aget(user__guild_id=guild_id)).bank

    async def test_interest_runs_for_due_guilds_with_module_enabled(self):
        await self.fund(1, 100_000)
        await self.fund(2, 100_000)
        await cog_settings.set_enabled(2, "banksystem", False, cascade=True)

        served = await self.cog.run_interest()

        self.assertEqual(served, 1)
        self.assertEqual(await self.bank_of(1), 100_100)
        self.assertEqual(await self.bank_of(2), 100_000)

    async def test_interest_is_not_paid_twice(self):
        await self.fund(1, 100_000)

        await self.cog.run_interest()
        served = await self.cog.run_interest()

        self.assertEqual(served, 0)
        self.assertEqual(await self.bank_of(1), 100_100)

    async def test_interest_failure_in_one_guild_does_not_stop_others(self):
        await self.fund(1, 100_000)
        await self.fund(2, 100_000)
        original = bank.pay_interest

        async def flaky(guild_id, now=None):
            if guild_id == 1:
                raise RuntimeError("boom")
            return await original(guild_id, now)

        with patch.object(bank, "pay_interest", side_effect=flaky):
            with self.assertLogs("demolizzen.cogs.banksystem.banksystem", "ERROR"):
                served = await self.cog.run_interest()

        self.assertEqual(served, 1)
        self.assertEqual(await self.bank_of(2), 100_100)

    def test_loop_checks_every_six_hours(self):
        self.assertEqual(Bank.interest.hours, 6)


class BankSettingsPageTest(TestCase):
    def setUp(self):
        cog_settings.invalidate()
        self.admin = make_member(10, "admin", manage_guild=True)
        self.guild = make_guild(
            1, "Alpha", members=[make_member(1, "boss"), self.admin]
        )
        self.back = AsyncMock()

    def interaction(self, user=None):
        return make_interaction(guild=self.guild, user=user or self.admin)

    async def make_view(self, **fields) -> BankSettingsView:
        await guilds.ensure_guild(1, "Alpha")
        if fields:
            await GuildBankSettings.objects.filter(guild_id=1).aupdate(**fields)
        return BankSettingsView(1, 10, self.back, await bank.get_settings(1))

    async def stored(self) -> GuildBankSettings:
        return await GuildBankSettings.objects.aget(guild_id=1)

    async def test_embed_shows_rate_and_switches(self):
        await guilds.ensure_guild(1, "Alpha")
        settings = await bank.update_settings(1, allow_withdrawals=False)

        embed = build_bank_settings_embed(settings)

        self.assertEqual(field(embed, "Interest per week"), "0.1%")
        self.assertEqual(field(embed, "Deposits"), "✅")
        self.assertEqual(field(embed, "Withdrawals"), "❌")

    async def test_existing_rate_outside_choices_is_shown(self):
        view = await self.make_view(interest_rate=0.5)

        self.assertEqual(field(view.embed(), "Interest per week"), "50%")

    async def test_controls(self):
        view = await self.make_view()

        self.assertEqual(
            labels(view),
            ["Interest per week", "Deposits: On", "Withdrawals: On", "Back"],
        )
        self.assertEqual(
            [option.label for option in view.children[0].options],
            [f"{percent:g}%" for percent in INTEREST_CHOICES],
        )

    async def test_set_interest_stores_fraction(self):
        view = await self.make_view()
        interaction = self.interaction()

        await view.set_interest(interaction, 5)

        self.assertAlmostEqual((await self.stored()).interest_rate, 0.05)
        edit = interaction.response.edit_message.await_args.kwargs
        self.assertEqual(field(edit["embed"], "Interest per week"), "5%")

    async def test_select_is_wired(self):
        view = await self.make_view()
        select = view.children[0]

        with patch.object(
            type(select), "values", new_callable=PropertyMock, return_value=["2"]
        ):
            await select.callback(self.interaction())

        self.assertAlmostEqual((await self.stored()).interest_rate, 0.02)

    async def test_fractional_choice_is_stored_exactly(self):
        view = await self.make_view()

        await view.set_interest(self.interaction(), 0.25)

        self.assertAlmostEqual((await self.stored()).interest_rate, 0.0025)

    async def test_toggle_flips_deposits_and_withdrawals(self):
        view = await self.make_view()

        await view.toggle(self.interaction(), "allow_deposits")
        await view.toggle(self.interaction(), "allow_withdrawals")

        stored = await self.stored()
        self.assertFalse(stored.allow_deposits)
        self.assertFalse(stored.allow_withdrawals)
        self.assertIn("Deposits: Off", labels(view))
        self.assertIn("Withdrawals: Off", labels(view))

    async def test_page_respects_panel_permission(self):
        view = await self.make_view()
        foreign = self.interaction(make_member(99, manage_guild=True))

        self.assertFalse(await view.interaction_check(foreign))
        self.assertTrue(await view.interaction_check(self.interaction()))

    async def test_back_returns_to_panel(self):
        view = await self.make_view()
        interaction = self.interaction()

        await view.go_back(interaction)

        self.back.assert_awaited_once_with(interaction)
        self.assertTrue(view.is_finished())

    async def test_page_function_shows_settings(self):
        interaction = self.interaction()

        await bank_settings_page(interaction, self.back)

        edit = interaction.response.edit_message.await_args.kwargs
        self.assertIsInstance(edit["view"], BankSettingsView)
        self.assertEqual(edit["embed"].title, "🏦 Banksystem – Settings")


class BankExtensionTest(TestCase):
    def setUp(self):
        with patch("discord.ext.tasks.Loop.start"):
            self.bot = Demolizzen()
            self.bot.preload_ext = ["banksystem"]
            self.results = self.bot.load_preload_extensions()
        self.addCleanup(settings_pages.unregister, "banksystem")

    def test_bank_settings_page_is_registered(self):
        self.assertIsNone(self.results["banksystem"])
        self.assertIs(settings_pages.get("banksystem"), bank_settings_page)

    def test_no_bank_config_cog_or_command(self):
        names = {command.name for command in self.bot.pending_application_commands}

        self.assertEqual(sorted(self.bot.cogs), ["Bank", "BankAdmin"])
        self.assertNotIn("bank_config", names)
        self.assertIn("bank", names)
