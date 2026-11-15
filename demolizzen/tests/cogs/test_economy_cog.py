# Standard Library
from unittest.mock import MagicMock, patch

# Discord
import discord

# Django
from django.test import TestCase

# Demolizzen
from demolizzen.cogs.economy import missionfunc
from demolizzen.cogs.economy.economy import Economy
from demolizzen.cogs.economy.mission import TextAdventure
from demolizzen.models import (
    EconomyShip,
    EconomySolarSystem,
    UserBankAccount,
    UserDailyReward,
    UserProfile,
    UserRaidMission,
)
from demolizzen.services import bank, guilds
from demolizzen.tests.helpers import make_ctx, make_guild, make_member

MODULE = "demolizzen.cogs.economy.economy"


class EconomyTestCase(TestCase):
    def setUp(self):
        self.guild = make_guild(1, "Alpha")
        self.alice = make_member(10, "alice", guild=self.guild)
        self.bob = make_member(11, "bob", guild=self.guild)
        self.alice.mention, self.bob.mention = "<@10>", "<@11>"
        self.cog = Economy(MagicMock())

    async def ctx(self, author=None, cog=None):
        ctx = make_ctx(guild=self.guild, author=author or self.alice)
        await (cog or self.cog).cog_before_invoke(ctx)
        return ctx

    async def fund(self, member, wallet: int):
        await guilds.ensure_guild(1, "Alpha")
        account = await bank.ensure_account(1, member.id, member.name)
        await UserBankAccount.objects.filter(pk=account.pk).aupdate(wallet=wallet)

    async def wallet(self, member) -> int:
        return (await UserBankAccount.objects.aget(user__user_id=member.id)).wallet

    @staticmethod
    def lines(ctx) -> str:
        call = ctx.respond.await_args
        embed = call.kwargs.get("embed")
        if embed is None:
            return call.args[0] if call.args else call.kwargs.get("content", "")
        return " ".join([embed.description or ""] + [f.value for f in embed.fields])


class DailyTest(EconomyTestCase):
    async def test_daily_credits_reward_and_works_without_profile(self):
        ctx = await self.ctx()

        with patch(f"{MODULE}.random.randrange", return_value=20):
            await self.cog.daily.callback(self.cog, ctx)

        self.assertEqual(await self.wallet(self.alice), 25)
        self.assertIn("daily reward of 25", self.lines(ctx))
        self.assertEqual((await UserDailyReward.objects.aget()).streak, 1)

    async def test_daily_cannot_be_collected_twice(self):
        ctx = await self.ctx()
        with patch(f"{MODULE}.random.randrange", return_value=20):
            await self.cog.daily.callback(self.cog, ctx)
            again = await self.ctx()
            await self.cog.daily.callback(self.cog, again)

        self.assertEqual(await self.wallet(self.alice), 25)
        self.assertIn("already collected", self.lines(again))


class GankTest(EconomyTestCase):
    async def gank(self, target, chance: int, amount: int = 7):
        ctx = await self.ctx()
        with patch(f"{MODULE}.random.randint", side_effect=[chance, amount]):
            await self.cog.gank.callback(self.cog, ctx, target)
        return ctx

    async def test_gank_success_moves_money_from_victim(self):
        await self.fund(self.alice, 50)
        await self.fund(self.bob, 100)

        ctx = await self.gank(self.bob, chance=10)

        self.assertEqual(await self.wallet(self.bob), 93)
        self.assertEqual(await self.wallet(self.alice), 57)
        self.assertIn("has looted 7:coin:", self.lines(ctx))

    async def test_gank_failure_moves_money_to_victim(self):
        await self.fund(self.alice, 50)
        await self.fund(self.bob, 100)

        ctx = await self.gank(self.bob, chance=50)

        self.assertEqual(await self.wallet(self.alice), 43)
        self.assertEqual(await self.wallet(self.bob), 107)
        self.assertIn("has lost 7:coin:", self.lines(ctx))

    async def test_gank_victim_without_money_finds_wreck_empty(self):
        await self.fund(self.alice, 50)

        ctx = await self.gank(self.bob, chance=10)

        self.assertEqual(await self.wallet(self.alice), 50)
        self.assertEqual(await self.wallet(self.bob), 0)
        self.assertIn("finds it empty", self.lines(ctx))

    async def test_failed_gank_without_money(self):
        await self.fund(self.alice, 3)
        await self.fund(self.bob, 100)

        ctx = await self.gank(self.bob, chance=50)

        self.assertEqual(await self.wallet(self.alice), 3)
        self.assertEqual(await self.wallet(self.bob), 100)
        self.assertIn("you are broke", self.lines(ctx))

    async def test_wormhole_moves_nothing(self):
        await self.fund(self.alice, 50)
        await self.fund(self.bob, 100)

        ctx = await self.gank(self.bob, chance=90)

        self.assertEqual(await self.wallet(self.alice), 50)
        self.assertEqual(await self.wallet(self.bob), 100)
        self.assertIn("wormhole", self.lines(ctx))

    async def test_gank_self_and_bot_is_refused(self):
        await self.fund(self.alice, 50)
        robot = make_member(99, "robot", bot=True, guild=self.guild)

        for target in (self.alice, robot):
            with self.subTest(target=target.name):
                ctx = await self.ctx()
                await self.cog.gank.callback(self.cog, ctx, target)

                self.assertEqual(self.lines(ctx), "You can't gank this target.")
                self.assertTrue(ctx.respond.await_args.kwargs["ephemeral"])

        self.assertEqual(await self.wallet(self.alice), 50)
        self.assertFalse(await UserProfile.objects.filter(user_id=99).aexists())


