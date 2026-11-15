# Demolizzen
from demolizzen.core import settings_pages
from demolizzen.core.bot import Demolizzen

from ._settings_page import bank_settings_page
from .banksystem import Bank
from .banksystem_admin import BankAdmin


def setup(bot: Demolizzen):
    settings_pages.register("banksystem", bank_settings_page)
    bot.add_cog(BankAdmin(bot))
    bot.add_cog(Bank(bot))


def teardown(bot: Demolizzen):  # pylint: disable=unused-argument
    settings_pages.unregister("banksystem")
