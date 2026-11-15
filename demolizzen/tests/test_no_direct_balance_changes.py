# Standard Library
import re
from pathlib import Path

# Django
from django.test import SimpleTestCase

COGS = Path(__file__).resolve().parent.parent / "cogs"
ASSIGNMENT = re.compile(r"\.(wallet|bank)\s*(\+=|-=|\*=|=(?!=))")
SAVE = re.compile(r"bank_account\.a?save\(")


class BalanceOwnershipTest(SimpleTestCase):
    """Only the bank service may change balances; cogs book through it."""

    def test_no_cog_assigns_wallet_or_bank(self):
        offenders = []
        for path in sorted(COGS.rglob("*.py")):
            for number, line in enumerate(path.read_text().splitlines(), start=1):
                if ASSIGNMENT.search(line) or SAVE.search(line):
                    offenders.append(
                        f"{path.relative_to(COGS)}:{number}: {line.strip()}"
                    )

        self.assertEqual(offenders, [])
