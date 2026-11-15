# Standard Library
import logging

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup

# Demolizzen
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog
from demolizzen.services import bank, guilds
from demolizzen.services.errors import BankError

logger = logging.getLogger(__name__)


class BankAdmin(BaseCog):
    """
    Cog for administering bank accounts.
    """

    key = "banksystem"

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
        self.title = "Banksystem"
        self.alias = "bank_admin"

    bank_admin = SlashCommandGroup(
        "bank_admin",
        "Banksystem Administration",
        contexts=[discord.InteractionContextType.guild],
        default_member_permissions=discord.Permissions(manage_guild=True),
    )

    @bank_admin.command(name="give-money")
    @checks.is_admin()
    @option("member", description="Choose Member")
    @option("amount", description="Specify the amount of Coins to Give")
    async def give_money(
        self, ctx: discord.ApplicationContext, member: discord.Member, amount: int
    ):
        """Give money to a specific user."""
        await guilds.ensure_guild(ctx.guild.id, ctx.guild.name)
        try:
            await bank.credit(ctx.guild.id, member.id, member.display_name, amount)
        except BankError as error:
            await ctx.respond(error.message, ephemeral=True)
            return
        await ctx.respond(
            f"You gave {amount}:coin:! to {member.mention}", ephemeral=True
        )

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
        """Remove money from a specific user. Takes at most what is there."""
        await guilds.ensure_guild(ctx.guild.id, ctx.guild.name)
        try:
            removed = await bank.debit(
                ctx.guild.id,
                member.id,
                member.display_name,
                amount,
                account=konto,
                clamp=True,
            )
        except BankError as error:
            await ctx.respond(error.message, ephemeral=True)
            return
        await ctx.respond(
            f"You removed {removed}:coin:! from {member.mention}", ephemeral=True
        )

    @bank_admin.command(name="remove-bank")
    @checks.is_admin()
    @option("member", description="Choose Member")
    async def reset_money(
        self, ctx: discord.ApplicationContext, member: discord.Member
    ):
        """
        Reset Bankaccount from Member
        """
        await guilds.ensure_guild(ctx.guild.id, ctx.guild.name)
        await bank.reset(ctx.guild.id, member.id, member.display_name)
        await ctx.respond(
            f"Bankaccount from {member.mention} has been reset.", ephemeral=True
        )
