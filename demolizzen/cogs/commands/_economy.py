# Standard Library
import random

# Discord
import discord
from discord import option
from discord.ext import commands

# Demolizzen
from demolizzen.services import shop as shop_service
from demolizzen.services.errors import ItemNotOwned, NotEnoughItems, ShopError


async def get_bag_data(ctx: discord.AutocompleteContext) -> list[str]:
    """Suggest the items in the member's bag that start with what was typed."""
    typed = (ctx.value or "").lower()
    items = await shop_service.get_bag(
        ctx.interaction.guild.id, ctx.interaction.user.id
    )
    # Discord shows at most 25 suggestions.
    return [item.name for item in items if item.name.lower().startswith(typed)][:25]


class CommandsEconomy:
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @commands.slash_command(contexts=[discord.InteractionContextType.guild])
    @option("item_name", description="Pick your item!", autocomplete=get_bag_data)
    @option("amount", description="Specify amount")
    async def use(self, ctx: discord.ApplicationContext, item_name: str, amount: int):
        """
        Use an item from your bag
        """
        # Random Drink Text
        drinktext = [
            f"enjoys **`{item_name.capitalize()}`**.",
            f"drinks **`{item_name.capitalize()}`**.",
            f"opens **`{item_name.capitalize()}`** and downs it in one go.",
            f"shotguns **`{item_name.capitalize()}`**.",
            "🍺, Cheers!",
        ]
        # Random Drink Text
        drinktext2 = [
            f"knocks back **`{amount}`** x **`{item_name.capitalize()}`**, oh dear, that was too much 🤮!",
            f"cannot get enough and starts boozing **`{amount}`** x **`{item_name.capitalize()}`**.",
            f"has a crate full of **`{item_name.capitalize()}`** and starts drinking.",
            "... lies motionless on the floor. 🥴🥴",
        ]

        # The amount must be positive
        if amount <= 0:
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, 🙄 the number must be positive...",
            )
            await ctx.respond(embed=em)
            return

        # Take the items out of the bag
        try:
            used = await shop_service.use_item(
                ctx.guild.id, ctx.author.id, ctx.author.display_name, item_name, amount
            )
        except ItemNotOwned:
            problem = f"You don't have `{item_name.capitalize()}` in your bag"
        except NotEnoughItems:
            problem = f"You don't have enough `{item_name.capitalize()}` in your bag"
        except ShopError as error:
            problem = error.message
        else:
            problem = None
        if problem is not None:
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, {problem}",
            )
            await ctx.respond(embed=em)
            return

        # The shop files drinks under "drinks"; older bags may say "drink".
        if used.item_type in ("drink", "drinks"):
            if amount <= 1:
                em = discord.Embed(
                    title="",
                    color=discord.Color.teal(),
                    description=f"{ctx.author.mention}, "
                    + random.choice(drinktext)
                    + "",
                )
            else:
                em = discord.Embed(
                    title="",
                    color=discord.Color.teal(),
                    description=f"{ctx.author.mention}, "
                    + random.choice(drinktext2)
                    + "",
                )
        else:
            em = discord.Embed(
                title="",
                color=discord.Color.teal(),
                description=f"{ctx.author.mention}, uses {amount} x {item_name.capitalize()}",
            )
        await ctx.respond(embed=em)
