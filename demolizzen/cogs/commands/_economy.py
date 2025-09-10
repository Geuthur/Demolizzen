# Standard Library
import random

# Discord
import discord
from discord import option
from discord.ext import commands

# Demolizzen
from demolizzen import models


# Automatische auswahl für Tasche von jeweiligen Discord User
async def get_bag_data(ctx: discord.AutocompleteContext):
    # SQL-Abfrage, um das ausgewählte Item zu finden
    try:
        user = await models.UserProfile.objects.select_related("bags").aget(
            user_id=ctx.interaction.user.id, guild_id=ctx.interaction.guild.id
        )
        items = [
            item.item_name
            async for item in user.bags.items.all()
            if item.item_name.lower().startswith(ctx.value.lower())
        ]
    except models.UserProfile.DoesNotExist:
        return []
    except models.UserBag.DoesNotExist:
        return []
    except models.UserBagItems.DoesNotExist:
        return []
    return items


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
            f"genießt **`{item_name.capitalize()}`**.",
            f"trinkt **`{item_name.capitalize()}`**.",
            f"öffnet und ex't **`{item_name.capitalize()}`**.",
            f"tornadot **`{item_name.capitalize()}`**.",
            "🍺, Prost!",
        ]
        # Random Drink Text
        drinktext2 = [
            f"schießt sich **`{amount}`** x **`{item_name.capitalize()}`**, oweia ich glaub das war zuviel 🤮!",
            f"kann nicht genug bekommen und fängt an **`{amount}`** x **`{item_name.capitalize()}`** zu saufen.",
            f"hat einen Kasten voll/er **`{item_name.capitalize()}`** und fängt an zu trinken.",
            "... liegt am boden regungslos. 🥴🥴",
        ]

        # Überprüfe, ob die Menge positiv ist
        if amount <= 0:
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, 🙄 the number must be positive...",
            )
            await ctx.respond(embed=em)
            return

        # Get User Bag Item
        try:
            user_bag_items = await models.UserBagItems.objects.aget(
                user_bag=ctx.user_profile.bags,
                item_name=item_name,
            )
        except models.UserBag.DoesNotExist:
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, Your Bag is empty... Buy something with /buy",
            )
            await ctx.respond(embed=em)
            return
        except models.UserBagItems.DoesNotExist:
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, You don't have `{item_name.capitalize()}` in your bag",
            )
            await ctx.respond(embed=em)
            return

        # Überprüfe, ob genug Items vorhanden sind
        if user_bag_items.quantity < amount:
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, You don't have enough `{item_name.capitalize()}` in your bag",
            )
            await ctx.respond(embed=em)
            return

        # Aktualisiere die Menge des Items im Bag
        changed_quantity = user_bag_items.quantity - amount
        user_bag_items.quantity = changed_quantity

        # Update the item quantity in the database
        await user_bag_items.asave()

        if user_bag_items.item_type == "drink":
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
                description=f"{ctx.author.mention}, benutzt {amount} x {item_name.capitalize()}",
            )
        await ctx.respond(embed=em)
