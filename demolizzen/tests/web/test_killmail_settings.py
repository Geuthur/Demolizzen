# Standard Library
from unittest.mock import patch

# Django
from django.test import Client

# Demolizzen
from demolizzen.models import UserProfile
from demolizzen.services import killmails
from demolizzen.tests.web.test_ticket_settings import DirectoryPagesTestCase
from demolizzen.web import eve_names
from demolizzen.web.discord_api import BotTokenMissing
from demolizzen.web.eve_names import EveName

PAGE = "/guilds/1/settings/killmail"
NEW = {"action": "add", "channel": "11", "group": "99000001", "threshold": "1000000"}


class KillmailPageTestCase(DirectoryPagesTestCase):
    def setUp(self):
        super().setUp()
        # What EVE's API knows; the tests never ask the real one.
        self.eve: dict[int, EveName] = {}
        self.eve_asked: list[list[int]] = []
        patcher = patch.object(eve_names, "lookup", self.lookup)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def lookup(self, ids):
        self.eve_asked.append(sorted(ids))
        return {number: self.eve[number] for number in ids if number in self.eve}

    def subscribe(self, channel_id=11, group_id=500, guild_id=1, **kwargs):
        rule, _ = self.run_async(
            killmails.add_subscription(
                guild_id, 7, "owner", channel_id, group_id, **kwargs
            )
        )
        return rule

    def rules(self, guild_id=1):
        return self.run_async(killmails.rules_for_guild(guild_id))

    def listed(self, response) -> list[dict]:
        return response.context["values"]["subscriptions"]

    def refused(self, data, message=None):
        """The form comes back, says why, and nothing was stored or changed."""
        before = self.rules(1), self.rules(2)
        response = self.client.post(PAGE, data)
        self.assertEqual(response.status_code, 400)
        if message:
            self.assertContains(response, message, status_code=400)
        self.assertEqual((self.rules(1), self.rules(2)), before)
        return response


class KillmailListTest(KillmailPageTestCase):
    def test_zkillboard_module_links_to_its_settings(self):
        self.assertContains(
            self.client.get("/guilds/1/"), 'href="/guilds/1/settings/killmail"'
        )

    def test_page_says_so_when_no_channel_receives_killmails(self):
        response = self.client.get(PAGE)

        self.assertContains(response, "<h1>zKillboard settings</h1>", html=True)
        self.assertEqual(self.listed(response), [])
        self.assertContains(response, "No channel receives killmails yet.")

    def test_subscriptions_of_this_server_are_listed(self):
        first = self.subscribe(11, 99000001, threshold=1_000_000, losses=True)
        second = self.subscribe(14, 30000142)
        self.subscribe(91, 777, guild_id=2)

        response = self.client.get(PAGE)

        self.assertEqual(
            [
                (sub["id"], sub["follows"], sub["threshold"], sub["losses"])
                for sub in self.listed(response)
            ],
            [
                (first.id, "99000001", 1_000_000, True),
                (second.id, "30000142", 1, False),
            ],
        )
        self.assertEqual(
            [
                (str(option["value"]), option["label"], option["selected"])
                for option in self.listed(response)[0]["channels"]
            ],
            [("11", "#general (Lobby)", True), ("14", "#ticket-log (Tickets)", False)],
        )
        self.assertNotContains(response, "777")
        self.assertNotContains(response, "other")

    def test_subscription_to_everything_is_named(self):
        self.subscribe(11, killmails.GLOBAL_GROUP_ID)

        self.assertEqual(
            self.listed(self.client.get(PAGE))[0]["follows"], "Every killmail"
        )

    def test_channel_discord_no_longer_lists_is_shown_and_can_be_kept(self):
        rule = self.subscribe(4711, 500)

        page = self.client.get(PAGE)
        options = self.listed(page)[0]["channels"]
        self.assertEqual(
            (options[-1]["value"], options[-1]["label"], options[-1]["selected"]),
            (4711, "Deleted channel (4711)", True),
        )

        self.client.post(
            PAGE,
            {
                "action": "update",
                "subscription": rule.id,
                "channel": "4711",
                "threshold": "9",
            },
        )
        self.assertEqual(
            [(r.channel_id, r.threshold) for r in self.rules()], [(4711, 9)]
        )


