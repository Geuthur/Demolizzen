# Demolizzen
from demolizzen.core.bot import Demolizzen

from .eveonline import EveOnline


def setup(bot: Demolizzen):
    bot.add_cog(EveOnline(bot))
