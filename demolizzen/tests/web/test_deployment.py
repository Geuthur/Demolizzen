# Standard Library
import re
import tomllib
from pathlib import Path
from unittest.mock import patch

# Django
from django.test import SimpleTestCase

# Demolizzen
from demolizzen.core.extensions import with_extra

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

    def test_compose_lets_the_container_reach_a_database_on_the_host(self):
        compose = (ROOT / "docker-compose.yml").read_text()

        self.assertIn('"host.docker.internal:host-gateway"', compose)


class ImageBuildTest(SimpleTestCase):
    """The build stage gets only the files it is given."""

    def test_every_file_the_package_build_needs_is_copied_in(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        needed = {project["readme"], project["license"]["file"], "pyproject.toml"}

        for name in ("Dockerfile", "Dockerfile.bot"):
            # Text before the first FROM is the file's comment.
            build_stage = (ROOT / name).read_text().split("\nFROM ")[1]
            copied = set()
            for line in re.findall(r"^COPY (.+)$", build_stage, re.M):
                copied |= set(line.split()[:-1])
            with self.subTest(dockerfile=name):
                self.assertEqual(needed - copied, set())
                self.assertIn("demolizzen", copied)

    def test_docker_does_not_hide_those_files_from_the_build(self):
        ignored = (ROOT / ".dockerignore").read_text().split()

        for name in (
            "pyproject.toml",
            "README.md",
            "LICENSE",
            "manage.py",
            "demolizzen",
        ):
            with self.subTest(file=name):
                self.assertNotIn(name, ignored)


class BotContainerTest(SimpleTestCase):
    """The template that runs the bot itself in a container."""

    def setUp(self):
        self.dockerfile = (ROOT / "Dockerfile.bot").read_text()
        self.compose = (ROOT / "docker-compose.bot.yml").read_text()

    def workdir(self) -> str:
        return re.findall(r"^WORKDIR (\S+)$", self.dockerfile, re.M)[-1]

    def test_container_starts_the_bot_that_exists(self):
        # Demolizzen
        from demolizzen import launch

        self.assertIn('"-m", "demolizzen.launch"', self.dockerfile)
        self.assertTrue(callable(launch.run_bot))
        self.assertIn("DJANGO_SETTINGS_MODULE=demolizzen.settings", self.dockerfile)

    def test_database_is_brought_up_to_date_by_the_bot_itself(self):
        # The bot applies pending migrations at every start, wherever it runs;
        # the container must not switch that off.
        # Demolizzen
        from demolizzen.core import schema

        self.assertTrue(schema.enabled(None))
        self.assertNotIn("AUTO_MIGRATE", self.dockerfile)
        self.assertNotIn("AUTO_MIGRATE", self.compose)

    def test_stop_signal_reaches_the_bot_not_a_shell(self):
        # "docker stop" must let the bot close its connections.
        self.assertIn('CMD ["python", "-m", "demolizzen.launch"]', self.dockerfile)

    def test_management_commands_work_inside_the_container(self):
        # README: python manage.py migrate / init_database
        self.assertRegex(self.dockerfile, r"COPY .*manage\.py")
        self.assertTrue((ROOT / "manage.py").is_file())

    def test_bot_does_not_run_as_root(self):
        user = re.findall(r"^USER (\S+)$", self.dockerfile, re.M)[-1]

        self.assertNotIn(user, ("root", "0"))

    def test_log_folder_exists_where_the_bot_writes_and_is_kept(self):
        # Demolizzen
        from demolizzen import config

        logs = f"{self.workdir()}/{config.LOGS_DIR}"

        # The bot creates the last folder only; the image must bring the rest.
        self.assertIn(f"mkdir -p {logs}", self.dockerfile)
        self.assertIn(f"- bot-logs:{logs}", self.compose)

    def test_image_is_built_without_what_only_the_panel_needs(self):
        self.assertNotIn("[web]", self.dockerfile)
        self.assertNotIn("uvicorn", self.dockerfile)

    def test_compose_builds_the_bot_image_and_reads_the_settings_file(self):
        self.assertIn("dockerfile: Dockerfile.bot", self.compose)
        self.assertIn("env_file: .env", self.compose)
        self.assertIn("restart: unless-stopped", self.compose)
        self.assertIn('"host.docker.internal:host-gateway"', self.compose)

    def test_bot_publishes_no_port(self):
        # It only connects outwards.
        self.assertNotIn("ports:", self.compose)
        self.assertNotIn("EXPOSE", self.dockerfile)

    def test_starting_the_panel_never_starts_a_second_bot(self):
        # Two bots with one token answer every command twice.
        panel = (ROOT / "docker-compose.yml").read_text()

        self.assertNotIn("demolizzen.launch", panel)
        self.assertNotIn("Dockerfile.bot", panel)
        self.assertNotRegex(panel, re.compile(r"^  bot:", re.M))

    def test_docs_warn_about_running_the_bot_twice(self):
        docs = (ROOT / "docs/bot-docker.md").read_text()

        self.assertIn("docker compose -f docker-compose.bot.yml up -d --build", docs)
        self.assertIn("init_database", docs)
        self.assertRegex(docs, r"(?i)stop the bot .*before")


class BotDatabaseTemplateTest(SimpleTestCase):
    """The optional database next to the bot, for those who have none yet."""

    def setUp(self):
        self.compose = (ROOT / "docker-compose.bot.yml").read_text()
        # The block of the service, up to the next top-level key.
        self.db = re.search(r"^  db:\n(.*?)(?=^\S)", self.compose, re.M | re.S).group(1)
        self.bot = re.search(
            r"^  bot:\n(.*?)(?=^  \S)", self.compose, re.M | re.S
        ).group(1)

    def test_database_only_starts_when_asked_for(self):
        # Whoever has a database already must not get a second, empty one.
        self.assertIn('profiles: ["database"]', self.db)
        self.assertNotIn("profiles:", self.bot)

    def test_bot_starts_without_the_database_service(self):
        # depends_on would drag the database in, or stop the bot without it.
        self.assertNotIn("depends_on", self.bot)

    def test_login_is_the_one_the_bot_uses(self):
        for line in (
            "MARIADB_DATABASE: ${DATABASE_NAME:-}",
            "MARIADB_USER: ${DATABASE_USER:-}",
            "MARIADB_PASSWORD: ${DATABASE_PASSWORD:-}",
            "MARIADB_ROOT_PASSWORD: ${DATABASE_ROOT_PASSWORD:-}",
        ):
            with self.subTest(line=line):
                self.assertIn(line, self.db)

    def test_no_password_is_written_into_the_file(self):
        # Either a reference to .env or deliberately blank.
        for value in re.findall(r"PASSWORD: (.+)", self.compose):
            self.assertRegex(value, r'^(\$\{[A-Z_]+:-\}|"")$')

    def test_administrator_password_stays_out_of_bot_and_panel(self):
        # env_file hands a container all of .env; these two only need their
        # own login.
        blank = 'DATABASE_ROOT_PASSWORD: ""'

        self.assertIn(blank, self.bot)
        self.assertIn(blank, (ROOT / "docker-compose.yml").read_text())

    def test_data_outlives_the_container(self):
        self.assertIn("- db-data:/var/lib/mysql", self.db)
        self.assertRegex(
            self.compose, re.compile(r"^volumes:\n(  .+\n)*  db-data:", re.M)
        )

    def test_database_is_not_published_to_the_network(self):
        self.assertNotIn("ports:", self.compose)

    def test_tables_can_hold_every_character(self):
        # Names and messages contain emoji.
        self.assertIn("--character-set-server=utf8mb4", self.db)

    def test_root_password_setting_is_documented_without_a_value(self):
        example = (ROOT / ".env.example").read_text()

        self.assertRegex(example, re.compile(r"^DATABASE_ROOT_PASSWORD=$", re.M))

    def test_docs_tell_how_to_use_and_back_up_the_database(self):
        docs = (ROOT / "docs/bot-docker.md").read_text()

        self.assertIn("--profile database", docs)
        self.assertIn("DATABASE_HOST=db", docs)
        self.assertIn("mariadb-dump", docs)


class ExtraExtensionsTest(SimpleTestCase):
    """Modules of single servers are switched on in .env, not by editing code."""

    def test_nothing_set_loads_the_standard_modules(self):
        self.assertEqual(with_extra(["core", "panel"], None), ["core", "panel"])
        self.assertEqual(with_extra(["core", "panel"], "  "), ["core", "panel"])

    def test_named_modules_are_loaded_after_the_standard_ones(self):
        self.assertEqual(
            with_extra(["core", "ticket"], " vow, Geuthur ,,"),
            ["core", "ticket", "vow", "geuthur"],
        )

    def test_module_is_never_loaded_twice(self):
        self.assertEqual(
            with_extra(["core", "ticket"], "ticket,vow,vow"), ["core", "ticket", "vow"]
        )

    def test_given_list_is_left_as_it_was(self):
        standard = ["core"]

        with_extra(standard, "vow")

        self.assertEqual(standard, ["core"])

    def test_only_plain_module_names_are_accepted(self):
        # The names become part of an import path.
        for bad in ("../x", "os.system", "a b", "vow;rm"):
            with self.subTest(name=bad), self.assertRaises(ValueError):
                with_extra(["core"], bad)

    def test_bot_loads_what_the_setting_names(self):
        # Demolizzen
        from demolizzen import config
        from demolizzen.core.bot import Demolizzen

        with patch.dict("os.environ", {"EXTRA_EXTENSIONS": "vow"}):
            bot = Demolizzen()

        self.assertEqual(bot.preload_ext, [*config.PRELOAD_EXTENSIONS, "vow"])
        self.assertNotIn("vow", config.PRELOAD_EXTENSIONS)

    def test_bot_without_the_setting_loads_the_configured_modules(self):
        # Demolizzen
        from demolizzen import config
        from demolizzen.core.bot import Demolizzen

        with patch.dict("os.environ", {}, clear=False) as environ:
            environ.pop("EXTRA_EXTENSIONS", None)
            bot = Demolizzen()

        self.assertEqual(bot.preload_ext, list(config.PRELOAD_EXTENSIONS))

    def test_setting_is_documented(self):
        self.assertIn("EXTRA_EXTENSIONS=", (ROOT / ".env.example").read_text())
