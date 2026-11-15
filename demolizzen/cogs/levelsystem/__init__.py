# Demolizzen
from demolizzen.core import settings_pages
from demolizzen.core.bot import Demolizzen

from ._settings_page import level_settings_page
from .levelsystem import Levelsystem


def setup(bot: Demolizzen):
    settings_pages.register("levelsystem", level_settings_page)
    bot.add_cog(Levelsystem(bot))


def teardown(bot: Demolizzen):  # pylint: disable=unused-argument
    settings_pages.unregister("levelsystem")
