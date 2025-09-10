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
from demolizzen.models import BankAccount, UserProfile


class Bank(commands.Cog):
    """
    Save you money, Deposit it or Withdraw it watch out of other Players...
    """

    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.last_update_time = timezone.now()
        self.title = "Banksystem"
        self.alias = "bank"
        self.earns = 0.01
        self.deposits.start()

    def cog_unload(self):
        self.deposits.cancel()

    bank = SlashCommandGroup(
        "bank", "Banksystem", contexts=[discord.InteractionContextType.guild]
    )

    # Täglicher Update-Task
    @tasks.loop(hours=168)
    async def deposits(self):
        await self.process_daily_interest()
        self.last_update_time = timezone.now()

    @deposits.before_loop
    async def before_deposits(self):
        await self.bot.wait_until_ready()
        self.bot.logger.info("Bank Interest Ready")

    async def process_daily_interest(self):
        try:
            self.bot.logger.debug("Starting bank interest update...")
            bank_accounts = [r async for r in BankAccount.objects.all()]
            items = []
            for account in bank_accounts:
                interest = int(account.bank * self.earns)
                account.bank += interest
                items.append(account)
            updated = await BankAccount.objects.abulk_update(items, fields=["bank"])
            if updated:
                self.bot.logger.info(
                    f"Payout {len(items)} Accounts with {self.earns * 100}% interest."
                )
            else:
                self.bot.logger.error("Failed to update bank accounts.")
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.bot.logger.exception(f"Error during bank interest update: {e}")

    @bank.command()
    async def create(self, ctx: discord.ApplicationContext):
        """
        Create your Bank Account
        """
        user, __ = await UserProfile.objects.aget_or_create(
            user_id=ctx.author.id,
            user_name=ctx.author.display_name,
            guild__guild_id=ctx.guild.id,
        )

        try:
            await BankAccount.objects.acreate(user=user)
        except IntegrityError as e:
            self.bot.logger.debug(f"IntegrityError: {e}")
            await ctx.respond(
                f"❌ {ctx.author.mention}, You already have a bank account.",
                ephemeral=True,
            )
            return
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.bot.logger.exception(f"Error creating bank account: {e}")
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
        try:
            user = await UserProfile.objects.select_related("bank_account").aget(
                user_id=ctx.author.id,
                user_name=ctx.author.display_name,
                guild__guild_id=ctx.guild.id,
            )
            bank_account = user.bank_account
        except BankAccount.DoesNotExist:
            await ctx.respond(
                f"❌ {ctx.author.mention}, You do not have a bank account yet. Please create one using `/bank create`.",
                ephemeral=True,
            )
            return

        em = discord.Embed(
            title="",
            color=discord.Color.dark_teal(),
            description=f"{ctx.author.mention}, You have\n",
        )
        em.add_field(
            name="Personal 💰",
            value=f"`🪙` **Wallet**: ${bank_account.wallet}",
            inline=True,
        )
        em.add_field(
            name="Bank 🏦",
            value=f"`💵` **Balance:** ${bank_account.bank}\n `📈` **INTEREST:** 1%",
            inline=True,
        )
        await ctx.respond(embed=em)
        self.bot.logger.debug(
            "Balance checked for user %s in guild %s", ctx.author.id, ctx.guild.id
        )

    @bank.command()
    @option("amount", description="Specify the amount of Coins to Deposit")
    async def deposit(self, ctx: discord.ApplicationContext, amount: int):
        """
        Deposit your money to the bank
        """
        try:
            user = await UserProfile.objects.select_related("bank_account").aget(
                user_id=ctx.author.id,
                user_name=ctx.author.display_name,
                guild__guild_id=ctx.guild.id,
            )
            bank_account = user.bank_account
        except BankAccount.DoesNotExist:
            await ctx.respond(
                f"❌ {ctx.author.mention}, You do not have a bank account yet. Please create one using `/bank create`.",
                ephemeral=True,
            )
            return

        amount = int(amount)

        if amount > bank_account.wallet:
            await ctx.respond("You don't have that much money!")
            return

        if amount < 0:
            await ctx.respond("Amount must be positive!")
            return

        # Attempt to update both wallet and bank balances
        def update_balances():
            bank_account.wallet -= amount
            bank_account.bank += amount
            bank_account.save()

        await sync_to_async(update_balances)()
        await ctx.respond(f"You deposited {amount} :coin:!")

    @bank.command()
    @option("amount", description="Specify the amount of Coins to Withdraw")
    async def withdraw(self, ctx: discord.ApplicationContext, amount: int):
        """
        Withdraw your money from the bank
        """
        try:
            user = await UserProfile.objects.select_related("bank_account").aget(
                user_id=ctx.author.id,
                user_name=ctx.author.display_name,
                guild__guild_id=ctx.guild.id,
            )
            bank_account = user.bank_account
        except BankAccount.DoesNotExist:
            await ctx.respond(
                f"❌ {ctx.author.mention}, You do not have a bank account yet. Please create one using `/bank create`.",
                ephemeral=True,
            )
            return

        amount = int(amount)

        if amount > bank_account.bank:
            await ctx.respond("You don't have that much money!")
            return
        if amount < 0:
            await ctx.respond("Amount must be positive!")
            return

        # Attempt to update both wallet and bank balances
        def update_balances():
            with transaction.atomic():
                bank_account.bank -= amount
                bank_account.wallet += amount
                bank_account.save()

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
            user_account = await UserProfile.objects.aget(
                user_id=ctx.author.id, guild__guild_id=server_id
            )
            member_account = await UserProfile.objects.aget(
                user_id=member.id, guild__guild_id=server_id
            )
            user_bank_account = user_account.bank_account
            member_bank_account = member_account.bank_account
        except UserProfile.DoesNotExist:
            await ctx.respond(
                "❌ One of the accounts does not exist.",
                ephemeral=True,
            )
            return
        except BankAccount.DoesNotExist:
            await ctx.respond(
                "❌ One of the bank accounts does not exist.",
                ephemeral=True,
            )
            return

        if user_account and member_account:
            amount = int(amount)

            if amount > user_bank_account.wallet:
                await ctx.respond("You don't have that much money!")
                return

            if amount < 0:
                await ctx.respond("Amount must be positive!")
                return

            # Update both accounts in the database
            def update_balances():
                with transaction.atomic():
                    user_bank_account.wallet -= amount
                    member_bank_account.wallet += amount
                    user_bank_account.save()
                    member_bank_account.save()

            await sync_to_async(update_balances)()
            await ctx.respond(f"You gave {amount}:coin:! to {member.mention}")
        elif user_account and member_account is None:
            await ctx.respond(
                f"❌ {member.mention} does not have a bank account yet. Ask them to create one first.",
                ephemeral=True,
            )
        elif user_account is None and member_account:
            await ctx.respond(
                "❌ You does not have a bank account yet. Please create one first.",
                ephemeral=True,
            )
        else:
            await ctx.respond("❌ Something went wrong, please try again later.")

    # ------------------------------ADMIN BEREICH----------------------------

    @commands.Cog.listener()
    async def on_guild_join(self, guild):  # pylint: disable=unused-argument
        """Event when the bot joins a guild."""

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):  # pylint: disable=unused-argument
        """Event when the bot is removed from a guild."""
