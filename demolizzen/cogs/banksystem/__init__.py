from .banksystem import Bank


def setup(bot):
    bot.add_cog(Bank(bot))
