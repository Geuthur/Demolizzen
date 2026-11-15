# Standard Library
from dataclasses import replace

# Django
from django.test import SimpleTestCase, TestCase

# Demolizzen
from demolizzen.models import UserProfile, ZKillboard
from demolizzen.services import guilds, killmails
from demolizzen.services.errors import (
    DuplicateSubscription,
    InvalidThreshold,
    SubscriptionNotFound,
)
from demolizzen.services.killmails import KillFacts, SubscriptionRule

FACTS = KillFacts(
    killmail_id=1,
    total_value=5_000_000,
    solar_system_id=30000142,
    region_id=10000002,
    victim_corporation_id=100,
    victim_alliance_id=200,
    attacker_corporation_ids=frozenset({300}),
    attacker_alliance_ids=frozenset({400}),
    attacker_character_ids=frozenset({500}),
)


def rule(group_id=None, threshold=None, losses=False) -> SubscriptionRule:
    return SubscriptionRule(
        id=1,
        guild_id=1,
        channel_id=10,
        group_id=group_id,
        threshold=threshold,
        losses=losses,
    )


class MatchesTest(SimpleTestCase):
    def test_global_subscription_matches_everything(self):
        self.assertTrue(killmails.matches(rule(), FACTS))

    def test_threshold(self):
        self.assertTrue(killmails.matches(rule(threshold=5_000_000), FACTS))
        self.assertFalse(killmails.matches(rule(threshold=5_000_001), FACTS))

    def test_kill_without_value_passes_the_threshold(self):
        worthless = replace(FACTS, total_value=0)

        self.assertTrue(killmails.matches(rule(threshold=10**9), worthless))

    def test_system(self):
        self.assertTrue(killmails.matches(rule(30000142), FACTS))

    def test_region(self):
        self.assertTrue(killmails.matches(rule(10000002), FACTS))
        self.assertFalse(
            killmails.matches(rule(10000002), replace(FACTS, region_id=None))
        )

    def test_attackers(self):
        for group_id in (300, 400, 500):
            with self.subTest(group_id=group_id):
                self.assertTrue(killmails.matches(rule(group_id), FACTS))

    def test_victim_only_counts_with_losses(self):
        for group_id in (100, 200):
            with self.subTest(group_id=group_id):
                self.assertFalse(killmails.matches(rule(group_id), FACTS))
                self.assertTrue(killmails.matches(rule(group_id, losses=True), FACTS))

    def test_unrelated_group(self):
        self.assertFalse(killmails.matches(rule(999, losses=True), FACTS))

    def test_threshold_applies_before_the_group(self):
        self.assertFalse(killmails.matches(rule(300, threshold=10**9), FACTS))

    def test_is_loss(self):
        self.assertTrue(killmails.is_loss(rule(100), FACTS))
        self.assertTrue(killmails.is_loss(rule(200), FACTS))
        self.assertFalse(killmails.is_loss(rule(300), FACTS))
        self.assertFalse(killmails.is_loss(rule(), FACTS))


class SubscriptionStoreTest(TestCase):
    async def add(self, channel_id=10, group_id=300, guild_id=1, **kwargs):
        await guilds.ensure_guild(guild_id, f"G{guild_id}")
        return await killmails.add_subscription(
            guild_id, 77, "owner", channel_id, group_id, **kwargs
        )

    async def test_add_creates_the_subscription_and_the_owner(self):
        created_rule, created = await self.add(threshold=1000, losses=True)

        self.assertTrue(created)
        self.assertEqual(
            (created_rule.guild_id, created_rule.channel_id, created_rule.group_id),
            (1, 10, 300),
        )
        self.assertEqual((created_rule.threshold, created_rule.losses), (1000, True))
        self.assertTrue(await UserProfile.objects.filter(user_id=77).aexists())

    async def test_default_threshold(self):
        created_rule, _ = await self.add()

        self.assertEqual(created_rule.threshold, 1)

    async def test_same_channel_and_group_is_not_added_twice(self):
        first, _ = await self.add(threshold=1000)
        await guilds.ensure_members(1, [(78, "other")])

        again, created = await killmails.add_subscription(
            1, 78, "other", 10, 300, threshold=5
        )

        self.assertFalse(created)
        self.assertEqual(again, first)
        self.assertEqual(await ZKillboard.objects.acount(), 1)

    async def test_global_group_six_becomes_none(self):
        created_rule, _ = await self.add(group_id=6)

        self.assertIsNone(created_rule.group_id)
        self.assertIsNone((await killmails.load_rules())[0].group_id)

    async def test_load_and_guild_rules(self):
        await self.add(channel_id=10, group_id=300)
        await self.add(channel_id=11, group_id=301)
        await self.add(channel_id=20, group_id=300, guild_id=2)

        self.assertEqual(len(await killmails.load_rules()), 3)
        self.assertEqual(
            sorted(r.channel_id for r in await killmails.rules_for_guild(1)), [10, 11]
        )

    async def test_remove_subscription_checks_the_guild(self):
        created_rule, _ = await self.add()

        self.assertFalse(await killmails.remove_subscription(created_rule.id, 2))
        self.assertTrue(await killmails.remove_subscription(created_rule.id, 1))
        self.assertFalse(await killmails.remove_subscription(created_rule.id, 1))

    async def test_remove_for_channel_and_guild_return_the_ids(self):
        first, _ = await self.add(channel_id=10, group_id=300)
        second, _ = await self.add(channel_id=10, group_id=301)
        third, _ = await self.add(channel_id=11, group_id=300)

        self.assertEqual(
            sorted(await killmails.remove_for_channel(10)),
            sorted([first.id, second.id]),
        )
        self.assertEqual(await killmails.remove_for_guild(1), [third.id])
        self.assertEqual(await killmails.remove_for_guild(1), [])