class MissionMoneyTest(EconomyTestCase):
    def setUp(self):
        super().setUp()
        self.missions = TextAdventure(MagicMock())

    async def make_mission(self, wallet: int, salary: int = 50, insurance: int = 500):
        await self.fund(self.alice, wallet)
        await EconomySolarSystem.objects.acreate(name="Jita", security_status=0.9)
        ship = await EconomyShip.objects.acreate(
            name="Rifter",
            ship_type="frigate",
            ship_speed=1,
            price=300,
            insurance=insurance,
            description="Fast",
            category="raiding",
        )
        profile = await UserProfile.objects.aget(user_id=10, guild_id=1)
        await UserRaidMission.objects.acreate(
            user=profile, salary=salary, chance=50, active=True, ship=ship
        )
        return await UserRaidMission.objects.select_related("user", "ship").aget(
            user=profile
        )

    async def trigger(self, mission, rolls):
        ctx = make_ctx(guild=self.guild, author=self.alice)
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.send_message = MagicMock(side_effect=_async_none)
        with patch.object(missionfunc.random, "randint", side_effect=rolls):
            view = missionfunc.MissionEvent(ctx, None, mission)
            await view.mission_trigger(interaction)

    async def test_successful_mission_pays_out(self):
        mission = await self.make_mission(wallet=0)

        await self.trigger(mission, [100, 1, 1, 15, 15])

        self.assertEqual(await self.wallet(self.alice), 50)

    async def test_lost_ship_costs_at_most_the_wallet(self):
        mission = await self.make_mission(wallet=120, insurance=500)

        await self.trigger(mission, [1, 100, 100, 15, 15])

        self.assertEqual(await self.wallet(self.alice), 0)

    async def test_buying_a_ship_takes_the_price(self):
        await self.fund(self.alice, 1000)
        ship = await EconomyShip.objects.acreate(
            name="Rifter",
            ship_type="frigate",
            ship_speed=1,
            price=300,
            insurance=50,
            description="Fast",
            category="raiding",
        )
        ctx = await self.ctx(cog=self.missions)

        await self.missions.buy.callback(self.missions, ctx, "Raiding", "Rifter")

        self.assertEqual(await self.wallet(self.alice), 700)
        mission = await UserRaidMission.objects.aget(user__user_id=10)
        self.assertEqual(mission.ship_id, ship.pk)

    async def test_ship_is_not_bought_without_enough_money(self):
        await self.fund(self.alice, 100)
        await EconomyShip.objects.acreate(
            name="Rifter",
            ship_type="frigate",
            ship_speed=1,
            price=300,
            insurance=50,
            description="Fast",
            category="raiding",
        )
        ctx = await self.ctx(cog=self.missions)

        await self.missions.buy.callback(self.missions, ctx, "Raiding", "Rifter")

        self.assertEqual(await self.wallet(self.alice), 100)
        mission = await UserRaidMission.objects.filter(user__user_id=10).afirst()
        self.assertTrue(mission is None or mission.ship_id is None)


async def _async_none(*args, **kwargs):
    return None
