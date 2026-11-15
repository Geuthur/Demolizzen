# Standard Library
import io
from contextlib import redirect_stdout
from unittest.mock import patch

# Django
from django.db import OperationalError
from django.test import TestCase, override_settings

# Demolizzen
from demolizzen.web import check

GOOD = {
    "SECRET_KEY": "k" * 50,
    "DISCORD_CLIENT_ID": "4242",
    "DISCORD_CLIENT_SECRET": "client-secret-value",
    "WEB_BASE_URL": "https://panel.example.com",
    "BOT_TOKEN": "bot-token-value",
    "DEBUG": False,
}


def run() -> tuple[int, str]:
    out = io.StringIO()
    with redirect_stdout(out):
        code = check.main()
    return code, out.getvalue()


class CheckTest(TestCase):
    @override_settings(**GOOD)
    def test_everything_in_order(self):
        code, text = run()

        self.assertEqual(code, 0)
        self.assertIn("OK    Database reachable", text)
        self.assertIn("OK    Database is up to date", text)
        self.assertIn("OK    Sign-in with Discord is configured", text)
        self.assertNotIn("FAIL", text)
        # The test database may be reached without TLS; nothing else may warn.
        warnings = [line for line in text.splitlines() if line.startswith("WARN")]
        self.assertTrue(all("not encrypted" in line for line in warnings), warnings)

    @override_settings(**GOOD)
    def test_secrets_are_never_printed(self):
        _, text = run()

        for secret in ("k" * 50, "client-secret-value", "bot-token-value"):
            self.assertNotIn(secret, text)

    @override_settings(**{**GOOD, "DISCORD_CLIENT_ID": "", "DISCORD_CLIENT_SECRET": ""})
    def test_missing_discord_application_fails(self):
        code, text = run()

        self.assertEqual(code, 1)
        self.assertIn("FAIL  DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET", text)

    def test_address_must_be_https(self):
        for url in ("", "http://panel.example.com", "panel.example.com"):
            with (
                self.subTest(url=url),
                override_settings(**{**GOOD, "WEB_BASE_URL": url}),
            ):
                code, text = run()

                self.assertEqual(code, 1)
                self.assertIn("FAIL  WEB_BASE_URL", text)

        with override_settings(
            **{**GOOD, "WEB_BASE_URL": "http://localhost:8000", "DEBUG": True}
        ):
            self.assertEqual(run()[0], 0)

    def test_weak_secret_key_fails(self):
        for key in ("", "short"):
            with (
                self.subTest(key=key),
                override_settings(**{**GOOD, "SECRET_KEY": key}),
            ):
                code, text = run()

                self.assertEqual(code, 1)
                self.assertIn("FAIL  SECRET_KEY", text)

    @override_settings(**{**GOOD, "BOT_TOKEN": ""})
    def test_missing_bot_token_is_only_a_warning(self):
        code, text = run()

        self.assertEqual(code, 0)
        self.assertIn("WARN  BOT_TOKEN is not set", text)

    @override_settings(**GOOD)
    def test_unreachable_database_fails_with_a_hint(self):
        cases = {
            2003: "bind-address",
            2002: "bind-address",
            1045: "not allowed to connect from this address",
            1049: "DATABASE_NAME",
            2026: "TLS",
        }
        for number, hint in cases.items():
            error = OperationalError(
                number, f"problem {number} for 'panel'@'172.18.0.2'"
            )
            with (
                self.subTest(number=number),
                patch.object(check.connection, "ensure_connection", side_effect=error),
            ):
                code, text = run()

                self.assertEqual(code, 1)
                self.assertIn("FAIL  Database not reachable", text)
                self.assertIn(f"problem {number}", text)
                self.assertIn(hint, text)
                self.assertNotIn("up to date", text)

    @override_settings(**GOOD)
    def test_missing_migrations_fail(self):
        with patch.object(
            check, "_pending_migrations", return_value=["0013_x", "0014_y"]
        ):
            code, text = run()

        self.assertEqual(code, 1)
        self.assertIn("FAIL  2 database migrations are missing", text)
        self.assertIn("0013_x, 0014_y", text)

    def test_pending_migrations_of_the_test_database(self):
        self.assertEqual(check._pending_migrations(), [])

    def test_encryption_is_reported(self):
        self.assertEqual(check._encryption_finding("TLS_AES_256_GCM_SHA384")[0], "OK")
        level, text = check._encryption_finding("")
        self.assertEqual(level, "WARN")
        self.assertIn("DATABASE_SSL_MODE=REQUIRED", text)
        self.assertIsNone(check._encryption_finding(None))
