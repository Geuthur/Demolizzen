# Discord
import discord
from discord.ext import commands
from discord.ext.pages import Paginator

# Demolizzen
from demolizzen.core.bot import Demolizzen
from demolizzen.services import bank, shop
from demolizzen.utils.functions import get_command_mention

MAX_BAG_FIELDS = 25


class CommandsBase:
    def __init__(self, bot: Demolizzen):
        self.bot = bot

    @commands.slash_command(
        name="donate", contexts=[discord.InteractionContextType.guild]
    )
    async def donate(self, ctx):
        """
        Support the Bot Programmer with a small donation
        """
        await ctx.respond("Feel free to Donate if you want ♥")
        await ctx.respond("https://www.paypal.com/paypalme/HellRiderZ")

    @commands.slash_command(contexts=[discord.InteractionContextType.guild])
    async def bag(self, ctx: discord.ApplicationContext):
        """
        Show you items in the bag
        """
        items = await shop.get_bag(ctx.guild.id, ctx.author.id)
        if not items:
            app_command = get_command_mention(
                bot=self.bot,
                cog="Shop",
                slash_command="shop",
                slash_command_group="buy",
            )
            em = discord.Embed(
                description=f"{ctx.author.mention}, Your Bag is empty... Buy something with {app_command}",
                color=discord.Color.teal(),
            )
            await ctx.respond(embed=em)
            return

        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Bag", color=discord.Color.teal()
        )
        # An embed holds 25 fields at most.
        for item in items[:MAX_BAG_FIELDS]:
            embed.add_field(
                name=item.name, value=f"Quantity: {item.quantity}", inline=False
            )
        if len(items) > MAX_BAG_FIELDS:
            embed.set_footer(text=f"… and {len(items) - MAX_BAG_FIELDS} more")
        await ctx.respond(embed=embed)

    class LeaderboardPaginator(Paginator):
        def __init__(self, pages, timeout):
            super().__init__(pages, timeout=timeout)

        async def on_timeout(self) -> None:
            if isinstance(self.message, discord.Interaction):
                await self.message.delete()
            else:
                await self.message.delete()

    @commands.slash_command(contexts=[discord.InteractionContextType.guild])
    async def richest(self, ctx: discord.ApplicationContext):
        """
        Get Information about the Richest Players
        """
        richest = await bank.richest(ctx.guild.id)
        if not richest.top:
            await ctx.respond(
                "No users found in the database. Please try again later.",
                ephemeral=True,
                delete_after=60,
            )
            return

        pages = []
        description = f":bank: Server Total :coin: {richest.total}\n\n"
        medals = {1: ":first_place:", 2: ":second_place:", 3: ":third_place:"}
        for number, (name, wallet) in enumerate(richest.top, start=1):
            place = medals.get(number, f"#{number}")
            description += f"{place} {name} :coin: {wallet}\n"

        embed = discord.Embed(
            title=f"{ctx.guild.name} Richest Players",
            color=discord.Color.teal(),
        )
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        embed.description = description
        pages.append(embed)

        paginator = self.LeaderboardPaginator(pages=pages, timeout=60)
        await paginator.respond(ctx.interaction)
