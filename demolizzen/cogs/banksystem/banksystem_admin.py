# Standard Library
import logging

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands

# Django
from django.utils import timezone

# Demolizzen
from demolizzen import models
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen

logger = logging.getLogger(__name__)


class BankAdmin(commands.Cog):
    """
    Cog for administering bank accounts.
    """

    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.last_update_time = timezone.now()
        self.title = "Banksystem"
        self.alias = "bank_admin"

    bank_admin = SlashCommandGroup(
        "bank_admin",
        "Banksystem Administration",
        contexts=[discord.InteractionContextType.guild],
        default_member_permissions=discord.Permissions(manage_guild=True),
    )

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        # Load or create the user profile
        user, created = await models.UserProfile.objects.select_related(
            "guild"
        ).aget_or_create(
            user_id=ctx.author.id,
            guild__guild_id=ctx.guild.id,
            defaults={"user_name": ctx.author.display_name},
        )
        ctx.user_profile = user
        logger.debug(f"User Profile loaded for {ctx.author} in guild {ctx.guild}")
        if created:
            logger.debug(
                f"Created new user profile for {ctx.author} in guild {ctx.guild}"
            )
        # Ensure the guild bank settings exist
        guild_bank_settings, created = (
            await models.GuildBankSettings.objects.aget_or_create(
                guild=user.guild,
            )
        )
        ctx.guild_bank_settings = guild_bank_settings
        logger.debug(f"Guild Bank Settings loaded for guild {ctx.guild}")

    @bank_admin.command(name="give-money")
    @checks.is_admin()
    @option("member", description="Choose Member")
    @option("amount", description="Specify the amount of Coins to Give")
    async def give_money(
        self, ctx: discord.ApplicationContext, member: discord.Member, amount: int
    ):
        """Give money to a specific user."""
        amount = int(amount)
        if amount < 0:
            await ctx.respond("Amount must be positive!")
            return

        try:
            user = await models.UserProfile.objects.select_related("bank_account").aget(
                user_id=member.id, guild_id=ctx.guild.id
            )
            bank_account = user.bank_account
        except models.UserBankAccount.DoesNotExist:
            bank_account = await models.UserBankAccount.objects.acreate(
                user=user,
            )

        bank_account.wallet += amount
        # Update the bank account with the new amount
        await bank_account.asave()

        await ctx.respond(
            f"You gave {amount}:coin:! to {member.mention}", ephemeral=True
        )
        return

    @bank_admin.command(name="remove-money")
    @checks.is_admin()
    @option("member", description="Choose Member")
    @option("amount", description="Specify the amount of Coins to Remove")
    @option("konto", description="Choose Account", choices=["wallet", "bank"])
    async def remove_money(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        amount: int,
        konto: str,
    ):
        """Remove money from a specific user."""
        # Get Server-ID for further process
        server_id = ctx.guild.id

        if amount < 0:
            await ctx.respond("Amount must be positive!")
            return

        if konto not in ["wallet", "bank"]:
            await ctx.respond("Invalid account type selected.")
            return

        # Fetch the bank account for the member
        try:
            user = await models.UserProfile.objects.select_related("bank_account").aget(
                user_id=member.id, guild_id=server_id
            )
            bank_account = user.bank_account
        except models.UserBankAccount.DoesNotExist:
            await ctx.respond(f"❌ {member.name}, has no bank account.", ephemeral=True)
            return

        # If the account exists, check the account type and adjust the balance accordingly
        if konto == "wallet":
            amount = min(amount, bank_account.wallet)
            bank_account.wallet -= amount
        elif konto == "bank":
            amount = min(amount, bank_account.bank)
            bank_account.bank -= amount

        # Update the account in the database
        await bank_account.asave()

        await ctx.respond(
            f"You removed {amount}:coin:! from {member.mention}", ephemeral=True
        )
        return

    @bank_admin.command(name="remove-bank")
    @checks.is_admin()
    @option("member", description="Choose Member")
    async def reset_money(
        self, ctx: discord.ApplicationContext, member: discord.Member
    ):
        """
        Reset Bankaccount from Member
        """
        # Fetch the bank account for the member
        try:
            user = await models.UserProfile.objects.select_related("bank_account").aget(
                user_id=member.id, guild_id=ctx.guild.id
            )
            bank_account = user.bank_account
        except models.UserBankAccount.DoesNotExist:
            await ctx.respond(f"❌ {member.name}, has no bank account.", ephemeral=True)
            return

        # Reset the bank account from the database
        bank_account.wallet = 0
        bank_account.bank = 0

        # Update the account in the database
        await bank_account.asave()

        await ctx.respond(
            f"Bankaccount from {member.mention} has been reset.", ephemeral=True
        )
        return
