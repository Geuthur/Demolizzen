# Standard Library
from urllib.parse import parse_qs, urlsplit

# Django
from django.test import SimpleTestCase, override_settings

# Demolizzen
from demolizzen.web import base_settings

CSP = (
    "default-src 'none'; style-src 'self'; form-action 'self'; "
    "base-uri 'none'; frame-ancestors 'none'"
)


class PagesTest(SimpleTestCase):
    def test_healthz_answers_ok(self):
        response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertNotIn("panel_session", response.cookies)

    def test_landing_offers_the_discord_sign_in(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/login"')
        self.assertContains(response, "Sign in with Discord")
        self.assertNotContains(response, "Sign out")
        self.assertContains(response, '<link rel="stylesheet" href="/panel.css">')

    def test_stylesheet_is_served(self):
        response = self.client.get("/panel.css")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/css; charset=utf-8")
        self.assertIn(b"body", response.content)
        self.assertIn("max-age=3600", response["Cache-Control"])

    def test_pages_send_a_content_security_policy(self):
        for path in ("/", "/healthz", "/nowhere"):
            with self.subTest(path=path):
                response = self.client.get(path)

                self.assertEqual(response["Content-Security-Policy"], CSP)
                self.assertEqual(response["X-Frame-Options"], "DENY")
                self.assertEqual(response["X-Content-Type-Options"], "nosniff")
                self.assertEqual(response["Referrer-Policy"], "same-origin")

    @override_settings(DEBUG=False)
    def test_unknown_page_is_404(self):
        response = self.client.get("/nowhere")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "This page does not exist.", status_code=404)
        self.assertContains(response, 'href="/"', status_code=404)

    def test_login_redirects_to_discord_with_a_fresh_state(self):
        first = self.client.get("/login")
        state = self.client.session["oauth_state"]
        second = self.client.get("/login")

        url = urlsplit(first["Location"])
        self.assertEqual(first.status_code, 302)
        self.assertEqual(url.netloc + url.path, "discord.com/oauth2/authorize")
        query = parse_qs(url.query)
        self.assertEqual(query["state"], [state])
        self.assertEqual(query["client_id"], ["123"])
        self.assertEqual(query["redirect_uri"], ["https://panel.example/callback"])
        self.assertGreaterEqual(len(state), 32)
        self.assertNotEqual(
            parse_qs(urlsplit(second["Location"]).query)["state"], [state]
        )

    @override_settings(DISCORD_CLIENT_ID="", DISCORD_CLIENT_SECRET="")
    def test_login_without_configuration_says_so(self):
        response = self.client.get("/login")

        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "Sign-in is not set up yet.", status_code=503)


class SettingsTest(SimpleTestCase):
    def test_allowed_hosts_come_from_the_base_url_and_the_extra_list(self):
        self.assertEqual(
            base_settings.allowed_hosts(
                "https://panel.example:8443/", " a.example, b.example ,"
            ),
            ["panel.example", "a.example", "b.example"],
        )
        self.assertEqual(base_settings.allowed_hosts("", None), [])
        self.assertEqual(base_settings.allowed_hosts(None, "x.example"), ["x.example"])

    def test_session_cookie(self):
        self.assertEqual(
            base_settings.SESSION_ENGINE,
            "django.contrib.sessions.backends.signed_cookies",
        )
        self.assertEqual(base_settings.SESSION_COOKIE_AGE, 7 * 24 * 3600)
        self.assertTrue(base_settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(base_settings.SESSION_COOKIE_SAMESITE, "Lax")

    def test_production_settings(self):
        # Demolizzen
        from demolizzen.web import settings as production

        self.assertEqual(production.ROOT_URLCONF, "demolizzen.web.urls")
        self.assertEqual(production.SESSION_COOKIE_SECURE, not production.DEBUG)
        self.assertEqual(production.CSRF_COOKIE_SECURE, not production.DEBUG)
        self.assertEqual(
            production.SECURE_PROXY_SSL_HEADER, ("HTTP_X_FORWARDED_PROTO", "https")
        )
        self.assertIn("demolizzen", production.INSTALLED_APPS)
