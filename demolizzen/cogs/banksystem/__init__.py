# Demolizzen
from demolizzen.core.bot import Demolizzen

from .banksystem import Bank
from .banksystem_admin import BankAdmin
from .banksystem_config import BankConfig


def setup(bot: Demolizzen):
    bot.add_cog(BankConfig(bot))
    bot.add_cog(BankAdmin(bot))
    bot.add_cog(Bank(bot))
