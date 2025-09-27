# Standard Library
import logging

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks

# Django
from django.db import close_old_connections
from django.utils import timezone

# Demolizzen
from demolizzen import models
from demolizzen.core.bot import Demolizzen

logger = logging.getLogger(__name__)


class BankConfig(commands.Cog):
    """
    Cog for managing bank configuration settings.
    """

    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.last_update_time = timezone.now()
        self.title = "Banksystem"
        self.alias = "bank_config"
        self.deposits.start()

    bank_config = SlashCommandGroup(
        "bank_config",
        "Banksystem Configuration",
        contexts=[discord.InteractionContextType.guild],
        default_member_permissions=discord.Permissions(manage_guild=True),
    )

    def cog_unload(self):
        self.deposits.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.debug("Bank Cog is ready.")
        guild_profiles = [g async for g in models.GuildProfile.objects.all()]
        if not guild_profiles:
            logger.warning(
                "No guild profiles found. Skipping bank settings initialization."
            )
            return

        create_counter = 0
        for guild in guild_profiles:
            try:
                _, created = await models.GuildBankSettings.objects.aget_or_create(
                    guild=guild
                )
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
        close_old_connections()
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
                g
                async for g in models.GuildBankSettings.objects.all().select_related(
                    "guild"
                )
            ]
            for guild_bank in guild_bank_settings:
                bank_accounts = [
                    r
                    async for r in models.UserBankAccount.objects.filter(
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
                    updated = await models.UserBankAccount.objects.abulk_update(
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
        # Load or create the user profile
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
        # Ensure the guild bank settings exist
        guild_bank_settings, created = (
            await models.GuildBankSettings.objects.aget_or_create(
                guild=user.guild,
            )
        )
        ctx.guild_bank_settings = guild_bank_settings
        logger.debug(f"Guild Bank Settings loaded for guild {ctx.guild}")

    @bank_config.command(name="set-interest-rate")
    @commands.guild_only()
    @option("rate", description="Set the interest rate (in percentage, e.g., 5 for 5%)")
    async def set_interest_rate(self, ctx: discord.ApplicationContext, rate: float):
        """Set the interest rate for the bank."""
        if rate < 0 or rate > 100:
            await ctx.respond("Interest rate must be between 0 and 100.")
            return

        ctx.guild_bank_settings.interest_rate = rate
        await ctx.guild_bank_settings.asave()

        await ctx.respond(f"Interest rate set to {rate}%.")
