# Django
from django.test import SimpleTestCase

# Demolizzen
from demolizzen import config
from demolizzen.core import registry
from demolizzen.core.registry import REGISTRY
from demolizzen.services.errors import UnknownCog


class RegistryTest(SimpleTestCase):
    def test_fixed_cogs_are_not_toggleable(self):
        self.assertEqual(
            {key for key, info in REGISTRY.items() if not info.toggleable},
            {"core", "owner", "guild", "panel"},
        )

    def test_registry_matches_preload_extensions(self):
        self.assertEqual(
            set(REGISTRY) - {"panel"}, set(config.PRELOAD_EXTENSIONS) - {"panel"}
        )

    def test_keys_match_entries(self):
        for key, info in REGISTRY.items():
            self.assertEqual(key, info.key)
            self.assertTrue(info.title)
            self.assertTrue(info.description)

    def test_get_returns_entry(self):
        self.assertEqual(registry.get("ticket").title, "Ticket System")

    def test_get_unknown_raises(self):
        with self.assertRaises(UnknownCog):
            registry.get("nope")

    def test_toggleable_excludes_fixed_cogs_and_keeps_order(self):
        keys = [info.key for info in registry.toggleable()]

        self.assertEqual(keys, [k for k in REGISTRY if REGISTRY[k].toggleable])
        self.assertNotIn("core", keys)

    def test_bank_dependents(self):
        self.assertEqual(
            registry.dependents("banksystem"), ["economy", "shop", "games"]
        )
        self.assertEqual(registry.requirements("games"), ["banksystem"])

    def test_cog_without_links_has_none(self):
        self.assertEqual(registry.dependents("ticket"), [])
        self.assertEqual(registry.requirements("ticket"), [])

    def test_requirements_reference_toggleable_known_cogs(self):
        for info in REGISTRY.values():
            for required in info.requires:
                self.assertTrue(REGISTRY[required].toggleable, f"{info.key}→{required}")
                self.assertTrue(info.toggleable, info.key)
