# Standard Library
from unittest.mock import patch

# Django
from django.test import override_settings

# Demolizzen
from demolizzen.models import GuildTicketSettings
from demolizzen.services import cog_settings, guilds, levels, tickets
from demolizzen.tests.web.fakes import FakeBot, channel, listed, role
from demolizzen.tests.web.test_login import PanelTestCase
from demolizzen.web import directory
from demolizzen.web.discord_api import BotTokenMissing, DiscordError

TICKET = "/guilds/1/settings/ticket"
LEVELS = "/guilds/1/settings/levelsystem"
BANK = "/guilds/1/settings/banksystem"

FULL = {
    "category": "21",
    "archive_category": "22",
    "log_channel": "14",
    "roles": ["52", "53"],
    "allow_user_close": "on",
    "auto_archive_days": "14",
    "max_open_tickets": "3",
}


class DirectoryPagesTestCase(PanelTestCase):
    def setUp(self):
        super().setUp()
        cog_settings.invalidate()
        directory.clear()
        self.register(1, 2)
        self.discord.guilds = [listed(1), listed(2, owner=True)]
        self.bot = FakeBot()
        self.bot.channels[1] = [
            channel(20, "Lobby", kind=4, position=0),
            channel(21, "Tickets", kind=4, position=1),
            channel(22, "Archive", kind=4, position=2),
            channel(11, "general", position=0, parent=20),
            channel(14, "ticket-log", position=0, parent=21),
        ]
        self.bot.roles[1] = [
            role(1, "@everyone", position=0),
            role(52, "Admin", position=5),
            role(53, "Moderator", position=3),
        ]
        # Another server's channels and roles must never be accepted for server 1.
        self.bot.channels[2] = [channel(90, "Elsewhere", kind=4), channel(91, "other")]
        self.bot.roles[2] = [role(95, "Stranger")]
        patcher = patch(
            "demolizzen.web.discord_api.get_bot_client", side_effect=lambda: self.bot
        )
        self.get_bot_client = patcher.start()
        self.addCleanup(patcher.stop)
        self.sign_in()

    def stored(self, guild_id=1) -> dict:
        settings = self.run_async(tickets.get_settings(guild_id))
        return {
            "category": settings.category_id,
            "archive": settings.archive_category_id,
            "log": settings.log_channel_id,
            "roles": tickets.staff_role_ids(settings),
            "close": settings.allow_user_close,
            "reopen": settings.allow_user_reopen,
            "days": settings.auto_archive_days,
            "open": settings.max_open_tickets,
        }

    def options(self, response, name) -> list[tuple[str, str, bool]]:
        return [
            (str(option["value"]), option["label"], option["selected"])
            for option in response.context["values"][name]
        ]


