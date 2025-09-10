# Demolizzen
from demolizzen.core.bot import Demolizzen

from .vow import Vow


def setup(bot: Demolizzen):
    bot.add_cog(Vow(bot))
