from .geuthur import Geuthur


def setup(bot):
    bot.add_cog(Geuthur(bot))
