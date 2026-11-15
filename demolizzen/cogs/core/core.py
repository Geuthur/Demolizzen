# Discord
import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands

# Demolizzen
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog


class Core(BaseCog):
    """General bot functions."""

    key = "core"

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
        self.title = "Core"
        self.alias = "core"

    botsettings = SlashCommandGroup(
        "bot", "Bot Settings", contexts=[discord.InteractionContextType.guild]
    )

    @botsettings.command()
    @commands.cooldown(3, 600, commands.BucketType.user)  # 3 per 10 minutes per member
    async def uptime(self, ctx: discord.ApplicationContext):
        """
        Show how long the bot has been running for
        """
        # https://i.imgur.com/82Cqf1x.png
        em = discord.Embed(
            title="Uptime",
            color=discord.Color.blue(),
            description=f"{self.bot.uptime_str}",
        )
        guilds = len(self.bot.guilds)
        users = len(list(self.bot.get_all_members()))
        if guilds:
            em.add_field(
                name="", value=f"Servers: {guilds} - Members: {users}", inline=False
            )
        await ctx.respond(embed=em)

    @botsettings.command()
    async def changelog(self, ctx: discord.ApplicationContext):
        """
        Show the bot's changelog
        """
        em = discord.Embed(
            title="Changelog",
            color=discord.Color.blue(),
            description="Here is the changelog for the bot: [CHANGELOG.md](https://github.com/Geuthur/Demolizzen/blob/master/CHANGELOG.md)",
        )
        return await ctx.respond(embed=em)
