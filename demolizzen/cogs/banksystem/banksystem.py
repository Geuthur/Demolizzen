# Standard Library
import logging

# Third Party
from asgiref.sync import sync_to_async

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands

# Django
from django.db import IntegrityError, transaction
from django.utils import timezone

# Demolizzen
from demolizzen import models
from demolizzen.core.bot import Demolizzen

logger = logging.getLogger(__name__)


class Bank(commands.Cog):
    """
    Save you money, Deposit it or Withdraw it watch out of other Players...
    """

    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.last_update_time = timezone.now()
        self.title = "Banksystem"
        self.alias = "bank"

    bank = SlashCommandGroup(
        "bank", "Banksystem", contexts=[discord.InteractionContextType.guild]
    )

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        user, created = await models.UserProfile.objects.select_related(
            "guild"
        ).aget_or_create(
            user_id=ctx.author.id,
            user_name=ctx.author.display_name,
            guild__guild_id=ctx.guild.id,
        )
        ctx.user_profile = user
        logger.debug(f"User Profile loaded for {ctx.author} in guild {ctx.guild}")
        if created:
            logger.debug(
                f"Created new user profile for {ctx.author} in guild {ctx.guild}"
            )
        bank_account, created = await models.UserBankAccount.objects.aget_or_create(
            user=user,
        )
        if created:
            logger.debug(
                f"Created new bank account for user {ctx.author} in guild {ctx.guild}"
            )
        ctx.bank_account = bank_account
        logger.debug(f"Bank Account loaded for {ctx.author} in guild {ctx.guild}")
        guild_settings, created = await models.GuildBankSettings.objects.aget_or_create(
            guild=user.guild,
        )
        ctx.guild_settings = guild_settings
        logger.debug(f"Guild Bank Settings loaded for guild {ctx.guild}")

    @bank.command()
    async def create(self, ctx: discord.ApplicationContext):
        """
        Create your Bank Account
        """
        try:
            await models.UserBankAccount.objects.acreate(user=ctx.user_profile)
        except IntegrityError as e:
            logger.debug(f"IntegrityError: {e}")
            await ctx.respond(
                f"❌ {ctx.author.mention}, You already have a bank account.",
                ephemeral=True,
            )
            return
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception(f"Error creating bank account: {e}")
            await ctx.respond(
                "❌ An error occurred while creating your bank account. Please try again later.",
                ephemeral=True,
            )
            return
        await ctx.respond(
            f"✅ {ctx.author.mention}, Your Bank Account has been created successfully!"
        )

    @bank.command()
    async def balance(self, ctx: discord.ApplicationContext):
        """
        Check your money
        """
        em = discord.Embed(
            title="",
            color=discord.Color.dark_teal(),
            description=f"{ctx.author.mention}, You have\n",
        )
        em.add_field(
            name="Personal 💰",
            value=f"`🪙` **Wallet**: ${ctx.bank_account.wallet}",
            inline=True,
        )
        em.add_field(
            name="Bank 🏦",
            value=f"`💵` **Balance:** ${ctx.bank_account.bank}\n `📈` **INTEREST:** {ctx.guild_settings.interest_rate * 100}%",
            inline=True,
        )
        await ctx.respond(embed=em)

    @bank.command()
    @option("amount", description="Specify the amount of Coins to Deposit")
    async def deposit(self, ctx: discord.ApplicationContext, amount: int):
        """
        Deposit your money to the bank
        """
        amount = int(amount)

        if amount > ctx.bank_account.wallet:
            await ctx.respond("You don't have that much money!")
            return

        if amount < 0:
            await ctx.respond("Amount must be positive!")
            return

        # Attempt to update both wallet and bank balances
        def update_balances():
            ctx.bank_account.wallet -= amount
            ctx.bank_account.bank += amount
            ctx.bank_account.save()

        await sync_to_async(update_balances)()
        await ctx.respond(f"You deposited {amount} :coin:!")

    @bank.command()
    @option("amount", description="Specify the amount of Coins to Withdraw")
    async def withdraw(self, ctx: discord.ApplicationContext, amount: int):
        """
        Withdraw your money from the bank
        """
        amount = int(amount)

        if amount > ctx.bank_account.bank:
            await ctx.respond("You don't have that much money!")
            return
        if amount < 0:
            await ctx.respond("Amount must be positive!")
            return

        # Attempt to update both wallet and bank balances
        def update_balances():
            with transaction.atomic():
                ctx.bank_account.bank -= amount
                ctx.bank_account.wallet += amount
                ctx.bank_account.save()

        await sync_to_async(update_balances)()
        await ctx.respond(f"You Withdraw {amount} :coin:!")

    @bank.command()
    @option("member", description="Choose Member")
    @option("amount", description="Specify the amount of Coins to Send")
    async def send(
        self, ctx: discord.ApplicationContext, member: discord.Member, amount: int
    ):
        """
        Send your money to a specific user
        """
        # await ctx.defer()

        # Get Server-ID for further process
        server_id = ctx.guild.id

        if member == ctx.author:
            await ctx.respond("You can't send to yourself...")
            return

        try:
            member_account = await models.UserProfile.objects.select_related(
                "bank_account"
            ).aget(user_id=member.id, guild__guild_id=server_id)
            member_bank_account = member_account.bank_account
        except models.UserProfile.DoesNotExist:
            await ctx.respond(
                "❌ One of the accounts does not exist.",
                ephemeral=True,
            )
            return
        except models.UserBankAccount.DoesNotExist:
            await ctx.respond(
                "❌ One of the bank accounts does not exist.",
                ephemeral=True,
            )
            return

        if ctx.bank_account and member_account:
            amount = int(amount)

            if amount > ctx.bank_account.wallet:
                await ctx.respond("You don't have that much money!")
                return

            if amount < 0:
                await ctx.respond("Amount must be positive!")
                return

            # Update both accounts in the database
            def update_balances():
                with transaction.atomic():
                    ctx.bank_account.wallet -= amount
                    member_bank_account.wallet += amount
                    ctx.bank_account.save()
                    member_bank_account.save()

            await sync_to_async(update_balances)()
            await ctx.respond(f"You gave {amount}:coin:! to {member.mention}")
        elif ctx.bank_account and member_account is None:
            await ctx.respond(
                f"❌ {member.mention} does not have a bank account yet. Ask them to create one first.",
                ephemeral=True,
            )
        elif ctx.bank_account is None and member_account:
            await ctx.respond(
                "❌ You does not have a bank account yet. Please create one first.",
                ephemeral=True,
            )
        else:
            await ctx.respond("❌ Something went wrong, please try again later.")
