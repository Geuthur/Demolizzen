from .token import Token


def setup(bot):
    bot.add_cog(Token(bot))
