# Demolizzen
from demolizzen.core.bot import Demolizzen

from .general import General


def setup(bot: Demolizzen):
    bot.add_cog(General(bot))
