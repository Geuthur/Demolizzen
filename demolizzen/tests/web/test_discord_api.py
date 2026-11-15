# Standard Library
import json
from urllib.parse import parse_qs, urlsplit

# Third Party
import aiohttp

# Django
from django.test import SimpleTestCase, override_settings

# Demolizzen
from demolizzen.web import discord_api
from demolizzen.web.discord_api import (
    DiscordClient,
    DiscordError,
    DiscordUnauthorized,
)


class Answer:
    def __init__(self, status=200, data=None, error=None, broken=False):
        self.status = status
        self._data = data
        self._error = error
        self._broken = broken

    async def __aenter__(self):
        if self._error is not None:
            raise self._error
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def json(self, **kwargs):
        if self._broken:
            raise json.JSONDecodeError("bad", "{", 0)
        return self._data


class FakeSession:
    """Stands in for aiohttp.ClientSession and remembers the requests."""

    def __init__(self, answer):
        self.answer = answer
        self.requests = []

    def __call__(self, **kwargs):
        self.session_options = kwargs
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    def get(self, url, **kwargs):
        self.requests.append(("GET", url, kwargs))
        return self.answer

    def post(self, url, **kwargs):
        self.requests.append(("POST", url, kwargs))
        return self.answer


class DiscordClientTest(SimpleTestCase):
    def make(self, answer=None) -> DiscordClient:
        self.http = FakeSession(answer or Answer())
        return DiscordClient(
            "123", "secret", "https://panel.example/callback", session_factory=self.http
        )

    def test_authorize_url_carries_client_scopes_redirect_and_state(self):
        url = urlsplit(self.make().authorize_url("abc"))

        self.assertEqual(
            f"{url.scheme}://{url.netloc}{url.path}",
            "https://discord.com/oauth2/authorize",
        )
        self.assertEqual(
            parse_qs(url.query),
            {
                "response_type": ["code"],
                "client_id": ["123"],
                "scope": ["identify guilds"],
                "redirect_uri": ["https://panel.example/callback"],
                "state": ["abc"],
                "prompt": ["none"],
            },
        )
        self.assertNotIn("secret", url.query)

    async def test_exchange_code_posts_the_form_and_returns_the_token(self):
        client = self.make(Answer(data={"access_token": "tok", "expires_in": 604800}))

        self.assertEqual(await client.exchange_code("the-code"), "tok")

        ((method, url, kwargs),) = self.http.requests
        self.assertEqual(
            (method, url), ("POST", "https://discord.com/api/oauth2/token")
        )
        self.assertEqual(
            kwargs["data"],
            {
                "grant_type": "authorization_code",
                "code": "the-code",
                "redirect_uri": "https://panel.example/callback",
                "client_id": "123",
                "client_secret": "secret",
            },
        )
        self.assertNotIn("json", kwargs)
        self.assertEqual(self.http.session_options["timeout"].total, 10)

    async def test_user_and_guilds_are_fetched_with_the_bearer_token(self):
        client = self.make(Answer(data={"id": "10", "username": "alice"}))
        self.assertEqual(
            await client.fetch_user("tok"), {"id": "10", "username": "alice"}
        )
        method, url, kwargs = self.http.requests[0]
        self.assertEqual(
            (method, url), ("GET", "https://discord.com/api/v10/users/@me")
        )
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer tok")

        client = self.make(Answer(data=[{"id": "1"}]))
        self.assertEqual(await client.fetch_guilds("tok"), [{"id": "1"}])
        self.assertEqual(
            self.http.requests[0][1], "https://discord.com/api/v10/users/@me/guilds"
        )

    async def test_401_is_unauthorized(self):
        client = self.make(Answer(status=401, data={"message": "401: Unauthorized"}))

        with self.assertRaises(DiscordUnauthorized):
            await client.fetch_guilds("tok")
        with self.assertRaises(DiscordUnauthorized):
            await client.fetch_user("tok")

    async def test_other_errors_timeouts_and_bad_answers_are_discord_errors(self):
        answers = {
            "rate limited": Answer(status=429, data={"retry_after": 1}),
            "server error": Answer(status=503),
            "timeout": Answer(error=TimeoutError()),
            "connection": Answer(error=aiohttp.ClientConnectionError("down")),
            "broken json": Answer(broken=True),
            "wrong shape": Answer(data={"not": "a list"}),
        }
        for name, answer in answers.items():
            with self.subTest(case=name):
                with self.assertRaises(DiscordError) as raised:
                    await self.make(answer).fetch_guilds("tok")
                self.assertNotIsInstance(raised.exception, DiscordUnauthorized)

    async def test_user_without_id_is_a_discord_error(self):
        with self.assertRaises(DiscordError):
            await self.make(Answer(data={"username": "alice"})).fetch_user("tok")

    async def test_refused_code_is_a_discord_error(self):
        answers = [
            Answer(status=400, data={"error": "invalid_grant"}),
            Answer(status=401, data={"error": "invalid_client"}),
            Answer(data={"token_type": "Bearer"}),
            Answer(data={"access_token": ""}),
        ]
        for answer in answers:
            with self.subTest(status=answer.status):
                with self.assertRaises(DiscordError):
                    await self.make(answer).exchange_code("the-code")

    @override_settings(
        DISCORD_CLIENT_ID="55",
        DISCORD_CLIENT_SECRET="s3",
        WEB_BASE_URL="https://panel.example",
    )
    def test_get_client_uses_the_settings(self):
        url = discord_api.get_client().authorize_url("x")

        self.assertIn("client_id=55", url)
        self.assertIn("redirect_uri=https%3A%2F%2Fpanel.example%2Fcallback", url)
