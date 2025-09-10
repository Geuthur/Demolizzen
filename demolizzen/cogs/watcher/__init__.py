# Demolizzen
from demolizzen.cogs.watcher.watcher import Watcher
from demolizzen.core.bot import Demolizzen


def setup(bot: Demolizzen):
    bot.add_cog(Watcher(bot))
