from .eveonline import Eve


def setup(bot):
    bot.add_cog(Eve(bot))
