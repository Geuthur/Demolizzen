# Standard Library
from unittest.mock import MagicMock, patch

# Django
from django.test import TestCase

# Demolizzen
from demolizzen.cogs.games.games import Games
from demolizzen.models import UserBankAccount, UserProfile
from demolizzen.services import guilds
from demolizzen.tests.helpers import make_ctx, make_guild, make_member

LOSING = [":red_circle:", ":yellow_circle:", ":blue_circle:"]


class SlotsTest(TestCase):
    async def play(self, wallet: int | None, amount: int, rolls):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.ensure_members(1, [(10, "player")])
        if wallet is not None:
            user = await UserProfile.objects.aget(user_id=10, guild_id=1)
            await UserBankAccount.objects.acreate(user=user, wallet=wallet)
        guild = make_guild(1, "Alpha")
        ctx = make_ctx(guild=guild, author=make_member(10, "player", guild=guild))
        cog = Games(MagicMock())
        with patch("demolizzen.cogs.games.games.random.choice", side_effect=rolls):
            await cog.slots.callback(cog, ctx, amount)
        return ctx

    async def wallet(self) -> int:
        return (await UserBankAccount.objects.aget(user__user_id=10)).wallet

    async def test_losing_takes_the_bet_from_the_wallet(self):
        await self.play(1000, 100, LOSING)

        self.assertEqual(await self.wallet(), 900)

    async def test_winning_adds_to_the_wallet(self):
        await self.play(1000, 100, [":red_circle:"] * 3)

        self.assertEqual(await self.wallet(), 1200)

    async def test_player_without_account_is_told_so(self):
        ctx = await self.play(None, 100, LOSING)

        embed = ctx.respond.await_args.kwargs["embed"]
        self.assertIn("don't have a bank account", embed.description)

    async def test_bet_above_wallet_is_refused(self):
        await self.play(50, 100, LOSING)

        self.assertEqual(await self.wallet(), 50)

    async def test_win_message_names_the_doubled_bet(self):
        ctx = await self.play(1000, 100, [":red_circle:"] * 3)

        embed = ctx.respond.await_args.kwargs["embed"]
        self.assertIn("You won! 200 :coin:", embed.description)
