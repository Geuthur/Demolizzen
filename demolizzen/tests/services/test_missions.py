# Standard Library
from datetime import timedelta

# Django
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

# Demolizzen
from demolizzen.models import (
    EconomyShip,
    UserBankAccount,
    UserDailyReward,
    UserProfile,
    UserRaidMission,
    UserWorkMission,
)
from demolizzen.services import bank, guilds, missions
from demolizzen.services.errors import (
    AlreadySettled,
    GuildNotRegistered,
    InsufficientFunds,
    InvalidEventFactor,
    NoActiveMission,
    NoShip,
    OnCooldown,
    ShipAlreadyOwned,
    ShipNotFound,
)
from demolizzen.services.missions import Event, Kind, Outcome

A = 10
WHO = (1, A, "alice")
NOW = timezone.now()


class MissionsTestCase(TestCase):
    async def fund(self, wallet: int = 0):
        await guilds.ensure_guild(1, "Alpha")
        account = await bank.ensure_account(*WHO)
        await UserBankAccount.objects.filter(pk=account.pk).aupdate(wallet=wallet)

    async def wallet(self) -> int:
        return (await UserBankAccount.objects.aget(user__user_id=A)).wallet

    async def make_ship(self, name="Rifter", category="raiding", **fields):
        defaults = {
            "ship_type": "frigate",
            "ship_speed": 600,
            "price": 300,
            "insurance": 500,
            "description": "Fast",
        }
        defaults.update(fields)
        return await EconomyShip.objects.acreate(
            name=name, category=category, **defaults
        )

    async def with_ship(self, wallet: int = 0):
        await self.fund(wallet)
        ship = await self.make_ship()
        mission = await missions.get_mission(*WHO, Kind.RAIDING)
        await UserRaidMission.objects.filter(pk=mission.pk).aupdate(ship=ship)
        return ship

    async def mission(self) -> UserRaidMission:
        return await UserRaidMission.objects.aget(user__user_id=A)


class CooldownHelperTest(SimpleTestCase):
    def test_normal_member_keeps_the_duration(self):
        hour = timedelta(hours=1)

        self.assertEqual(missions.cooldown_for(1, 10, hour), hour)

    def test_test_accounts_have_ten_seconds(self):
        hour = timedelta(hours=1)
        ten = timedelta(seconds=10)

        for guild_id in (518052275076464640, 337275567487320064):
            for user_id in (784546720935182357, 240850566002114561):
                with self.subTest(guild_id=guild_id, user_id=user_id):
                    self.assertEqual(
                        missions.cooldown_for(guild_id, user_id, hour), ten
                    )
        self.assertEqual(missions.cooldown_for(1, 784546720935182357, hour), hour)

    def test_format_remaining(self):
        remaining = timedelta(hours=1, minutes=2, seconds=3, microseconds=500000)

        self.assertEqual(missions.format_remaining(remaining), "1:02:03")


class DailyTest(MissionsTestCase):
    async def test_first_claim(self):
        await self.fund()

        claim = await missions.claim_daily(*WHO, 20, NOW)

        self.assertEqual(claim, missions.DailyClaim(streak=1, reward=25))
        self.assertEqual(await self.wallet(), 25)

    async def test_second_claim_on_the_same_day_is_refused(self):
        await self.fund()
        await missions.claim_daily(*WHO, 20, NOW)

        with self.assertRaises(OnCooldown) as caught:
            await missions.claim_daily(*WHO, 20, NOW + timedelta(hours=1))

        self.assertEqual(caught.exception.remaining, timedelta(hours=23))
        self.assertEqual(await self.wallet(), 25)
        self.assertEqual((await UserDailyReward.objects.aget()).streak, 1)

    async def test_streak_grows_the_next_day(self):
        await self.fund()
        await missions.claim_daily(*WHO, 20, NOW)

        claim = await missions.claim_daily(*WHO, 20, NOW + timedelta(days=1, minutes=1))

        self.assertEqual(claim, missions.DailyClaim(streak=2, reward=30))
        self.assertEqual(await self.wallet(), 55)

    async def test_member_without_profile(self):
        await guilds.ensure_guild(1, "Alpha")

        claim = await missions.claim_daily(1, 77, "newcomer", 0, NOW)

        self.assertEqual(claim.reward, 5)


