# Django
from django.test import Client, override_settings

# Demolizzen
from demolizzen.models import GuildBankSettings
from demolizzen.services import bank, cog_settings, levels, missions
from demolizzen.services.missions import Event
from demolizzen.tests.web.fakes import listed
from demolizzen.tests.web.test_login import PanelTestCase
from demolizzen.web import session

BANK = "/guilds/1/settings/banksystem"
LEVELS = "/guilds/1/settings/levelsystem"
ECONOMY = "/guilds/1/settings/economy"


class SettingsTestCase(PanelTestCase):
    def setUp(self):
        super().setUp()
        cog_settings.invalidate()
        self.register(1, 2, 3)
        self.discord.guilds = [listed(1), listed(2, owner=True)]
        self.sign_in()

    def bank(self, guild_id=1):
        settings = self.run_async(bank.get_settings(guild_id))
        return (
            settings.interest_rate,
            settings.allow_deposits,
            settings.allow_withdrawals,
        )

    def event(self, guild_id=1) -> Event:
        return self.run_async(missions.get_event(guild_id))

    def announces(self, guild_id=1) -> bool:
        return self.run_async(levels.get_announcement(guild_id)).enabled


class SettingsPagesTest(SettingsTestCase):
    def test_modules_with_settings_link_to_their_page(self):
        response = self.client.get("/guilds/1/")

        for key in ("banksystem", "levelsystem", "economy", "ticket"):
            self.assertContains(response, f'href="/guilds/1/settings/{key}"')
        self.assertNotContains(response, 'href="/guilds/1/settings/games"')
        self.assertContains(response, ">Settings</a>", count=4)

    def test_bank_page_shows_the_stored_values(self):
        self.run_async(
            bank.update_settings(1, interest_rate=0.02, allow_withdrawals=False)
        )

        response = self.client.get(BANK)

        self.assertContains(response, "<h1>Banksystem settings</h1>", html=True)
        self.assertEqual(
            [choice["label"] for choice in response.context["values"]["choices"]],
            ["0%", "0.1%", "0.25%", "0.5%", "1%", "2%", "5%", "10%"],
        )
        self.assertContains(
            response, '<option value="2" selected>2%</option>', html=True
        )
        self.assertContains(
            response, '<input type="checkbox" name="allow_deposits" checked>', html=True
        )
        self.assertContains(
            response, '<input type="checkbox" name="allow_withdrawals">', html=True
        )
        self.assertContains(response, 'href="/guilds/1/"')

    def test_bank_settings_are_saved(self):
        response = self.client.post(
            BANK, {"interest": "5", "allow_deposits": "on", "allow_withdrawals": "on"}
        )

        self.assertRedirects(response, BANK, fetch_redirect_response=False)
        self.assertEqual(self.bank(), (0.05, True, True))

    def test_unchecked_boxes_switch_off(self):
        self.client.post(BANK, {"interest": "0.25"})

        self.assertEqual(self.bank(), (0.0025, False, False))

    def test_unusual_stored_interest_is_offered_and_kept(self):
        # A rate set some other way, with more digits than the form shows.
        self.run_async(bank.get_settings(1))
        GuildBankSettings.objects.filter(guild_id=1).update(interest_rate=0.0123456789)

        page = self.client.get(BANK)
        self.assertContains(
            page, '<option value="1.23457" selected>1.23457%</option>', html=True
        )

        self.client.post(BANK, {"interest": "1.23457", "allow_deposits": "on"})
        self.assertEqual(self.bank(), (0.0123456789, True, False))

    def test_interest_outside_the_choices_is_refused(self):
        for value in ("7", "abc", "", "-1", "100", "1e1"):
            with self.subTest(value=value):
                response = self.client.post(
                    BANK, {"interest": value, "allow_deposits": "on"}
                )

                self.assertContains(
                    response,
                    "Choose one of the listed interest rates.",
                    status_code=400,
                )
        self.assertEqual(self.bank(), (0.001, True, True))

    def test_level_announcements_are_saved(self):
        self.assertContains(
            self.client.get(LEVELS),
            '<input type="checkbox" name="announce" checked>',
            html=True,
        )

        self.client.post(LEVELS, {})
        self.assertFalse(self.announces())
        self.assertContains(
            self.client.get(LEVELS),
            '<input type="checkbox" name="announce">',
            html=True,
        )

        self.client.post(LEVELS, {"announce": "on"})
        self.assertTrue(self.announces())

    def test_event_is_saved(self):
        page = self.client.get(ECONOMY)
        self.assertContains(page, '<option value="2" selected>x2</option>', html=True)
        self.assertContains(page, '<input type="checkbox" name="active">', html=True)

        response = self.client.post(ECONOMY, {"active": "on", "factor": "5"})

        self.assertRedirects(response, ECONOMY, fetch_redirect_response=False)
        self.assertEqual(self.event(), Event(True, 5))

        self.client.post(ECONOMY, {"factor": "5"})
        self.assertEqual(self.event(), Event(False, 5))

    def test_factor_outside_one_to_ten_is_refused(self):
        self.client.post(ECONOMY, {"active": "on", "factor": "3"})

        for value in ("0", "11", "x", "", "2.5"):
            with self.subTest(value=value):
                response = self.client.post(ECONOMY, {"factor": value})

                self.assertContains(
                    response,
                    "The event factor must be between 1 and 10.",
                    status_code=400,
                )
        self.assertEqual(self.event(), Event(True, 3))

    def test_saved_notice_is_shown_once(self):
        self.client.post(BANK, {"interest": "1"})

        self.assertContains(self.client.get(BANK), "Banksystem settings saved.")
        self.assertNotContains(self.client.get(BANK), "Banksystem settings saved.")

    def test_other_servers_are_untouched(self):
        self.client.post(BANK, {"interest": "10"})
        self.client.post(ECONOMY, {"active": "on", "factor": "9"})
        self.client.post(LEVELS, {})

        self.assertEqual(self.bank(2), (0.001, True, True))
        self.assertEqual(self.event(2), Event(False, 2))
        self.assertTrue(self.announces(2))

    def test_page_says_when_the_module_is_off(self):
        self.assertNotContains(self.client.get(ECONOMY), "switched off on this server")

        self.client.post("/guilds/1/modules/economy", {"enabled": "0"})

        self.assertContains(
            self.client.get(ECONOMY), "Economy is switched off on this server."
        )


