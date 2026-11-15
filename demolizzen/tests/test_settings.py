# Django
from django.test import SimpleTestCase

# Demolizzen
from testenv.settings import use_mysql


class UseMysqlTest(SimpleTestCase):
    def test_truthy_values_select_mysql(self):
        for value in ("1", "true", "TRUE", "yes"):
            with self.subTest(value=value):
                self.assertTrue(use_mysql(value))

    def test_other_values_select_sqlite(self):
        for value in (None, "", "0", "false", "no"):
            with self.subTest(value=value):
                self.assertFalse(use_mysql(value))
