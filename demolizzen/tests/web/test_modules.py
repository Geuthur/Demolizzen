# Django
from django.test import Client, override_settings

# Demolizzen
from demolizzen.services import cog_settings
from demolizzen.tests.web.fakes import listed
from demolizzen.tests.web.test_login import PanelTestCase
from demolizzen.web import session

BANK_FAMILY = ["banksystem", "economy", "shop", "games"]


class ModulesTest(PanelTestCase):
    def setUp(self):
        super().setUp()
        cog_settings.invalidate()
        self.register(1, 2, 3)
        self.discord.guilds = [listed(1), listed(2, owner=True)]
        self.sign_in()

    def switch(self, key, enabled, guild_id=1, client=None, **extra):
        return (client or self.client).post(
            f"/guilds/{guild_id}/modules/{key}",
            {"enabled": "1" if enabled else "0", **extra},
        )

    def on(self, key, guild_id=1) -> bool:
        cog_settings.invalidate()
        return self.run_async(cog_settings.is_enabled(guild_id, key))

    def states(self, keys, guild_id=1) -> list[bool]:
        return [self.on(key, guild_id) for key in keys]

    def test_server_page_offers_a_switch_for_every_switchable_module(self):
        response = self.client.get("/guilds/1/")

        self.assertContains(response, 'action="/guilds/1/modules/games"')
        self.assertContains(response, 'action="/guilds/1/modules/banksystem"')
        self.assertNotContains(response, 'action="/guilds/1/modules/core"')
        self.assertNotContains(response, 'action="/guilds/1/modules/panel"')
        self.assertContains(response, "Switch off")
        self.assertNotContains(response, "Switch on")
        self.assertContains(response, "within a minute")

    def test_switch_off_and_on(self):
        response = self.switch("games", False)

        self.assertRedirects(response, "/guilds/1/", fetch_redirect_response=False)
        self.assertFalse(self.on("games"))
        page = self.client.get("/guilds/1/")
        self.assertContains(page, "Games switched off.")
        self.assertContains(page, "Switch on")

        self.switch("games", True)

        self.assertTrue(self.on("games"))
        self.assertContains(self.client.get("/guilds/1/"), "Games switched on.")

    def test_notice_is_shown_once(self):
        self.switch("games", False)

        self.assertContains(self.client.get("/guilds/1/"), "Games switched off.")
        self.assertNotContains(self.client.get("/guilds/1/"), "Games switched off.")

    def test_switching_off_a_needed_module_asks_first(self):
        response = self.switch("banksystem", False)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Switch off Banksystem?")
        self.assertContains(response, "Economy, Shop and Games need Banksystem")
        self.assertContains(response, 'name="confirm" value="1"')
        self.assertContains(response, 'name="enabled" value="0"')
        self.assertContains(response, 'action="/guilds/1/modules/banksystem"')
        self.assertContains(response, 'href="/guilds/1/"')
        self.assertEqual(self.states(BANK_FAMILY), [True, True, True, True])

    def test_confirming_switches_the_modules_together(self):
        response = self.switch("banksystem", False, confirm="1")

        self.assertRedirects(response, "/guilds/1/", fetch_redirect_response=False)
        self.assertEqual(self.states(BANK_FAMILY), [False, False, False, False])
        self.assertContains(
            self.client.get("/guilds/1/"),
            "Banksystem switched off, together with Economy, Shop and Games.",
        )
        # Other servers keep their own settings.
        self.assertEqual(self.states(BANK_FAMILY, guild_id=2), [True] * 4)

    def test_switching_on_asks_for_the_requirement(self):
        self.switch("banksystem", False, confirm="1")

        response = self.switch("economy", True)

        self.assertContains(response, "Switch on Economy?")
        self.assertContains(response, "Economy needs Banksystem")
        self.assertFalse(self.on("economy"))

        self.switch("economy", True, confirm="1")

        self.assertEqual(self.states(BANK_FAMILY), [True, True, False, False])
        self.assertContains(
            self.client.get("/guilds/1/"),
            "Economy switched on, together with Banksystem.",
        )

    def test_one_dependent_is_named_alone(self):
        self.switch("shop", False)
        self.switch("games", False)

        response = self.switch("banksystem", False)

        self.assertContains(response, "Economy needs Banksystem")

    def test_confirm_without_dependencies_is_a_plain_switch(self):
        self.switch("eveonline", False, confirm="1")

        self.assertFalse(self.on("eveonline"))
        self.assertContains(self.client.get("/guilds/1/"), "EVEOnline switched off.")

    def test_repeating_a_switch_is_harmless(self):
        self.switch("games", False)
        response = self.switch("games", False)

        self.assertRedirects(response, "/guilds/1/", fetch_redirect_response=False)
        self.assertFalse(self.on("games"))

    def test_module_that_is_always_on_cannot_be_switched(self):
        for key in ("core", "panel", "guild", "owner"):
            with self.subTest(key=key):
                response = self.switch(key, False)

                self.assertContains(response, "is always on", status_code=400)

    @override_settings(DEBUG=False)
    def test_unknown_module_is_404(self):
        self.assertEqual(self.switch("nonsense", False).status_code, 404)

    def test_other_values_are_refused(self):
        for data in ({"enabled": "maybe"}, {"enabled": ""}, {}, {"enabled": "true"}):
            with self.subTest(data=data):
                response = self.client.post("/guilds/1/modules/games", data)

                self.assertEqual(response.status_code, 400)
        self.assertTrue(self.on("games"))

    @override_settings(DEBUG=False)
    def test_foreign_guild_is_404_and_unchanged(self):
        for guild_id in (3, 999):
            with self.subTest(guild_id=guild_id):
                response = self.switch("games", False, guild_id=guild_id)

                self.assertEqual(response.status_code, 404)
        self.assertTrue(self.on("games", guild_id=3))

    @override_settings(DEBUG=False)
    def test_withdrawn_rights_block_the_switch(self):
        self.discord.guilds = [listed(1, permissions="0")]
        self.now += session.REFRESH_SECONDS + 1

        response = self.switch("games", False)

        self.assertEqual(response.status_code, 404)
        self.assertTrue(self.on("games"))

    def test_switch_needs_a_sign_in(self):
        response = self.switch("games", False, client=Client())

        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertTrue(self.on("games"))

    def test_switch_needs_post_and_csrf(self):
        self.assertEqual(self.client.get("/guilds/1/modules/games").status_code, 405)

        strict = Client(enforce_csrf_checks=True)
        self.sign_in(strict)
        refused = self.switch("games", False, client=strict)
        self.assertEqual(refused.status_code, 403)
        self.assertTrue(self.on("games"))

        strict.get("/guilds/1/")
        token = strict.cookies["csrftoken"].value
        accepted = self.switch("games", False, client=strict, csrfmiddlewaretoken=token)
        self.assertEqual(accepted.status_code, 302)
        self.assertFalse(self.on("games"))

    def test_switch_is_logged(self):
        with self.assertLogs("demolizzen.web.views", "INFO") as logs:
            self.switch("banksystem", False, confirm="1")

        (line,) = logs.output
        self.assertIn("user 10", line)
        self.assertIn("guild 1", line)
        self.assertIn("banksystem, economy, shop, games", line)
        self.assertIn("off", line)
