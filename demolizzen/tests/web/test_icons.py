# Standard Library
import re
from pathlib import Path

# Django
from django.template import Context, Template, TemplateSyntaxError
from django.test import SimpleTestCase

# Demolizzen
from demolizzen.core import registry
from demolizzen.tests.web.fakes import listed
from demolizzen.tests.web.test_login import PanelTestCase
from demolizzen.web import icons

WEB = Path(icons.__file__).resolve().parent


class IconTagTest(SimpleTestCase):
    def render(self, source: str) -> str:
        return Template(source).render(Context())

    def test_icon_is_drawn_into_the_page_itself(self):
        # The content security policy lets the panel load no icon font or
        # sprite from anywhere; markup in the page needs no permission.
        html = self.render('{% icon "power" %}')

        self.assertTrue(html.startswith("<svg"))
        self.assertIn("<path", html)
        self.assertNotIn("<script", html)
        self.assertNotIn("http://www.w3.org/2000/svg", html)  # not needed inline

    def test_icon_is_decoration_for_screen_readers(self):
        # The text next to it says what the control does.
        html = self.render('{% icon "power" %}')

        self.assertIn('aria-hidden="true"', html)
        self.assertIn('focusable="false"', html)

    def test_icon_takes_colour_and_size_from_the_text_around_it(self):
        html = self.render('{% icon "power" %}')

        self.assertIn('fill="currentColor"', html)
        self.assertIn('class="bi"', html)
        self.assertNotRegex(html, r'\s(width|height)="')

    def test_unknown_icon_fails_loudly_instead_of_leaving_a_hole(self):
        with self.assertRaises(TemplateSyntaxError):
            self.render('{% icon "no-such-icon" %}')

    def test_every_icon_a_template_names_is_shipped(self):
        named = set()
        for template in (WEB / "templates").rglob("*.html"):
            named |= set(re.findall(r'{% icon "([^"]+)" %}', template.read_text()))

        self.assertTrue(named)
        self.assertEqual(named - set(icons.ICONS), set())

    def test_every_module_has_an_icon(self):
        for key in registry.REGISTRY:
            with self.subTest(module=key):
                self.assertIn(icons.module_icon(key), icons.ICONS)

    def test_licence_of_the_icons_is_shipped_with_them(self):
        licence = (WEB / "static" / "icons" / "LICENSE.txt").read_text()

        self.assertIn("MIT License", licence)
        self.assertIn("Bootstrap", licence)


class IconsOnPagesTest(PanelTestCase):
    def setUp(self):
        super().setUp()
        self.register(1)
        self.discord.guilds = [listed(1)]
        self.sign_in()

    def test_module_state_is_a_badge_with_icon_and_word(self):
        self.client.post("/guilds/1/modules/games", {"enabled": "0"})

        response = self.client.get("/guilds/1/")

        self.assertContains(response, '<span class="badge on">', count=10)
        self.assertContains(response, '<span class="badge off">', count=1)
        # Never colour alone: the word is in the badge.
        self.assertRegex(
            response.content.decode(),
            r'<span class="badge off"><svg[^>]*>.*?</svg>\s*Off</span>',
        )

    def test_every_module_shows_its_own_icon(self):
        response = self.client.get("/guilds/1/")

        self.assertContains(
            response, '<span class="glyph', count=len(registry.REGISTRY)
        )

    def test_buttons_carry_an_icon_and_keep_their_words(self):
        page = self.client.get("/guilds/1/").content.decode()

        for words in ("Switch off", "Settings", "Sign out"):
            with self.subTest(words=words):
                self.assertRegex(page, rf"<svg[^>]*>.*?</svg>\s*(<span>)?{words}")