class KillmailNamesTest(KillmailPageTestCase):
    """What an id stands for: alliance, corporation, system, … and its name."""

    def shown(self, response) -> list[tuple]:
        return [
            (sub["kind"], sub["name"], sub["follows"]) for sub in self.listed(response)
        ]

    def test_kind_and_name_are_shown_with_the_id(self):
        self.subscribe(11, 99003581)
        self.subscribe(14, 30000142)
        self.subscribe(11, 98000001)
        self.eve = {
            99003581: EveName(99003581, "alliance", "Voices of War"),
            30000142: EveName(30000142, "solar_system", "Jita"),
            98000001: EveName(98000001, "corporation", "Hell Riders"),
        }

        response = self.client.get(PAGE)

        self.assertEqual(
            self.shown(response),
            [
                ("Alliance", "Voices of War", "99003581"),
                ("System", "Jita", "30000142"),
                ("Corporation", "Hell Riders", "98000001"),
            ],
        )
        self.assertContains(response, "Voices of War")
        self.assertContains(response, "Id 99003581")
        # All ids of the page in one question.
        self.assertEqual(self.eve_asked, [[30000142, 98000001, 99003581]])

    def test_id_stands_alone_when_eve_cannot_say_what_it_is(self):
        self.subscribe(11, 424242)

        response = self.client.get(PAGE)

        self.assertEqual(self.shown(response), [(None, None, "424242")])
        self.assertContains(response, "424242")

    def test_subscription_to_everything_is_not_looked_up(self):
        self.subscribe(11, killmails.GLOBAL_GROUP_ID)

        self.assertEqual(
            self.shown(self.client.get(PAGE)), [(None, None, "Every killmail")]
        )
        self.assertEqual(self.eve_asked, [[]])

    def test_kind_killmails_are_never_matched_by_is_pointed_out(self):
        self.subscribe(11, 20000020)
        self.subscribe(14, 99003581)
        self.eve = {
            20000020: EveName(20000020, "constellation", "Kimotoro"),
            99003581: EveName(99003581, "alliance", "Voices of War"),
        }

        response = self.client.get(PAGE)

        self.assertEqual(
            [(sub["kind"], sub["matched"]) for sub in self.listed(response)],
            [("Constellation", False), ("Alliance", True)],
        )
        self.assertContains(response, "never match", count=1)

    def test_name_from_eve_is_shown_as_text_never_as_markup(self):
        self.subscribe(11, 98000001)
        self.eve = {98000001: EveName(98000001, "corporation", "<script>x</script>")}

        response = self.client.get(PAGE)

        self.assertNotContains(response, "<script>x</script>")
        self.assertContains(response, "&lt;script&gt;x&lt;/script&gt;")


class KillmailAddTest(KillmailPageTestCase):
    def test_subscription_is_added_for_the_signed_in_user(self):
        response = self.client.post(PAGE, {**NEW, "losses": "on"})

        self.assertRedirects(response, PAGE, fetch_redirect_response=False)
        (rule,) = self.rules()
        self.assertEqual(
            (rule.channel_id, rule.group_id, rule.threshold, rule.losses),
            (11, 99000001, 1_000_000, True),
        )
        # 10 is the Discord id the panel signed in with.
        self.assertTrue(
            self.run_async(UserProfile.objects.filter(guild_id=1, user_id=10).aexists())
        )
        self.assertContains(self.client.get(PAGE), "Subscription added.")

    def test_empty_threshold_means_every_value(self):
        self.client.post(PAGE, {**NEW, "threshold": ""})

        self.assertEqual(self.rules()[0].threshold, killmails.DEFAULT_THRESHOLD)

    def test_channel_of_another_server_is_refused(self):
        self.refused({**NEW, "channel": "91"}, "not on this server")

    def test_channel_must_be_chosen(self):
        self.refused({**NEW, "channel": ""})

    def test_category_is_no_place_for_killmails(self):
        self.refused({**NEW, "channel": "21"})

    def test_followed_id_must_be_a_positive_number(self):
        for group in ("", "abc", "0", "-5", "1.5", "9" * 13):
            with self.subTest(group=group):
                self.refused({**NEW, "group": group}, "id to follow")

    def test_threshold_must_be_a_sensible_number(self):
        for threshold in (
            "abc",
            "-1",
            "1.5",
            "9" * 19,
            str(killmails.MAX_THRESHOLD + 1),
        ):
            with self.subTest(threshold=threshold):
                self.refused({**NEW, "threshold": threshold}, "ISK threshold")

    def test_channel_cannot_follow_the_same_id_twice(self):
        self.subscribe(11, 99000001)

        self.refused(NEW, "already follows")


