# Standard Library
import re
from pathlib import Path

# Django
from django.test import SimpleTestCase

PACKAGE = Path(__file__).resolve().parents[1]
# Modules that are not loaded and belong to single German-speaking servers.
SKIPPED = ("cogs/geuthur/", "cogs/vow/", "cogs/automod/", "cogs/token/", "tests/")
GERMAN = re.compile(r"[äöüßÄÖÜ]")


class LanguageTest(SimpleTestCase):
    """English is the bot's language: texts, log lines and comments."""

    def test_no_german_text_in_the_code(self):
        found = []
        for path in sorted(PACKAGE.rglob("*.py")):
            relative = path.relative_to(PACKAGE).as_posix()
            if relative.startswith(SKIPPED) or "/migrations/" in f"/{relative}":
                continue
            for number, line in enumerate(path.read_text("utf-8").splitlines(), 1):
                if GERMAN.search(line):
                    found.append(f"{relative}:{number}")

        self.assertEqual(found, [])
