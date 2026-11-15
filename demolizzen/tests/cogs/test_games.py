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

    async def test_player_without_account_gets_one_and_is_refused(self):
        ctx = await self.play(None, 100, LOSING)

        embed = ctx.respond.await_args.kwargs["embed"]
        self.assertIn("not have enough", embed.description)
        self.assertEqual(await self.wallet(), 0)

    async def test_zero_stake_is_refused(self):
        ctx = await self.play(1000, 0, LOSING)

        embed = ctx.respond.await_args.kwargs["embed"]
        self.assertIn("Amount must be at least 1.", embed.description)
        self.assertEqual(await self.wallet(), 1000)

    async def test_stake_above_the_table_limit_is_refused(self):
        ctx = await self.play(1000, 241, LOSING)

        embed = ctx.respond.await_args.kwargs["embed"]
        self.assertIn("The limit is 240", embed.description)
        self.assertEqual(await self.wallet(), 1000)

    async def test_bet_above_wallet_is_refused(self):
        await self.play(50, 100, LOSING)

        self.assertEqual(await self.wallet(), 50)

    async def test_win_message_names_the_doubled_bet(self):
        ctx = await self.play(1000, 100, [":red_circle:"] * 3)

        embed = ctx.respond.await_args.kwargs["embed"]
        self.assertIn("You won! 200 :coin:", embed.description)


class DiceTest(TestCase):
    async def play(self, wallet: int, amount: int, rolls):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.ensure_members(1, [(10, "player")])
        user = await UserProfile.objects.aget(user_id=10, guild_id=1)
        await UserBankAccount.objects.acreate(user=user, wallet=wallet)
        guild = make_guild(1, "Alpha")
        ctx = make_ctx(guild=guild, author=make_member(10, "player", guild=guild))
        cog = Games(MagicMock())
        with patch(
            "demolizzen.cogs.games.games.random.randint", side_effect=rolls
        ) as randint:
            await cog.dice.callback(cog, ctx, amount)
        return ctx, randint

    async def wallet(self) -> int:
        return (await UserBankAccount.objects.aget(user__user_id=10)).wallet

    @staticmethod
    def lines(ctx) -> str:
        embed = ctx.respond.await_args.kwargs["embed"]
        return " ".join([embed.description or ""] + [f.value for f in embed.fields])

    async def test_higher_dice_win_twice_the_stake(self):
        ctx, _ = await self.play(1000, 100, [6, 6, 1, 1])

        self.assertEqual(await self.wallet(), 1200)
        self.assertIn("You won 200 :coin:", self.lines(ctx))

    async def test_lower_dice_lose_the_stake(self):
        ctx, _ = await self.play(1000, 100, [1, 1, 6, 6])

        self.assertEqual(await self.wallet(), 900)
        self.assertIn("You lose 100 :coin:", self.lines(ctx))

    async def test_one_higher_die_is_not_enough(self):
        await self.play(1000, 100, [6, 1, 1, 6])

        self.assertEqual(await self.wallet(), 900)

    async def test_dice_have_six_sides(self):
        _, randint = await self.play(1000, 100, [3, 3, 3, 3])

        self.assertEqual(randint.call_count, 4)
        for call in randint.call_args_list:
            self.assertEqual(call.args, (1, 6))

    async def test_stake_above_wallet_is_refused(self):
        ctx, _ = await self.play(50, 100, [6, 6, 1, 1])

        self.assertEqual(await self.wallet(), 50)
        self.assertIn("not have enough", self.lines(ctx))
