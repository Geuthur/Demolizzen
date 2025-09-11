# Demolizzen
from demolizzen.core.bot import Demolizzen

from .owner import Owner


def setup(bot: Demolizzen):
    bot.add_cog(Owner(bot))
