# Standard Library
import zlib

# Django
from django.core import signing
from django.test import SimpleTestCase, override_settings

# Demolizzen
from demolizzen.tests.web.test_login import PanelTestCase
from demolizzen.web import base_settings
from demolizzen.web.crypto import EncryptedJSONSerializer

SESSION = {"user": {"id": 10, "name": "Alice"}, "token": "discord-access-token-123"}


class EncryptedSerializerTest(SimpleTestCase):
    def test_round_trip(self):
        serializer = EncryptedJSONSerializer()

        self.assertEqual(serializer.loads(serializer.dumps(SESSION)), SESSION)

    def test_content_cannot_be_read(self):
        data = EncryptedJSONSerializer().dumps(SESSION)

        self.assertIsInstance(data, bytes)
        self.assertNotIn(b"discord-access-token", data)
        self.assertNotIn(b"Alice", data)
        self.assertNotIn(b"token", data)

    def test_same_content_looks_different_every_time(self):
        serializer = EncryptedJSONSerializer()

        self.assertNotEqual(serializer.dumps(SESSION), serializer.dumps(SESSION))

    def test_another_secret_key_cannot_read_it(self):
        data = EncryptedJSONSerializer().dumps(SESSION)

        with override_settings(SECRET_KEY="a-completely-different-key"):
            with self.assertRaises(Exception):
                EncryptedJSONSerializer().loads(data)
            other = EncryptedJSONSerializer().dumps(SESSION)
            self.assertEqual(EncryptedJSONSerializer().loads(other), SESSION)

    def test_changed_content_is_rejected(self):
        data = bytearray(EncryptedJSONSerializer().dumps(SESSION))
        data[20] = data[20] ^ 1

        with self.assertRaises(Exception):
            EncryptedJSONSerializer().loads(bytes(data))

    def test_sessions_use_it(self):
        self.assertEqual(
            base_settings.SESSION_SERIALIZER,
            "demolizzen.web.crypto.EncryptedJSONSerializer",
        )


class SessionCookieTest(PanelTestCase):
    def cookie_payload(self) -> bytes:
        """What anyone holding the cookie can decode without the key."""
        value = self.client.cookies["panel_session"].value.split(":")[0]
        compressed = value.startswith(".")
        data = signing.b64_decode(value.lstrip(".").encode())
        return zlib.decompress(data) if compressed else data

    def test_cookie_reveals_neither_token_nor_name(self):
        self.discord.token = "discord-access-token-123"
        self.register(1)

        self.sign_in()

        payload = self.cookie_payload()
        self.assertNotIn(b"discord-access-token", payload)
        self.assertNotIn(b"Alice", payload)
        self.assertNotIn(b"guild_ids", payload)
        # The panel itself still reads it.
        self.assertEqual(self.client.session["token"], "discord-access-token-123")
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_cookie_changed_by_the_visitor_is_no_session(self):
        self.sign_in()
        cookie = self.client.cookies["panel_session"]
        cookie.set("panel_session", cookie.value[:-2] + "xx", cookie.value[:-2] + "xx")

        response = self.client.get("/")

        self.assertContains(response, "Sign in with Discord")