class WorkTest(MissionsTestCase):
    async def test_first_shift_pays_nothing(self):
        await self.fund()

        shift = await missions.work(*WHO, 50, 10, NOW)

        self.assertEqual(shift, missions.WorkShift(True, 0, timedelta(hours=1)))
        self.assertEqual(await self.wallet(), 0)
        self.assertEqual((await UserWorkMission.objects.aget()).salary, 50)

    async def test_working_again_too_early_is_refused(self):
        await self.fund()
        await missions.work(*WHO, 50, 10, NOW)

        with self.assertRaises(OnCooldown) as caught:
            await missions.work(*WHO, 50, 10, NOW + timedelta(minutes=20))

        self.assertEqual(caught.exception.remaining, timedelta(minutes=40))

    async def test_later_shift_pays_the_payout(self):
        await self.fund()
        await missions.work(*WHO, 50, 10, NOW)

        shift = await missions.work(*WHO, 70, 10, NOW + timedelta(hours=1))

        self.assertEqual(shift, missions.WorkShift(False, 70, timedelta(hours=1)))
        self.assertEqual(await self.wallet(), 70)

    async def test_shift_is_paid_only_once(self):
        await self.fund()
        await missions.work(*WHO, 50, 10, NOW)
        later = NOW + timedelta(hours=1)
        await missions.work(*WHO, 70, 10, later)

        with self.assertRaises(OnCooldown):
            await missions.work(*WHO, 70, 10, later)

        self.assertEqual(await self.wallet(), 70)


class BeginTest(MissionsTestCase):
    async def test_mission_needs_a_ship(self):
        await self.fund()

        with self.assertRaises(NoShip):
            await missions.begin(*WHO, Kind.RAIDING, 20, 15, NOW)

    async def test_first_mission_starts(self):
        await self.with_ship()

        self.assertTrue(await missions.begin(*WHO, Kind.RAIDING, 20, 15, NOW))

        mission = await self.mission()
        self.assertEqual((mission.salary, mission.chance), (20, 15))
        self.assertTrue(mission.active)
        self.assertEqual(mission.cooldown, NOW)

    async def test_mission_in_flight_is_on_cooldown(self):
        await self.with_ship()
        await missions.begin(*WHO, Kind.RAIDING, 20, 15, NOW)

        with self.assertRaises(OnCooldown) as caught:
            await missions.begin(*WHO, Kind.RAIDING, 99, 99, NOW + timedelta(minutes=4))

        self.assertEqual(caught.exception.remaining, timedelta(minutes=6))

    async def test_returned_mission_awaits_its_report(self):
        await self.with_ship()
        await missions.begin(*WHO, Kind.RAIDING, 20, 15, NOW)

        started = await missions.begin(
            *WHO, Kind.RAIDING, 99, 99, NOW + timedelta(minutes=10)
        )

        self.assertFalse(started)
        mission = await self.mission()
        self.assertEqual((mission.salary, mission.chance), (20, 15))
        self.assertEqual(mission.cooldown, NOW)

    async def test_mining_and_raiding_are_separate(self):
        await self.with_ship()
        await missions.begin(*WHO, Kind.RAIDING, 20, 15, NOW)

        with self.assertRaises(NoShip):
            await missions.begin(*WHO, Kind.MINING, 20, 15, NOW)

    async def test_get_mission_loads_the_ship(self):
        ship = await self.with_ship()

        mission = await missions.get_mission(*WHO, Kind.RAIDING)

        self.assertEqual(mission.ship.name, ship.name)


