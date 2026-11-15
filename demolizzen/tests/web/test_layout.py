# Demolizzen
from demolizzen.services import cog_settings
from demolizzen.tests.web.fakes import listed
from demolizzen.tests.web.test_login import PanelTestCase


class LayoutTest(PanelTestCase):
    def setUp(self):
        super().setUp()
        cog_settings.invalidate()
        self.register(1, 2, 3)
        self.discord.guilds = [listed(1), listed(2, owner=True)]
        self.sign_in()

    def test_font_is_served(self):
        response = self.client.get("/exo2.woff2")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "font/woff2")
        self.assertTrue(response.content.startswith(b"wOF2"))
        self.assertIn("max-age=604800", response["Cache-Control"])
        self.assertIn(b"/exo2.woff2", self.client.get("/panel.css").content)

    def test_server_rail_lists_servers_and_marks_the_current_one(self):
        response = self.client.get("/guilds/2/")

        self.assertEqual(
            response.context["servers"],
            [
                {"id": 1, "name": "Server 1", "current": False},
                {"id": 2, "name": "Server 2", "current": True},
            ],
        )
        self.assertContains(
            response, '<a href="/guilds/2/" aria-current="page">Server 2</a>', html=True
        )
        self.assertContains(response, '<a href="/guilds/1/">Server 1</a>', html=True)
        self.assertNotContains(response, "Server 3")

    def test_confirmation_page_keeps_the_rail(self):
        response = self.client.post("/guilds/1/modules/banksystem", {"enabled": "0"})

        self.assertContains(
            response, '<a href="/guilds/1/" aria-current="page">Server 1</a>', html=True
        )

    def test_dependent_modules_name_what_they_need(self):
        response = self.client.get("/guilds/1/")

        modules = {module["key"]: module for module in response.context["modules"]}
        self.assertEqual(modules["economy"]["needs"], "Banksystem")
        self.assertEqual(modules["banksystem"]["needs"], "")
        self.assertContains(response, "Needs Banksystem", count=3)

    def test_summary_counts_switchable_modules(self):
        self.client.post("/guilds/1/modules/games", {"enabled": "0"})

        response = self.client.get("/guilds/1/")

        self.assertEqual(response.context["tally"], {"on": 10, "total": 11})
        self.assertContains(response, "10 of 11 modules on")
        # One segment per switchable module, lit while it is on.
        self.assertContains(response, 'class="seg on"', count=10)
        self.assertContains(response, 'class="seg"', count=1)

    def test_always_on_modules_are_listed_apart(self):
        response = self.client.get("/guilds/1/")

        html = response.content.decode()
        self.assertIn("Always on", html)
        fixed = html[html.index("Always on") :]
        for title in ("Core", "Owner", "Guild", "Panel"):
            self.assertIn(title, fixed)
        self.assertNotIn("Switch off", fixed)

    def test_home_shows_module_counts_per_server(self):
        self.client.post("/guilds/1/modules/games", {"enabled": "0"})

        response = self.client.get("/")

        self.assertEqual(
            response.context["servers"],
            [
                {"id": 1, "name": "Server 1", "current": False, "on": 10, "total": 11},
                {"id": 2, "name": "Server 2", "current": False, "on": 11, "total": 11},
            ],
        )
        self.assertContains(response, "10 of 11 modules on")

    def test_landing_has_no_server_rail(self):
        self.client.post("/logout")

        response = self.client.get("/")

        self.assertNotContains(response, 'aria-label="Servers"')