class TicketSettingsTest(DirectoryPagesTestCase):
    def test_ticket_module_links_to_its_settings(self):
        self.assertContains(
            self.client.get("/guilds/1/"), 'href="/guilds/1/settings/ticket"'
        )

    def test_ticket_page_offers_channels_and_roles(self):
        response = self.client.get(TICKET)

        self.assertContains(response, "<h1>Ticket System settings</h1>", html=True)
        self.assertEqual(
            self.options(response, "categories"),
            [
                ("", "Not set", True),
                ("20", "Lobby", False),
                ("21", "Tickets", False),
                ("22", "Archive", False),
            ],
        )
        self.assertEqual(self.options(response, "archive_categories")[0][1], "None")
        self.assertEqual(
            self.options(response, "log_channels"),
            [
                ("", "None", True),
                ("11", "#general (Lobby)", False),
                ("14", "#ticket-log (Tickets)", False),
            ],
        )
        self.assertEqual(
            [
                (r["value"], r["label"], r["checked"])
                for r in response.context["values"]["roles"]
            ],
            [(52, "Admin", False), (53, "Moderator", False)],
        )
        self.assertNotContains(response, "@everyone")
        self.assertNotContains(response, "Elsewhere")

    def test_ticket_settings_are_saved(self):
        response = self.client.post(TICKET, FULL)

        self.assertRedirects(response, TICKET, fetch_redirect_response=False)
        self.assertEqual(
            self.stored(),
            {
                "category": 21,
                "archive": 22,
                "log": 14,
                "roles": [52, 53],
                "close": True,
                "reopen": False,
                "days": 14,
                "open": 3,
            },
        )
        page = self.client.get(TICKET)
        self.assertContains(page, "Ticket System settings saved.")
        self.assertIn(("21", "Tickets", True), self.options(page, "categories"))
        self.assertEqual(
            [r["checked"] for r in page.context["values"]["roles"]], [True, True]
        )

    def test_optional_channels_can_be_cleared(self):
        self.client.post(TICKET, FULL)

        self.client.post(TICKET, {**FULL, "archive_category": "", "log_channel": ""})

        stored = self.stored()
        self.assertEqual((stored["archive"], stored["log"]), (None, None))
        self.assertEqual(stored["category"], 21)

    def test_ids_discord_did_not_list_are_refused(self):
        attempts = [
            {"category": "90"},  # a category of another server
            {"category": "11"},  # a text channel is no category
            {"archive_category": "999"},
            {"log_channel": "21"},  # a category is no text channel
            {"log_channel": "91"},
            {"roles": ["52", "95"]},  # a role of another server
            {"roles": ["1"]},  # @everyone
            {"category": "abc"},
            {"roles": ["x"]},
        ]
        for change in attempts:
            with self.subTest(change=change):
                response = self.client.post(TICKET, {**FULL, **change})

                self.assertEqual(response.status_code, 400)
                self.assertContains(response, "not on this server", status_code=400)
        self.assertEqual(self.stored()["category"], None)
        self.assertEqual(self.stored()["roles"], [])

    def test_more_than_25_roles_are_refused(self):
        self.bot.roles[1] = [role(100 + n, f"R{n}") for n in range(30)]

        response = self.client.post(
            TICKET, {**FULL, "roles": [str(100 + n) for n in range(26)]}
        )

        self.assertContains(response, "Choose at most 25 staff roles.", status_code=400)
        self.assertEqual(self.stored()["roles"], [])

    def test_limits_outside_the_choices_are_refused(self):
        for change in (
            {"auto_archive_days": "2"},
            {"auto_archive_days": ""},
            {"max_open_tickets": "4"},
            {"max_open_tickets": "x"},
        ):
            with self.subTest(change=change):
                response = self.client.post(TICKET, {**FULL, **change})

                self.assertContains(
                    response, "Choose one of the listed values.", status_code=400
                )
        self.assertEqual(self.stored()["category"], None)

    def test_deleted_channel_and_role_are_shown_and_kept(self):
        self.run_async(
            tickets.update_settings(
                1, category_id=777, log_channel_id=778, roles=[52, 779]
            )
        )

        page = self.client.get(TICKET)
        self.assertIn(
            ("777", "Deleted category (777)", True), self.options(page, "categories")
        )
        self.assertIn(
            ("778", "Deleted channel (778)", True), self.options(page, "log_channels")
        )
        self.assertIn(
            (779, "Deleted role (779)", True),
            [
                (r["value"], r["label"], r["checked"])
                for r in page.context["values"]["roles"]
            ],
        )

        response = self.client.post(
            TICKET,
            {**FULL, "category": "777", "log_channel": "778", "roles": ["52", "779"]},
        )

        self.assertRedirects(response, TICKET, fetch_redirect_response=False)
        stored = self.stored()
        self.assertEqual(stored["days"], 14)
        self.assertEqual((stored["category"], stored["log"]), (777, 778))
        self.assertEqual(stored["roles"], [52, 779])

    def test_page_says_what_is_missing_to_open_tickets(self):
        self.assertContains(
            self.client.get(TICKET),
            "Members can open tickets once a ticket category and at least one staff role are set.",
        )

        self.client.post(TICKET, FULL)

        self.assertNotContains(self.client.get(TICKET), "Members can open tickets once")

    def test_without_discord_the_other_settings_still_save(self):
        self.client.post(TICKET, FULL)
        directory.clear()
        self.bot.error = DiscordError("down")

        page = self.client.get(TICKET)
        self.assertContains(
            page, "Channels and roles could not be loaded from Discord."
        )
        self.assertNotContains(page, 'name="category"')
        self.assertNotContains(page, 'name="roles"')
        self.assertContains(page, 'name="auto_archive_days"')

        response = self.client.post(
            TICKET,
            {
                "allow_user_reopen": "on",
                "auto_archive_days": "30",
                "max_open_tickets": "5",
            },
        )

        self.assertRedirects(response, TICKET, fetch_redirect_response=False)
        self.assertEqual(
            self.stored(),
            {
                "category": 21,
                "archive": 22,
                "log": 14,
                "roles": [52, 53],
                "close": False,
                "reopen": True,
                "days": 30,
                "open": 5,
            },
        )

    def test_missing_bot_token_is_explained(self):
        self.get_bot_client.side_effect = BotTokenMissing("none")

        page = self.client.get(TICKET)

        self.assertContains(page, "BOT_TOKEN")
        self.assertContains(page, 'name="max_open_tickets"')

    def test_other_servers_keep_their_ticket_settings(self):
        self.client.post(TICKET, FULL)

        self.assertEqual(self.stored(2)["category"], None)
        self.assertEqual(GuildTicketSettings.objects.filter(guild_id=1).count(), 1)

    @override_settings(DEBUG=False)
    def test_foreign_guild_gets_no_directory(self):
        self.register(3)
        self.bot.calls.clear()

        response = self.client.get("/guilds/3/settings/ticket")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.bot.calls, [])


class LevelChannelTest(DirectoryPagesTestCase):
    def channel(self, guild_id=1):
        return self.run_async(guilds.get_main_channel(guild_id))

    def test_level_channel_is_saved(self):
        page = self.client.get(LEVELS)
        self.assertEqual(
            self.options(page, "channels"),
            [
                ("", "System channel", True),
                ("11", "#general (Lobby)", False),
                ("14", "#ticket-log (Tickets)", False),
            ],
        )

        self.client.post(LEVELS, {"announce": "on", "channel": "11"})
        self.assertEqual(self.channel(), 11)
        self.assertTrue(self.run_async(levels.get_announcement(1)).enabled)

        self.client.post(LEVELS, {"announce": "on", "channel": ""})
        self.assertIsNone(self.channel())

    def test_level_channel_not_listed_is_refused(self):
        for value in ("91", "21", "999", "abc"):
            with self.subTest(value=value):
                # Announcements unchecked: a refused form must not switch them off.
                response = self.client.post(LEVELS, {"channel": value})

                self.assertContains(response, "not on this server", status_code=400)
        self.assertIsNone(self.channel())
        self.assertTrue(self.run_async(levels.get_announcement(1)).enabled)

    def test_level_page_without_discord_still_saves_announcements(self):
        self.client.post(LEVELS, {"announce": "on", "channel": "11"})
        directory.clear()
        self.bot.error = DiscordError("down")

        page = self.client.get(LEVELS)
        self.assertNotContains(page, 'name="channel"')
        self.client.post(LEVELS, {})

        self.assertFalse(self.run_async(levels.get_announcement(1)).enabled)
        self.assertEqual(self.channel(), 11)

    def test_bank_page_does_not_ask_discord(self):
        self.client.get(BANK)
        self.client.post(BANK, {"interest": "1"})

        self.assertEqual(self.bot.calls, [])