class ResolveTest(SimpleTestCase):
    def resolve(self, **overrides) -> Outcome:
        values = {
            "roll": 10,
            "chance": 50,
            "payout": 100,
            "insurance": 500,
            "attack": False,
            "bonus_amount": 60,
            "event": False,
            "event_factor": 2,
        }
        values.update(overrides)
        return missions.resolve(**values)

    def test_success_pays_the_salary(self):
        self.assertEqual(self.resolve(), Outcome(True, 100, 0))

    def test_roll_equal_to_chance_succeeds(self):
        self.assertTrue(self.resolve(roll=50, chance=50).success)

    def test_failure_costs_the_insurance(self):
        self.assertEqual(self.resolve(roll=51), Outcome(False, -500, 0))

    def test_failure_during_an_event_costs_nothing(self):
        self.assertEqual(self.resolve(roll=51, event=True), Outcome(False, 0, 0))

    def test_attack_with_low_chance_adds_the_bonus(self):
        outcome = self.resolve(roll=10, chance=25, attack=True)

        self.assertEqual(outcome, Outcome(True, 160, 0))

    def test_attack_with_higher_chance_pays_eighty_percent(self):
        outcome = self.resolve(roll=10, chance=26, attack=True)

        self.assertEqual(outcome, Outcome(True, 80, 0))

    def test_event_multiplies_and_reports_the_extra(self):
        outcome = self.resolve(event=True, event_factor=1.5, payout=101)

        self.assertEqual(outcome, Outcome(True, 152, 51))

    def test_event_applies_after_the_attack_bonus(self):
        outcome = self.resolve(chance=25, attack=True, event=True, event_factor=2)

        self.assertEqual(outcome, Outcome(True, 320, 160))

    def test_resolve_never_lowers_the_payout_for_a_bad_factor(self):
        for factor in (0, -3, 0.5):
            with self.subTest(factor=factor):
                outcome = self.resolve(event=True, event_factor=factor)

                self.assertEqual(outcome, Outcome(True, 100, 0))


class EventTest(TestCase):
    async def test_event_defaults_to_off_with_factor_two(self):
        self.assertEqual(await missions.get_event(1), Event(False, 2))
        self.assertEqual(
            (missions.MIN_EVENT_FACTOR, missions.MAX_EVENT_FACTOR), (1, 10)
        )

    async def test_set_event_stores_per_guild(self):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.ensure_guild(2, "Beta")

        self.assertEqual(await missions.set_event(1, active=True), Event(True, 2))
        self.assertEqual(await missions.set_event(1, factor=5), Event(True, 5))
        self.assertEqual(await missions.set_event(1, active=False), Event(False, 5))

        self.assertEqual(await missions.get_event(1), Event(False, 5))
        self.assertEqual(await missions.get_event(2), Event(False, 2))

    async def test_factor_outside_one_to_ten_is_refused(self):
        await guilds.ensure_guild(1, "Alpha")
        await missions.set_event(1, active=True, factor=3)

        for factor in (0, -1, 11, 2.5, "3", True):
            with self.subTest(factor=factor):
                with self.assertRaises(InvalidEventFactor) as raised:
                    await missions.set_event(1, active=False, factor=factor)
                self.assertEqual(
                    raised.exception.message,
                    "The event factor must be between 1 and 10.",
                )

        self.assertEqual(await missions.get_event(1), Event(True, 3))

    async def test_set_event_needs_a_registered_guild(self):
        with self.assertRaises(GuildNotRegistered):
            await missions.set_event(99, active=True)


