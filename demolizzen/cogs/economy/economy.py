# Standard Library
import logging
import random

# Third Party
from asgiref.sync import sync_to_async

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands

# Django
from django.db import transaction
from django.utils import timezone

# Demolizzen
from demolizzen import models
from demolizzen.core.bot import Demolizzen

logger = logging.getLogger(__name__)


# pylint: disable=too-many-public-methods
class Economy(commands.Cog):
    """All about economy"""

    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.alias = "eco"
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
        try:
            user = await models.UserProfile.objects.select_related(
                "bank_account", "bags", "raid_mission", "mining_mission"
            ).aget(user_id=ctx.author.id, guild_id=ctx.guild.id)
            ctx.user_profile = user
            logger.debug(f"UserProfile loaded for {ctx.author}.")
        except models.UserProfile.DoesNotExist as exc:
            raise commands.CheckFailure(
                "UserProfile does not exist. Please register first. `/auth register`"
            ) from exc

        try:
            assert user.bank_account
        except models.UserBankAccount.DoesNotExist as exc:
            raise commands.CheckFailure(
                "Bank account does not exist. Please create one first. `/bank create`"
            ) from exc

    @commands.slash_command()
    async def daily(self, ctx: discord.ApplicationContext):
        """
        Collect your Daily Reward
        """
        try:
            daily_account, __ = await models.UserDailyReward.objects.select_related(
                "user"
            ).aget_or_create(user=ctx.user_profile)

            # Timer Manager
            remaining_time = await daily_account.user.get_cooldown(
                ctx=ctx,
                ship_cooldown=timezone.timedelta(days=1),
                last_cooldown=daily_account.last_claim,
            )

            delta = remaining_time.delta
            cooldown = remaining_time.cooldown

            if delta < remaining_time.timer:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, You have already collected your daily reward, wait a bit more `{cooldown}`",
                )
                await ctx.respond(embed=em)
                return

            # Set Daily Reward
            # Streak: +1 wenn mehr als 24h vergangen, sonst 1
            streak = daily_account.streak + 1 if delta > remaining_time.timer else 1
            daily_account.streak = streak
            daily_account.last_claim = timezone.now()
            daily_reward = random.randrange(30) + (daily_account.streak * 5)
            # Update Bank Account
            bank_account: models.UserBankAccount = ctx.user_profile.bank_account
            bank_account.wallet += daily_reward
            await daily_account.asave()
            await bank_account.asave()

            # Send Response
            em = discord.Embed(
                title="",
                color=discord.Color.teal(),
                description=f"{ctx.author.mention}, **{streak}** At once. Here is your daily reward of {daily_reward}:coin:",
            )

            await ctx.respond(embed=em)
        except Exception as e:
            logger.exception(f"Error in daily command: {e}")
            await ctx.respond(
                "An error occurred while processing your command. Please try again later."
            )
        return

    @commands.slash_command()
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
        # Get Information for further process
        server_id = ctx.guild.id
        author = ctx.author.name.capitalize()

        try:
            gank_account = await models.UserProfile.objects.select_related(
                "bank_account"
            ).aget(user_id=user.id, guild_id=server_id)
            assert gank_account.bank_account  # Ensure bank_account is loaded
        except (models.UserProfile.DoesNotExist, models.UserBankAccount.DoesNotExist):
            gank_account = None

        if gank_account is None:
            await ctx.respond("He hasn't a Bank Account...", ephemeral=True)
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

        bank_account: models.UserBankAccount = ctx.user_profile.bank_account

        # Erfolgreicher Raid
        if random_chance <= 25:
            # Überprüfen, ob der Benutzer genug Geld hat
            if gank_account.bank_account.wallet < amount:
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

            # Attempt to update both balances
            def gank_transaction():
                with transaction.atomic():
                    gank_account.bank_account.wallet -= amount
                    bank_account.wallet += amount
                    gank_account.bank_account.save()
                    bank_account.save()

            sync_to_async(gank_transaction)()

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

        # Mißlungerner Raid
        if random_chance <= 70:
            # Überprüfen, ob der Benutzer genug Geld hat
            if bank_account.wallet < amount:
                em.add_field(
                    name="",
                    value=f":rocket: {author} you are broke... go back to work...",
                    inline=False,
                )
                return await ctx.respond(embed=em)

            def gank_fail_transaction():
                with transaction.atomic():
                    bank_account.wallet -= amount
                    gank_account.bank_account.wallet += amount
                    bank_account.save()
                    gank_account.bank_account.save()

            await sync_to_async(gank_fail_transaction)()

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
