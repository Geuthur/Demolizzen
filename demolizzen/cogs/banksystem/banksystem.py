# Standard Library
import logging

# Third Party
from asgiref.sync import sync_to_async

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks

# Django
from django.db import IntegrityError, transaction
from django.utils import timezone

# Demolizzen
from demolizzen.core.bot import Demolizzen
from demolizzen.models import UserBankAccount, UserProfile
from demolizzen.models.guild import GuildBankSettings, GuildProfile

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
        self.deposits.start()

    def cog_unload(self):
        self.deposits.cancel()

    bank = SlashCommandGroup(
        "bank", "Banksystem", contexts=[discord.InteractionContextType.guild]
    )

    @commands.Cog.listener()
    async def on_ready(self):
        logger.debug("Bank Cog is ready.")
        guild_profiles = [g async for g in GuildProfile.objects.all()]
        if not guild_profiles:
            logger.warning(
                "No guild profiles found. Skipping bank settings initialization."
            )
            return

        create_counter = 0
        for guild in guild_profiles:
            try:
                _, created = await GuildBankSettings.objects.aget_or_create(guild=guild)
                if created:
                    create_counter += 1
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.exception(
                    f"Error loading bank settings for guild {guild.guild_name} ({guild.guild_id}): {e}"
                )
        if create_counter > 0:
            logger.info(f"Created bank settings for {create_counter} guild(s).")

    # Täglicher Update-Task
    @tasks.loop(hours=168)
    async def deposits(self):
        await self.process_daily_interest()
        self.last_update_time = timezone.now()

    @deposits.before_loop
    async def before_deposits(self):
        await self.bot.wait_until_ready()
        logger.info("Bank Interest Ready")

    async def process_daily_interest(self):
        try:
            logger.debug("Starting bank interest update...")
            guild_bank_settings = [
                g async for g in GuildBankSettings.objects.all().select_related("guild")
            ]
            for guild_bank in guild_bank_settings:
                bank_accounts = [
                    r
                    async for r in UserBankAccount.objects.filter(
                        user__guild=guild_bank.guild
                    )
                ]
                if bank_accounts and (
                    guild_bank.last_interest_update is None
                    or (timezone.now() - guild_bank.last_interest_update).days >= 7
                ):
                    items = []
                    for account in bank_accounts:
                        interest = int(account.bank * guild_bank.interest_rate)
                        account.bank += interest
                        items.append(account)
                    updated = await UserBankAccount.objects.abulk_update(
                        items, fields=["bank"]
                    )
                    if updated:
                        logger.info(
                            f"Payout {len(items)} Accounts with {guild_bank.interest_rate * 100}% interest for {guild_bank.guild}."
                        )
                    guild_bank.last_interest_update = timezone.now()
                    await guild_bank.asave()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception(f"Error during bank interest update: {e}")

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        user, created = await UserProfile.objects.select_related(
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
        bank_account, created = await UserBankAccount.objects.aget_or_create(
            user=user,
        )
        if created:
            logger.debug(
                f"Created new bank account for user {ctx.author} in guild {ctx.guild}"
            )
        ctx.bank_account = bank_account
        logger.debug(f"Bank Account loaded for {ctx.author} in guild {ctx.guild}")
        guild_settings, created = await GuildBankSettings.objects.aget_or_create(
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
            await UserBankAccount.objects.acreate(user=ctx.user_profile)
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
            member_account = await UserProfile.objects.select_related(
                "bank_account"
            ).aget(user_id=member.id, guild__guild_id=server_id)
            member_bank_account = member_account.bank_account
        except UserProfile.DoesNotExist:
            await ctx.respond(
                "❌ One of the accounts does not exist.",
                ephemeral=True,
            )
            return
        except UserBankAccount.DoesNotExist:
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
