# Standard Library
import logging

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup

# Demolizzen
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog
from demolizzen.services import bank, guilds
from demolizzen.services.errors import BankError

logger = logging.getLogger(__name__)


class Bank(BaseCog):
    """
    Save you money, Deposit it or Withdraw it watch out of other Players...
    """

    key = "banksystem"

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
        self.title = "Banksystem"
        self.alias = "bank"

    bank = SlashCommandGroup(
        "bank", "Banksystem", contexts=[discord.InteractionContextType.guild]
    )

    @staticmethod
    async def _refuse(ctx: discord.ApplicationContext, error: BankError) -> None:
        """Tell only the caller why the booking was not made."""
        await ctx.respond(error.message, ephemeral=True)

    @bank.command()
    async def balance(self, ctx: discord.ApplicationContext):
        """
        Check your money
        """
        await guilds.ensure_guild(ctx.guild.id, ctx.guild.name)
        balance = await bank.get_balance(
            ctx.guild.id, ctx.author.id, ctx.author.display_name
        )
        settings = await bank.get_settings(ctx.guild.id)

        em = discord.Embed(
            title="",
            color=discord.Color.dark_teal(),
            description=f"{ctx.author.mention}, You have\n",
        )
        em.add_field(
            name="Personal 💰",
            value=f"`🪙` **Wallet**: ${balance.wallet}",
            inline=True,
        )
        em.add_field(
            name="Bank 🏦",
            value=(
                f"`💵` **Balance:** ${balance.bank}\n "
                f"`📈` **INTEREST:** {settings.interest_rate * 100:g}%"
            ),
            inline=True,
        )
        await ctx.respond(embed=em)

    @bank.command()
    @option("amount", description="Specify the amount of Coins to Deposit")
    async def deposit(self, ctx: discord.ApplicationContext, amount: int):
        """
        Deposit your money to the bank
        """
        await guilds.ensure_guild(ctx.guild.id, ctx.guild.name)
        try:
            await bank.deposit(
                ctx.guild.id, ctx.author.id, ctx.author.display_name, amount
            )
        except BankError as error:
            await self._refuse(ctx, error)
            return
        await ctx.respond(f"You deposited {amount} :coin:!")

    @bank.command()
    @option("amount", description="Specify the amount of Coins to Withdraw")
    async def withdraw(self, ctx: discord.ApplicationContext, amount: int):
        """
        Withdraw your money from the bank
        """
        await guilds.ensure_guild(ctx.guild.id, ctx.guild.name)
        try:
            await bank.withdraw(
                ctx.guild.id, ctx.author.id, ctx.author.display_name, amount
            )
        except BankError as error:
            await self._refuse(ctx, error)
            return
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
        if member.bot:
            await ctx.respond("You can't send money to a bot.", ephemeral=True)
            return

        await guilds.ensure_guild(ctx.guild.id, ctx.guild.name)
        try:
            await bank.transfer(
                ctx.guild.id,
                ctx.author.id,
                ctx.author.display_name,
                member.id,
                member.display_name,
                amount,
            )
        except BankError as error:
            await self._refuse(ctx, error)
            return
        await ctx.respond(f"You gave {amount}:coin:! to {member.mention}")
