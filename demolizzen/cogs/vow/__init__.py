from .vow import Vow


def setup(bot):
    bot.add_cog(Vow(bot))
