# Standard Library
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Discord
import discord

# Django
from django.test import TestCase
from django.utils import timezone

# Demolizzen
from demolizzen import models as models_package
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
    UserWorkMission,
)
from demolizzen.services import bank, guilds, missions
from demolizzen.services.missions import Kind
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

    async def test_streak_grows_the_next_day(self):
        ctx = await self.ctx()
        with patch(f"{MODULE}.random.randrange", return_value=20):
            await self.cog.daily.callback(self.cog, ctx)
            await UserDailyReward.objects.all().aupdate(
                last_claim=timezone.now() - timedelta(days=1, minutes=5)
            )
            again = await self.ctx()
            await self.cog.daily.callback(self.cog, again)

        self.assertEqual(await self.wallet(self.alice), 55)
        self.assertIn("**2** At once", self.lines(again))


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

    async def make_ship(self, **fields):
        defaults = {
            "name": "Rifter",
            "ship_type": "frigate",
            "ship_speed": 600,
            "price": 300,
            "insurance": 500,
            "description": "Fast",
            "category": "raiding",
        }
        defaults.update(fields)
        return await EconomyShip.objects.acreate(**defaults)

    async def make_mission(self, wallet: int, salary: int = 50, insurance: int = 500):
        """A raid mission that has returned and awaits its report."""
        await self.fund(self.alice, wallet)
        await EconomySolarSystem.objects.acreate(name="Jita", security_status=0.9)
        ship = await self.make_ship(insurance=insurance)
        profile = await UserProfile.objects.aget(user_id=10, guild_id=1)
        await UserRaidMission.objects.acreate(
            user=profile,
            salary=salary,
            chance=50,
            active=True,
            ship=ship,
            cooldown=timezone.now() - timedelta(hours=1),
        )
        return await missions.get_mission(1, 10, "alice", Kind.RAIDING)

    def view(self, mission, init_chance: int):
        ctx = make_ctx(guild=self.guild, author=self.alice)
        with patch.object(missionfunc.random, "randint", return_value=init_chance):
            return missionfunc.MissionEvent(ctx, None, mission, Kind.RAIDING)

    @staticmethod
    def click():
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        return interaction

    async def trigger(self, view, roll: int):
        interaction = self.click()
        with patch.object(missionfunc.random, "randint", side_effect=[roll, 15]):
            result = await view.mission_trigger(interaction)
        return interaction, result

    @staticmethod
    def report(interaction) -> str:
        call = interaction.response.send_message.await_args
        embed = call.kwargs.get("embed")
        if embed is None:
            return call.args[0] if call.args else ""
        return " ".join(f.value for f in embed.fields)

    async def test_successful_mission_pays_out(self):
        mission = await self.make_mission(wallet=0)

        _, result = await self.trigger(self.view(mission, init_chance=100), roll=1)

        self.assertTrue(result)
        self.assertEqual(await self.wallet(self.alice), 50)

    async def test_lost_ship_costs_at_most_the_wallet(self):
        mission = await self.make_mission(wallet=120, insurance=500)

        await self.trigger(self.view(mission, init_chance=1), roll=100)

        self.assertEqual(await self.wallet(self.alice), 0)

    async def test_two_mission_messages_pay_only_once(self):
        mission = await self.make_mission(wallet=0)
        first = self.view(mission, init_chance=100)
        second = self.view(mission, init_chance=100)

        await self.trigger(first, roll=1)
        interaction, _ = await self.trigger(second, roll=1)

        self.assertEqual(await self.wallet(self.alice), 50)
        call = interaction.response.send_message.await_args
        self.assertEqual(call.args[0], "This mission has already been reported.")
        self.assertTrue(call.kwargs["ephemeral"])

    async def test_click_then_timeout_pays_only_once(self):
        mission = await self.make_mission(wallet=0)
        view = self.view(mission, init_chance=100)
        await self.trigger(view, roll=1)
        view.ctx.send = AsyncMock()

        with patch.object(missionfunc.random, "randint", side_effect=[1, 15]):
            with patch("discord.ui.View.on_timeout", new_callable=AsyncMock):
                await view.on_timeout()

        self.assertEqual(await self.wallet(self.alice), 50)
        view.ctx.send.assert_not_awaited()

    async def test_timeout_settles_an_unanswered_mission(self):
        mission = await self.make_mission(wallet=0)
        view = self.view(mission, init_chance=100)
        view.ctx.send = AsyncMock()

        with patch.object(missionfunc.random, "randint", side_effect=[1, 15]):
            with patch("discord.ui.View.on_timeout", new_callable=AsyncMock):
                await view.on_timeout()

        self.assertEqual(await self.wallet(self.alice), 50)
        view.ctx.send.assert_awaited_once()

    async def test_report_matches_booked_outcome(self):
        mission = await self.make_mission(wallet=1000, insurance=500)
        dock = mission.get_dock_story()

        lost, _ = await self.trigger(self.view(mission, init_chance=1), roll=100)

        self.assertEqual(await self.wallet(self.alice), 500)
        self.assertNotIn(dock, self.report(lost))
        self.assertIn("having paid 500 :coin: for insurance", self.report(lost))

    async def test_report_names_what_was_actually_paid(self):
        mission = await self.make_mission(wallet=120, insurance=500)

        lost, _ = await self.trigger(self.view(mission, init_chance=1), roll=100)

        self.assertIn("having paid 120 :coin: for insurance", self.report(lost))

    async def test_successful_report_names_the_payout(self):
        mission = await self.make_mission(wallet=0, salary=50)

        won, _ = await self.trigger(self.view(mission, init_chance=100), roll=1)

        self.assertIn("**`50`**", self.report(won))

    async def test_mission_cancel_then_click_pays_nothing(self):
        mission = await self.make_mission(wallet=0)
        view = self.view(mission, init_chance=100)
        ctx = await self.ctx(cog=self.missions)

        await self.missions.mission_cancel.callback(self.missions, ctx, "Raiding")
        interaction, _ = await self.trigger(view, roll=1)

        self.assertEqual(await self.wallet(self.alice), 0)
        self.assertIn("has been canceled", self.lines(ctx))
        self.assertEqual(
            interaction.response.send_message.await_args.args[0],
            "This mission has already been reported.",
        )

    async def test_mission_start_without_ship_tells_user(self):
        ctx = await self.ctx(cog=self.missions)

        await self.missions.missionevent.callback(self.missions, ctx, "Raiding")

        self.assertIn("You don't have a ship yet.", self.lines(ctx))

    async def test_mission_start_begins_then_reports(self):
        await self.fund(self.alice, 0)
        await EconomySolarSystem.objects.acreate(name="Jita", security_status=0.9)
        ship = await self.make_ship()
        mission = await missions.get_mission(1, 10, "alice", Kind.RAIDING)
        await UserRaidMission.objects.filter(pk=mission.pk).aupdate(ship=ship)

        first = await self.ctx(cog=self.missions)
        await self.missions.missionevent.callback(self.missions, first, "Raiding")
        self.assertIn("You are starting your mission", self.lines(first))

        early = await self.ctx(cog=self.missions)
        await self.missions.missionevent.callback(self.missions, early, "Raiding")
        self.assertIn("You are still on your way", self.lines(early))

        await UserRaidMission.objects.filter(pk=mission.pk).aupdate(
            cooldown=timezone.now() - timedelta(hours=1)
        )
        back = await self.ctx(cog=self.missions)
        await self.missions.missionevent.callback(self.missions, back, "Raiding")
        view = back.respond.await_args.kwargs["view"]
        self.assertIsInstance(view, missionfunc.MissionEvent)
        self.assertEqual([item.label for item in view.children], ["Attack", "Warp Out"])

    async def test_work_pays_once_per_shift(self):
        ctx = await self.ctx(cog=self.missions)
        await self.missions.work.callback(self.missions, ctx)
        self.assertIn("You are starting to work", self.lines(ctx))

        early = await self.ctx(cog=self.missions)
        await self.missions.work.callback(self.missions, early)
        self.assertIn("You have already started working", self.lines(early))
        self.assertEqual(await self.wallet(self.alice), 0)

        await UserWorkMission.objects.filter(user__user_id=10).aupdate(
            cooldown=timezone.now() - timedelta(hours=2)
        )
        paid = await self.ctx(cog=self.missions)
        await self.missions.work.callback(self.missions, paid)
        earned = await self.wallet(self.alice)
        self.assertGreater(earned, 0)
        self.assertIn(str(earned), self.lines(paid))

        again = await self.ctx(cog=self.missions)
        await self.missions.work.callback(self.missions, again)
        self.assertEqual(await self.wallet(self.alice), earned)

    async def test_buying_a_ship_takes_the_price(self):
        await self.fund(self.alice, 1000)
        ship = await self.make_ship()
        ctx = await self.ctx(cog=self.missions)

        await self.missions.buy.callback(self.missions, ctx, "Raiding", "Rifter")

        self.assertEqual(await self.wallet(self.alice), 700)
        mission = await UserRaidMission.objects.aget(user__user_id=10)
        self.assertEqual(mission.ship_id, ship.pk)
        self.assertIn("Buys a **`Rifter`**", self.lines(ctx))

    async def test_ship_is_not_bought_without_enough_money(self):
        await self.fund(self.alice, 100)
        await self.make_ship()
        ctx = await self.ctx(cog=self.missions)

        await self.missions.buy.callback(self.missions, ctx, "Raiding", "Rifter")

        self.assertEqual(await self.wallet(self.alice), 100)
        mission = await UserRaidMission.objects.filter(user__user_id=10).afirst()
        self.assertTrue(mission is None or mission.ship_id is None)
        self.assertIn("You don't have enough :coin:", self.lines(ctx))

    async def test_buying_the_same_ship_twice(self):
        await self.fund(self.alice, 1000)
        await self.make_ship()
        first = await self.ctx(cog=self.missions)
        await self.missions.buy.callback(self.missions, first, "Raiding", "Rifter")
        ctx = await self.ctx(cog=self.missions)

        await self.missions.buy.callback(self.missions, ctx, "Raiding", "Rifter")

        self.assertEqual(await self.wallet(self.alice), 700)
        self.assertIn("You already own the Ship", self.lines(ctx))


class ModelPurityTest(TestCase):
    def test_models_do_not_import_discord(self):
        folder = Path(models_package.__file__).parent
        offenders = [
            path.name
            for path in sorted(folder.glob("*.py"))
            if "import discord" in path.read_text()
        ]

        self.assertEqual(offenders, [])
