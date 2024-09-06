from .levelsystem import Levelsystem


def setup(bot):
    bot.add_cog(Levelsystem(bot))
