# Standard Library
import logging
import random

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands

# Demolizzen
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog
from demolizzen.services import bank, guilds, missions
from demolizzen.services.errors import InsufficientFunds, OnCooldown

logger = logging.getLogger(__name__)


# pylint: disable=too-many-public-methods
class Economy(BaseCog):
    """All about economy"""

    key = "economy"

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
        self.alias = "economy"
        self.title = "Economy"

    economy = SlashCommandGroup(
        "economy", "Text Adventure", contexts=[discord.InteractionContextType.guild]
    )
    mission = economy.create_subgroup(
        "mission", contexts=[discord.InteractionContextType.guild]
    )

    def set_event(self, guild_id, active, event_factor):
        self.events[guild_id] = (active, int(event_factor))

    def get_event(self, guild_id):
        return self.events.get(
            guild_id, (False, 0)
        )  # Standardwerte, falls das Event nicht vorhanden ist

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        # Members need no registration: profile and bank account are created on demand.
        await guilds.ensure_guild(ctx.guild.id, ctx.guild.name)
        await bank.ensure_account(ctx.guild.id, ctx.author.id, ctx.author.display_name)

    @commands.slash_command(contexts=[discord.InteractionContextType.guild])
    async def daily(self, ctx: discord.ApplicationContext):
        """
        Collect your Daily Reward
        """
        try:
            claim = await missions.claim_daily(
                ctx.guild.id,
                ctx.author.id,
                ctx.author.display_name,
                random.randrange(30),
            )
        except OnCooldown as cooldown:
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, You have already collected your daily reward, wait a bit more `{missions.format_remaining(cooldown.remaining)}`",
            )
            await ctx.respond(embed=em)
            return

        em = discord.Embed(
            title="",
            color=discord.Color.teal(),
            description=f"{ctx.author.mention}, **{claim.streak}** At once. Here is your daily reward of {claim.reward}:coin:",
        )
        await ctx.respond(embed=em)

    @commands.slash_command(contexts=[discord.InteractionContextType.guild])
    @commands.cooldown(1, 300, commands.BucketType.user)
    @option("user", description="Choose a target member", required=True)
    async def gank(self, ctx: discord.ApplicationContext, user: discord.Member):
        """
        Engage a target member and attempt to steal their coins.

        Arguments
        ----------
        ctx: `context`
            The context containing information about the request.
        user: `member`
            The target member from whom to attempt to steal coins.

        Returns
        -------
        str
            A message indicating the outcome of the attempted theft.
        """
        author = ctx.author.name.capitalize()

        if user.bot or user.id == ctx.author.id:
            await ctx.respond("You can't gank this target.", ephemeral=True)
            return

        # Embed create
        em = discord.Embed(title="", color=discord.Color.teal(), description="")
        em.add_field(
            name="",
            value=f":rocket: {ctx.author.mention} tries to gank {user.mention}!",
            inline=False,
        )

        # Configuration Gank System
        random_chance = random.randint(1, 100)
        amount = random.randint(1, 10)

        user_name = user.display_name.capitalize()
        # Text Adventure (English)
        ganktext = [
            "approaches and successfully starts scrambling!",
            "warps in and opens fire on the target.",
            "is surprised after being locked and pointed. Then leaves the ship frustrated...",
            f"spots {user_name}, who is AFK mining, and shoots their ship. It explodes...",
        ]

        # Text Adventure (English, failed raid)
        ganktext2 = [
            f"approaches and is immediately shot at by {user_name}!",
            f"warps to {user_name} and realizes local is full of reds...",
            f"surprises {user_name}, but doesn't realize {user_name} is sitting in a Titan 💣.",
            f"notices {user_name} is AFK mining. As they get closer, {user_name} quickly lights a Cyno.",
        ]

        attacker = (ctx.author.id, ctx.author.display_name)
        victim = (user.id, user.display_name)

        # Erfolgreicher Raid: the loot goes from the victim to the attacker
        if random_chance <= 25:
            try:
                await bank.transfer(ctx.guild.id, *victim, *attacker, amount)
            except InsufficientFunds:
                em.add_field(
                    name="",
                    value=f":rocket: {author} " + random.choice(ganktext) + "",
                    inline=False,
                )
                em.add_field(
                    name="",
                    value=f":rocket: {author} loots the wreck and finds it empty...",
                    inline=False,
                )
                await ctx.respond(embed=em)
                return

            em.add_field(
                name="",
                value=f":rocket: {author} " + random.choice(ganktext) + "",
                inline=False,
            )
            em.add_field(
                name="",
                value=f":rocket: {author} has looted {amount}:coin:!",
                inline=False,
            )
            return await ctx.respond(embed=em)

        # Mißlungerner Raid: the attacker pays the victim
        if random_chance <= 70:
            try:
                await bank.transfer(ctx.guild.id, *attacker, *victim, amount)
            except InsufficientFunds:
                em.add_field(
                    name="",
                    value=f":rocket: {author} you are broke... go back to work...",
                    inline=False,
                )
                return await ctx.respond(embed=em)

            em.add_field(
                name="",
                value=f":rocket: {author} " + random.choice(ganktext2) + "",
                inline=False,
            )
            em.add_field(
                name="",
                value=f":rocket: {author} has lost {amount}:coin:!",
                inline=False,
            )
            await ctx.respond(embed=em)
            return

        em.add_field(
            name="",
            value=f":rocket: {author} a wormhole appeared and sent you to another system.",
            inline=False,
        )
        return await ctx.respond(embed=em)
