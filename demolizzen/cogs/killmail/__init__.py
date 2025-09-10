# Demolizzen
from demolizzen.core.bot import Demolizzen

from .killmail import Killmail


def setup(bot: Demolizzen):
    bot.add_cog(Killmail(bot))