class KillmailChangeTest(KillmailPageTestCase):
    def change(self, rule, **data):
        return {"action": "update", "subscription": rule.id, **data}

    def test_channel_threshold_and_losses_are_changed(self):
        rule = self.subscribe(11, 500, threshold=1, losses=True)

        response = self.client.post(
            PAGE, self.change(rule, channel="14", threshold="2500000")
        )

        self.assertRedirects(response, PAGE, fetch_redirect_response=False)
        (changed,) = self.rules()
        self.assertEqual(
            (changed.channel_id, changed.group_id, changed.threshold, changed.losses),
            (14, 500, 2_500_000, False),
        )
        self.assertContains(self.client.get(PAGE), "Subscription saved.")

    def test_subscription_of_another_server_cannot_be_changed_from_here(self):
        foreign = self.subscribe(91, 777, guild_id=2)

        self.refused(
            self.change(foreign, channel="11", threshold="5"), "no longer exists"
        )

    def test_subscription_cannot_be_moved_to_another_servers_channel(self):
        rule = self.subscribe(11, 500)

        self.refused(self.change(rule, channel="91", threshold="5"))

    def test_nonsense_instead_of_a_subscription_is_refused(self):
        for subscription in ("", "abc", "-1", "999999"):
            with self.subTest(subscription=subscription):
                self.refused(
                    {
                        "action": "update",
                        "subscription": subscription,
                        "channel": "11",
                        "threshold": "5",
                    }
                )

    def test_moving_onto_a_channel_that_follows_the_same_id_is_refused(self):
        self.subscribe(14, 500)
        rule = self.subscribe(11, 500)

        self.refused(self.change(rule, channel="14", threshold="5"), "already follows")

    def test_unknown_action_is_refused(self):
        rule = self.subscribe(11, 500)

        self.refused({"action": "explode", "subscription": rule.id})
        self.refused({"subscription": rule.id, "channel": "14", "threshold": "5"})


class KillmailRemoveTest(KillmailPageTestCase):
    def test_subscription_is_removed(self):
        gone = self.subscribe(11, 500)
        kept = self.subscribe(14, 600)

        response = self.client.post(PAGE, {"action": "remove", "subscription": gone.id})

        self.assertRedirects(response, PAGE, fetch_redirect_response=False)
        self.assertEqual(self.rules(), [kept])
        self.assertContains(self.client.get(PAGE), "Subscription removed.")

    def test_subscription_of_another_server_cannot_be_removed_from_here(self):
        foreign = self.subscribe(91, 777, guild_id=2)

        self.refused({"action": "remove", "subscription": foreign.id})

    def test_removing_is_two_steps_without_javascript(self):
        self.subscribe(11, 500)

        response = self.client.get(PAGE)

        self.assertContains(response, "<details")
        self.assertContains(response, 'name="action" value="remove"')


class KillmailWithoutChannelListTest(KillmailPageTestCase):
    def setUp(self):
        super().setUp()
        self.rule = self.subscribe(11, 500, threshold=1)
        self.get_bot_client.side_effect = BotTokenMissing()

    def test_subscriptions_are_still_listed_with_the_channel_id(self):
        response = self.client.get(PAGE)

        (sub,) = self.listed(response)
        self.assertIsNone(sub["channels"])
        self.assertContains(response, "Channel 11")
        self.assertContains(response, "could not be loaded")

    def test_threshold_and_losses_can_be_changed_and_the_channel_stays(self):
        self.client.post(
            PAGE,
            {
                "action": "update",
                "subscription": self.rule.id,
                "channel": "14",
                "threshold": "7",
                "losses": "on",
            },
        )

        (changed,) = self.rules()
        self.assertEqual(
            (changed.channel_id, changed.threshold, changed.losses), (11, 7, True)
        )

    def test_nothing_can_be_added_without_knowing_the_channels(self):
        self.assertFalse(self.client.get(PAGE).context["values"]["has_directory"])
        self.refused(NEW, "could not be loaded")

    def test_removing_still_works(self):
        self.client.post(PAGE, {"action": "remove", "subscription": self.rule.id})

        self.assertEqual(self.rules(), [])


class KillmailPageSafetyTest(KillmailPageTestCase):
    def test_changes_need_the_csrf_token(self):
        strict = Client(enforce_csrf_checks=True)
        self.sign_in(strict)

        response = strict.post(PAGE, NEW)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.rules(), [])

    def test_server_the_user_may_not_manage_has_no_page(self):
        self.assertEqual(
            self.client.get("/guilds/3/settings/killmail").status_code, 404
        )
        self.assertEqual(
            self.client.post("/guilds/3/settings/killmail", NEW).status_code, 404
        )
