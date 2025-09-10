# Demolizzen
from demolizzen.core.bot import Demolizzen

from .admin import Admin


def setup(bot: Demolizzen):
    bot.add_cog(Admin(bot))
