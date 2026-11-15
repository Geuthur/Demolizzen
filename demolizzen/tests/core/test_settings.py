# Django
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

# Demolizzen
from demolizzen import settings as bot_settings
from demolizzen.settings import database_options


class DatabaseOptionsTest(SimpleTestCase):
    def test_nothing_set_changes_nothing(self):
        self.assertEqual(database_options(None, None), {})
        self.assertEqual(database_options("", " "), {})

    def test_required_refuses_unencrypted_connections(self):
        self.assertEqual(database_options("required", None), {"ssl_mode": "REQUIRED"})
        self.assertEqual(
            database_options(" VERIFY_IDENTITY ", None), {"ssl_mode": "VERIFY_IDENTITY"}
        )

    def test_certificate_authority_makes_the_server_prove_itself(self):
        self.assertEqual(
            database_options(None, "/certs/ca.pem"),
            {"ssl_mode": "VERIFY_CA", "ssl": {"ca": "/certs/ca.pem"}},
        )
        self.assertEqual(
            database_options("VERIFY_IDENTITY", "/certs/ca.pem"),
            {"ssl_mode": "VERIFY_IDENTITY", "ssl": {"ca": "/certs/ca.pem"}},
        )

    def test_modes_that_allow_plain_connections_are_passed_on(self):
        self.assertEqual(database_options("disabled", None), {"ssl_mode": "DISABLED"})
        self.assertEqual(database_options("PREFERRED", None), {"ssl_mode": "PREFERRED"})

    def test_misspelt_mode_stops_the_start(self):
        # Better not to start than to run unencrypted without anyone noticing.
        for mode in ("REQUIRE", "yes", "1", "verify"):
            with self.subTest(mode=mode):
                with self.assertRaises(ImproperlyConfigured):
                    database_options(mode, None)

    def test_settings_use_the_options(self):
        self.assertEqual(bot_settings.DATABASES["default"]["OPTIONS"], {})
