# Standard Library
from unittest.mock import patch

# Django
from django.conf import settings
from django.test import Client, TestCase

# Demolizzen
from demolizzen.services import guilds
from demolizzen.tests.web.fakes import FakeDiscord, listed
from demolizzen.web.discord_api import DiscordError


class PanelTestCase(TestCase):
    """Signs in through the real pages with a stand-in for Discord."""

    def setUp(self):
        self.discord = FakeDiscord()
        patcher = patch(
            "demolizzen.web.discord_api.get_client", return_value=self.discord
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.now = 1_000_000.0
        clock = patch("demolizzen.web.session._now", side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)

    def register(self, *guild_ids):
        for guild_id in guild_ids:
            self.run_async(guilds.ensure_guild(guild_id, f"Server {guild_id}"))

    @staticmethod
    def run_async(coroutine):
        # Third Party
        from asgiref.sync import async_to_sync

        async def run():
            return await coroutine

        return async_to_sync(run)()

    def sign_in(self, client=None, **query):
        client = client or self.client
        client.get("/login")
        state = client.session["oauth_state"]
        return client.get("/callback", {"code": "the-code", "state": state, **query})


class LoginTest(PanelTestCase):
    def test_callback_signs_in_and_keeps_manageable_registered_guilds(self):
        self.register(1, 2)
        self.discord.guilds = [
            listed(1),
            listed(2, permissions="0"),
            listed(3, owner=True),
        ]

        response = self.sign_in()

        self.assertRedirects(response, "/", fetch_redirect_response=False)
        session = self.client.session
        self.assertEqual(session["user"], {"id": 10, "name": "Alice"})
        self.assertEqual(session["guild_ids"], [1])
        self.assertNotIn("oauth_state", session)
        self.assertEqual(
            self.discord.calls,
            [("code", "the-code"), ("user", "tok"), ("guilds", "tok")],
        )

    def test_user_without_display_name_is_shown_by_username(self):
        self.discord.user = {"id": "10", "username": "alice", "global_name": None}

        self.sign_in()

        self.assertEqual(self.client.session["user"]["name"], "alice")

    def test_callback_with_wrong_or_missing_state_is_refused(self):
        attempts = [
            {"code": "c", "state": "something-else"},
            {"code": "c"},
            {"state": "x"},
            {"code": "c", "state": "ünïcode"},
        ]
        for query in attempts:
            with self.subTest(query=query):
                self.client.get("/login")
                expected = self.client.session["oauth_state"]
                if query.get("state") == "x":
                    query = {"state": expected}  # right state, no code

                response = self.client.get("/callback", query)

                self.assertContains(response, "could not be verified", status_code=400)
                self.assertNotIn("user", self.client.session)
        self.assertEqual(self.discord.calls, [])

    def test_callback_without_a_started_login_is_refused(self):
        response = Client().get("/callback", {"code": "c", "state": ""})

        self.assertEqual(response.status_code, 400)

    def test_state_works_only_once(self):
        self.client.get("/login")
        state = self.client.session["oauth_state"]
        self.client.get("/callback", {"code": "c", "state": state})
        self.client.post("/logout")

        again = self.client.get("/callback", {"code": "c", "state": state})

        self.assertEqual(again.status_code, 400)

    def test_cancelled_login_says_so(self):
        self.client.get("/login")

        response = self.client.get("/callback", {"error": "access_denied"})

        self.assertContains(response, "Sign-in was not completed.")
        self.assertContains(response, "Sign in with Discord")
        self.assertNotIn("user", self.client.session)

    def test_discord_failure_during_login_says_so(self):
        self.discord.login_error = DiscordError("down")

        response = self.sign_in()

        self.assertContains(response, "Discord did not answer", status_code=502)
        self.assertNotIn("user", self.client.session)

    def test_login_replaces_an_earlier_session(self):
        self.sign_in()
        self.discord.user = {"id": "11", "username": "bob", "global_name": "Bob"}

        self.sign_in()

        self.assertEqual(self.client.session["user"], {"id": 11, "name": "Bob"})

    def test_login_starts_a_fresh_session(self):
        self.client.get("/login")
        store = self.client.session
        store["leftover"] = "from before"
        store.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = store.session_key

        self.client.get(
            "/callback", {"code": "the-code", "state": store["oauth_state"]}
        )

        self.assertIn("user", self.client.session)
        self.assertNotIn("leftover", self.client.session)

    def test_logout_needs_post_and_csrf(self):
        strict = Client(enforce_csrf_checks=True)
        self.sign_in(strict)

        self.assertEqual(strict.get("/logout").status_code, 405)
        refused = strict.post("/logout")
        self.assertContains(refused, "Please go back", status_code=403)
        self.assertIn("user", strict.session)

        strict.get("/")
        token = strict.cookies["csrftoken"].value
        response = strict.post("/logout", {"csrfmiddlewaretoken": token})

        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertNotIn("user", strict.session)
