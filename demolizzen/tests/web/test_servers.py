# Django
from django.test import override_settings

# Demolizzen
from demolizzen.services import cog_settings
from demolizzen.tests.web.fakes import listed
from demolizzen.tests.web.test_login import PanelTestCase
from demolizzen.web import session
from demolizzen.web.discord_api import DiscordError, DiscordUnauthorized


class ServersTest(PanelTestCase):
    def setUp(self):
        super().setUp()
        cog_settings.invalidate()
        self.register(1, 2, 3)
        self.discord.guilds = [listed(1), listed(2, owner=True)]

    def guild_requests(self) -> int:
        return self.discord.calls.count(("guilds", "tok"))

    def test_home_lists_the_servers(self):
        self.sign_in()

        response = self.client.get("/")

        self.assertContains(response, 'href="/guilds/1/"')
        self.assertContains(response, "Server 1")
        self.assertContains(response, "Server 2")
        self.assertNotContains(response, "Server 3")
        self.assertContains(response, "Alice")
        self.assertContains(response, "Sign out")
        self.assertNotContains(response, "Sign in with Discord")

    def test_home_without_servers_explains_why(self):
        self.discord.guilds = [listed(3, permissions="0")]
        self.sign_in()

        response = self.client.get("/")

        self.assertContains(response, "No servers to manage")
        self.assertContains(response, "Manage Server")

    def test_guild_page_shows_module_states(self):
        self.run_async(cog_settings.set_enabled(1, "games", False))
        self.sign_in()

        response = self.client.get("/guilds/1/")

        self.assertContains(response, "<h1>Server 1</h1>", html=True)
        modules = {module["key"]: module for module in response.context["modules"]}
        self.assertFalse(modules["games"]["on"])
        self.assertTrue(modules["banksystem"]["on"])
        self.assertTrue(modules["core"]["fixed"])
        self.assertTrue(modules["core"]["on"])
        self.assertEqual(modules["economy"]["title"], "Economy")
        self.assertContains(response, "Always on")
        self.assertContains(response, "Missions and rewards.")

    @override_settings(DEBUG=False)
    def test_foreign_or_unknown_guild_is_404(self):
        self.sign_in()

        for guild_id in (3, 999):
            with self.subTest(guild_id=guild_id):
                response = self.client.get(f"/guilds/{guild_id}/")

                self.assertContains(
                    response, "This page does not exist.", status_code=404
                )
                self.assertNotContains(response, "Server 3", status_code=404)

    def test_pages_need_a_sign_in(self):
        response = self.client.get("/guilds/1/")

        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertEqual(self.discord.calls, [])

    def test_list_is_refreshed_after_five_minutes(self):
        self.sign_in()
        self.assertEqual(self.guild_requests(), 1)

        self.now += session.REFRESH_SECONDS - 1
        self.client.get("/")
        self.client.get("/guilds/1/")
        self.assertEqual(self.guild_requests(), 1)

        self.now += 2
        self.client.get("/")
        self.client.get("/")
        self.assertEqual(self.guild_requests(), 2)
        self.assertEqual(session.REFRESH_SECONDS, 300)

    @override_settings(DEBUG=False)
    def test_withdrawn_rights_remove_the_server(self):
        self.sign_in()
        self.discord.guilds = [listed(1, permissions="0"), listed(2, owner=True)]

        self.now += session.REFRESH_SECONDS + 1
        page = self.client.get("/guilds/1/")
        home = self.client.get("/")

        self.assertEqual(page.status_code, 404)
        self.assertNotContains(home, "Server 1")
        self.assertContains(home, "Server 2")

    def test_rejected_token_signs_out(self):
        self.sign_in()
        self.discord.guilds_error = DiscordUnauthorized("revoked")

        self.now += session.REFRESH_SECONDS + 1
        response = self.client.get("/guilds/1/")

        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertNotIn("user", self.client.session)
        self.assertContains(self.client.get("/"), "Sign in with Discord")

    def test_discord_failure_during_refresh_keeps_the_list(self):
        self.sign_in()
        self.discord.guilds_error = DiscordError("down")

        self.now += session.REFRESH_SECONDS + 1
        response = self.client.get("/guilds/1/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("user", self.client.session)

    def test_list_that_cannot_be_checked_for_too_long_signs_out(self):
        self.sign_in()
        self.discord.guilds_error = DiscordError("rate limited")

        self.now += session.MAX_STALE_SECONDS + 1
        response = self.client.get("/guilds/1/")

        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertNotIn("user", self.client.session)
        self.assertEqual(session.MAX_STALE_SECONDS, 1800)

    def test_server_the_bot_left_disappears(self):
        self.sign_in()
        self.run_async(self.remove(2))

        response = self.client.get("/")

        self.assertNotContains(response, "Server 2")
        self.assertEqual(self.client.get("/guilds/2/").status_code, 404)

    @staticmethod
    async def remove(guild_id: int):
        # Demolizzen
        from demolizzen.services import guilds

        await guilds.remove_guild(guild_id)
