# Standard Library
import re
import tomllib
from pathlib import Path

# Django
from django.test import SimpleTestCase

# Demolizzen
import demolizzen

ROOT = Path(demolizzen.__file__).resolve().parents[1]


class ReleaseTest(SimpleTestCase):
    """What a release must not forget."""

    def setUp(self):
        self.changelog = (ROOT / "CHANGELOG.md").read_text("utf-8")
        self.readme = (ROOT / "README.md").read_text("utf-8")
        self.project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))[
            "project"
        ]

    def test_version_has_its_section_in_the_changelog(self):
        heading = (
            rf"^## \[{re.escape(demolizzen.__version__)}\] - \d{{4}}-\d{{2}}-\d{{2}}$"
        )

        self.assertRegex(self.changelog, re.compile(heading, re.MULTILINE))

    def test_changelog_keeps_a_place_for_what_comes_next(self):
        unreleased = self.changelog.index("## [In Development] - Unreleased")
        released = self.changelog.index(f"## [{demolizzen.__version__}]")

        self.assertLess(unreleased, released)

    def test_released_sections_use_the_same_heading_level(self):
        released = self.changelog[
            self.changelog.index(f"## [{demolizzen.__version__}]") :
        ]

        for word in ("Added", "Fixed", "Changed", "Removed"):
            with self.subTest(section=word):
                self.assertNotRegex(released, re.compile(rf"^## {word}$", re.MULTILINE))

    def test_readme_tells_how_to_get_the_bot_running(self):
        # It is the project's front page and the package's description.
        for needed in (
            "pip install",
            ".env",
            "manage.py migrate",
            "python -m demolizzen.launch",
            "/panel",
            "docs/web-panel.md",
        ):
            with self.subTest(needed=needed):
                self.assertIn(needed, self.readme)

    def test_readme_names_the_python_version_the_package_requires(self):
        minimum = self.project["requires-python"].removeprefix(">=")

        self.assertIn(f"Python {minimum}", self.readme)

    def test_package_says_which_django_it_runs_on(self):
        django_floor = next(
            dependency
            for dependency in self.project["dependencies"]
            if dependency.startswith("django>=")
        )
        major_minor = ".".join(django_floor.removeprefix("django>=").split(".")[:2])

        self.assertIn(
            f"Framework :: Django :: {major_minor}", self.project["classifiers"]
        )
