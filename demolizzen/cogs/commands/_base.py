# Discord
import discord
from discord.ext import commands
from discord.ext.pages import Paginator

# Demolizzen
from demolizzen import models
from demolizzen.core.bot import Demolizzen
from demolizzen.utils.functions import get_command_mention


class CommandsBase:
    def __init__(self, bot: Demolizzen):
        self.bot = bot

    async def get_richest_data(self, ctx: discord.ApplicationContext):
        return [
            account
            async for account in models.UserBankAccount.objects.filter(
                user__guild_id=ctx.guild.id
            ).select_related("user")
        ]

    @commands.slash_command(
        name="spenden", contexts=[discord.InteractionContextType.guild]
    )
    async def spenden(self, ctx):
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
        # Erstelle eine Embed-Nachricht, um die Items anzuzeigen
        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Bag", color=discord.Color.teal()
        )
        try:
            bags: models.UserBag = ctx.user_profile.bags
            user_bag = [item async for item in bags.items.all()]
            for user_item in user_bag:
                item_name = user_item.item_name
                item_quantity = user_item.quantity

                embed.add_field(
                    name=item_name, value=f"Anzahl: {item_quantity}", inline=False
                )
        except (models.UserBagItems.DoesNotExist, models.UserBag.DoesNotExist):
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
        # Fetch User Data
        users = await self.get_richest_data(ctx)

        if not users:
            await ctx.respond(
                "No users found in the database. Please try again later.",
                ephemeral=True,
                delete_after=60,
            )
            return

        total = sum(user.wallet for user in users if hasattr(user, "wallet"))
        pages = []
        description = ""

        description += f":bank: Server Total :coin: {total}\n\n"

        # Nur die Top 10 Spieler anzeigen
        top_users = sorted(users, key=lambda x: x.wallet, reverse=True)[:10]

        for number, user in enumerate(top_users, start=1):
            name = user.user.user_name
            wallet = user.wallet if hasattr(user, "wallet") else 0

            if number == 1:
                place_emoji = ":first_place:"
                description += f"{place_emoji} {name.capitalize()} :coin: {wallet}\n"
            elif number == 2:
                place_emoji = ":second_place:"
                description += f"{place_emoji} {name.capitalize()} :coin: {wallet}\n"
            elif number == 3:
                place_emoji = ":third_place:"
                description += f"{place_emoji} {name.capitalize()} :coin: {wallet}\n"
            else:
                description += f"#{number} {name.capitalize()} :coin: {wallet}\n"

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
