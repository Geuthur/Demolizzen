# Standard Library
import re
from pathlib import Path

# Django
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[3]


class DeploymentFilesTest(SimpleTestCase):
    """The files an operator copies must match what the code reads."""

    def test_env_example_names_every_setting_the_code_reads(self):
        read = set(
            re.findall(
                r'os\.getenv\("([A-Z_]+)"\)',
                (ROOT / "demolizzen/config.py").read_text(),
            )
        )
        documented = set(
            re.findall(r"^([A-Z_]+)=", (ROOT / ".env.example").read_text(), re.M)
        )

        self.assertEqual(sorted(read - documented), [])

    def test_env_example_holds_no_secrets(self):
        for line in (ROOT / ".env.example").read_text().splitlines():
            name, _, value = line.partition("=")
            if re.search(r"SECRET|TOKEN|PASSWORD", name) and not name.startswith("#"):
                self.assertEqual(value, "", name)

    def test_container_starts_the_application_that_exists(self):
        # Demolizzen
        from demolizzen.web import asgi

        dockerfile = (ROOT / "Dockerfile").read_text()

        self.assertIn('"demolizzen.web.asgi:application"', dockerfile)
        self.assertTrue(callable(asgi.application))
        self.assertIn("DJANGO_SETTINGS_MODULE=demolizzen.web.settings", dockerfile)
        self.assertIn("/healthz", dockerfile)

    def test_compose_publishes_the_port_the_container_listens_on(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        compose = (ROOT / "docker-compose.yml").read_text()

        self.assertIn('"--port", "8000"', dockerfile)
        self.assertIn("${PANEL_BIND:-127.0.0.1}:${PANEL_PORT:-8000}:8000", compose)