class SettingsAccessTest(SettingsTestCase):
    @override_settings(DEBUG=False)
    def test_module_without_settings_is_404(self):
        for key in ("games", "core", "nonsense"):
            with self.subTest(key=key):
                self.assertEqual(
                    self.client.get(f"/guilds/1/settings/{key}").status_code, 404
                )
                self.assertEqual(
                    self.client.post(f"/guilds/1/settings/{key}", {}).status_code, 404
                )

    @override_settings(DEBUG=False)
    def test_foreign_guild_is_404_and_unchanged(self):
        self.assertEqual(
            self.client.get("/guilds/3/settings/banksystem").status_code, 404
        )
        response = self.client.post("/guilds/3/settings/banksystem", {"interest": "10"})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.bank(3), (0.001, True, True))

    @override_settings(DEBUG=False)
    def test_withdrawn_rights_block_saving(self):
        self.discord.guilds = [listed(1, permissions="0")]
        self.now += session.REFRESH_SECONDS + 1

        response = self.client.post(BANK, {"interest": "10"})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.bank(), (0.001, True, True))

    def test_settings_need_a_sign_in(self):
        anonymous = Client()

        self.assertRedirects(anonymous.get(BANK), "/", fetch_redirect_response=False)
        response = anonymous.post(BANK, {"interest": "10"})

        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertEqual(self.bank(), (0.001, True, True))

    def test_saving_needs_csrf(self):
        strict = Client(enforce_csrf_checks=True)
        self.sign_in(strict)

        refused = strict.post(BANK, {"interest": "10"})
        self.assertEqual(refused.status_code, 403)
        self.assertEqual(self.bank(), (0.001, True, True))

        strict.get(BANK)
        token = strict.cookies["csrftoken"].value
        accepted = strict.post(BANK, {"interest": "10", "csrfmiddlewaretoken": token})
        self.assertEqual(accepted.status_code, 302)
        self.assertEqual(self.bank()[0], 0.1)

    def test_saving_is_logged(self):
        with self.assertLogs("demolizzen.web.views", "INFO") as logs:
            self.client.post(ECONOMY, {"active": "on", "factor": "4"})

        (line,) = logs.output
        self.assertIn("user 10", line)
        self.assertIn("economy settings", line)
        self.assertIn("guild 1", line)