class SettleTest(MissionsTestCase):
    async def flying(self, wallet: int = 0):
        await self.with_ship(wallet)
        await missions.begin(*WHO, Kind.RAIDING, 20, 15, NOW)
        return (await self.mission()).cooldown

    async def test_settle_books_and_starts_the_next_mission(self):
        started_at = await self.flying()
        later = NOW + timedelta(minutes=10)

        applied = await missions.settle(
            *WHO,
            Kind.RAIDING,
            started_at,
            payout=120,
            next_salary=33,
            next_chance=44,
            now=later,
        )

        self.assertEqual(applied, 120)
        self.assertEqual(await self.wallet(), 120)
        mission = await self.mission()
        self.assertEqual((mission.salary, mission.chance), (33, 44))
        self.assertEqual(mission.cooldown, later)
        self.assertTrue(mission.active)

    async def test_mission_is_settled_only_once(self):
        started_at = await self.flying()
        later = NOW + timedelta(minutes=10)
        await missions.settle(
            *WHO,
            Kind.RAIDING,
            started_at,
            payout=120,
            next_salary=33,
            next_chance=44,
            now=later,
        )

        with self.assertRaisesMessage(
            AlreadySettled, "This mission has already been reported."
        ):
            await missions.settle(
                *WHO,
                Kind.RAIDING,
                started_at,
                payout=120,
                next_salary=33,
                next_chance=44,
                now=later,
            )

        self.assertEqual(await self.wallet(), 120)

    async def test_loss_takes_at_most_the_wallet(self):
        started_at = await self.flying(wallet=120)

        applied = await missions.settle(
            *WHO, Kind.RAIDING, started_at, payout=-500, next_salary=33, next_chance=44
        )

        self.assertEqual(applied, -120)
        self.assertEqual(await self.wallet(), 0)

    async def test_zero_payout_still_starts_the_next_mission(self):
        started_at = await self.flying(wallet=50)

        applied = await missions.settle(
            *WHO, Kind.RAIDING, started_at, payout=0, next_salary=33, next_chance=44
        )

        self.assertEqual(applied, 0)
        self.assertEqual((await self.mission()).salary, 33)

    async def test_cancelled_mission_cannot_be_settled(self):
        started_at = await self.flying()
        await missions.cancel(*WHO, Kind.RAIDING)

        with self.assertRaises(AlreadySettled):
            await missions.settle(
                *WHO,
                Kind.RAIDING,
                started_at,
                payout=120,
                next_salary=33,
                next_chance=44,
            )

        self.assertEqual(await self.wallet(), 0)

    async def test_mission_from_before_the_rebuild_can_be_settled(self):
        ship = await self.with_ship()
        profile = await UserProfile.objects.aget(user_id=A)
        old_start = NOW - timedelta(days=3)
        await UserRaidMission.objects.filter(user=profile).aupdate(
            ship=ship, salary=40, chance=20, active=True, cooldown=old_start
        )

        applied = await missions.settle(
            *WHO, Kind.RAIDING, old_start, payout=40, next_salary=33, next_chance=44
        )

        self.assertEqual(applied, 40)


class CancelTest(MissionsTestCase):
    async def test_cancel_resets_the_mission(self):
        await self.with_ship()
        await missions.begin(*WHO, Kind.RAIDING, 20, 15, NOW)

        await missions.cancel(*WHO, Kind.RAIDING)

        mission = await self.mission()
        self.assertFalse(mission.active)
        self.assertIsNone(mission.salary)
        self.assertIsNone(mission.chance)
        self.assertIsNone(mission.cooldown)

    async def test_cancel_without_active_mission(self):
        await self.fund()

        with self.assertRaises(NoActiveMission):
            await missions.cancel(*WHO, Kind.RAIDING)


class BuyShipTest(MissionsTestCase):
    async def test_buying_takes_the_price_and_assigns_the_ship(self):
        await self.fund(1000)
        ship = await self.make_ship()

        bought = await missions.buy_ship(*WHO, Kind.RAIDING, "rifter")

        self.assertEqual(bought.pk, ship.pk)
        self.assertEqual(await self.wallet(), 700)
        self.assertEqual((await self.mission()).ship_id, ship.pk)

    async def test_unknown_inactive_or_wrong_category(self):
        await self.fund(1000)
        await self.make_ship("Venture", category="mining")
        await self.make_ship("Retired", active=False)

        for name in ("Nothing", "Venture", "Retired"):
            with self.subTest(name=name):
                with self.assertRaises(ShipNotFound):
                    await missions.buy_ship(*WHO, Kind.RAIDING, name)

        self.assertEqual(await self.wallet(), 1000)

    async def test_ship_already_owned(self):
        await self.fund(1000)
        await self.make_ship()
        await missions.buy_ship(*WHO, Kind.RAIDING, "Rifter")

        with self.assertRaises(ShipAlreadyOwned):
            await missions.buy_ship(*WHO, Kind.RAIDING, "Rifter")

        self.assertEqual(await self.wallet(), 700)

    async def test_not_enough_money(self):
        await self.fund(299)
        await self.make_ship()

        with self.assertRaises(InsufficientFunds):
            await missions.buy_ship(*WHO, Kind.RAIDING, "Rifter")

        self.assertEqual(await self.wallet(), 299)
        mission = await UserRaidMission.objects.filter(user__user_id=A).afirst()
        self.assertTrue(mission is None or mission.ship_id is None)

    async def test_free_ship(self):
        await self.fund(0)
        await self.make_ship(price=0)

        await missions.buy_ship(*WHO, Kind.RAIDING, "Rifter")

        self.assertIsNotNone((await self.mission()).ship_id)
