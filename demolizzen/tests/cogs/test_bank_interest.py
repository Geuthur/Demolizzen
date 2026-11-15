# Standard Library
from unittest.mock import MagicMock, patch

# Django
from django.test import TestCase

# Demolizzen
from demolizzen.cogs.banksystem.banksystem_config import BankConfig
from demolizzen.models import UserBankAccount, UserProfile
from demolizzen.services import cog_settings, guilds


async def make_account(guild_id: int, user_id: int, bank: int) -> None:
    await guilds.ensure_guild(guild_id, f"G{guild_id}")
    await guilds.ensure_members(guild_id, [(user_id, "u")])
    user = await UserProfile.objects.aget(user_id=user_id, guild_id=guild_id)
    await UserBankAccount.objects.acreate(user=user, bank=bank)


async def bank_of(user_id: int) -> int:
    return (await UserBankAccount.objects.aget(user__user_id=user_id)).bank


class BankInterestTest(TestCase):
    def setUp(self):
        cog_settings.invalidate()

    async def test_interest_is_paid_only_where_the_bank_is_enabled(self):
        await make_account(1, 10, 100_000)
        await make_account(2, 20, 100_000)
        await cog_settings.set_enabled(2, "banksystem", False, cascade=True)
        with patch("discord.ext.tasks.Loop.start"):
            cog = BankConfig(MagicMock())

        await cog.process_daily_interest()

        self.assertEqual(await bank_of(10), 100_100)
        self.assertEqual(await bank_of(20), 100_000)