class SubscriptionUpdateTest(TestCase):
    """Changing a subscription, as the web panel does."""

    async def asyncSetUp(self):
        await guilds.ensure_guild(1, "Alpha")
        await guilds.ensure_guild(2, "Bravo")

    async def add(self, channel_id=10, group_id=100, guild_id=1, **kwargs):
        rule, _ = await killmails.add_subscription(
            guild_id, 7, "owner", channel_id, group_id, **kwargs
        )
        return rule

    async def test_channel_threshold_and_losses_are_changed(self):
        await self.asyncSetUp()
        rule = await self.add(threshold=5, losses=False)

        changed = await killmails.update_subscription(
            rule.id, 1, channel_id=11, threshold=1_000_000, losses=True
        )

        self.assertEqual(
            (changed.channel_id, changed.threshold, changed.losses),
            (11, 1_000_000, True),
        )
        self.assertEqual(changed.group_id, 100)
        self.assertEqual(await killmails.rules_for_guild(1), [changed])

    async def test_channel_is_kept_when_none_is_given(self):
        await self.asyncSetUp()
        rule = await self.add()

        changed = await killmails.update_subscription(
            rule.id, 1, threshold=9, losses=False
        )

        self.assertEqual(changed.channel_id, 10)
        self.assertEqual(changed.threshold, 9)

    async def test_subscription_of_another_guild_is_not_touched(self):
        await self.asyncSetUp()
        foreign = await self.add(guild_id=2)

        with self.assertRaises(SubscriptionNotFound):
            await killmails.update_subscription(
                foreign.id, 1, channel_id=11, threshold=9, losses=True
            )

        self.assertEqual(await killmails.rules_for_guild(2), [foreign])

    async def test_channel_cannot_follow_the_same_id_twice(self):
        await self.asyncSetUp()
        await self.add(channel_id=11)
        rule = await self.add(channel_id=10)

        with self.assertRaises(DuplicateSubscription):
            await killmails.update_subscription(
                rule.id, 1, channel_id=11, threshold=1, losses=False
            )

        self.assertEqual((await killmails.rules_for_guild(1))[1].channel_id, 10)

    async def test_saving_a_subscription_unchanged_is_no_duplicate(self):
        await self.asyncSetUp()
        rule = await self.add()

        changed = await killmails.update_subscription(
            rule.id, 1, channel_id=10, threshold=rule.threshold, losses=False
        )

        self.assertEqual(changed, rule)

    async def test_threshold_outside_the_limits_is_refused(self):
        await self.asyncSetUp()
        rule = await self.add(threshold=5)

        for threshold in (-1, killmails.MAX_THRESHOLD + 1):
            with self.subTest(threshold=threshold), self.assertRaises(InvalidThreshold):
                await killmails.update_subscription(
                    rule.id, 1, threshold=threshold, losses=False
                )

        self.assertEqual((await killmails.rules_for_guild(1))[0].threshold, 5)

    async def test_new_subscription_checks_the_threshold_too(self):
        await self.asyncSetUp()

        with self.assertRaises(InvalidThreshold):
            await self.add(threshold=killmails.MAX_THRESHOLD + 1)

        self.assertEqual(await killmails.rules_for_guild(1), [])
