# Standard Library
import random

# Discord
import discord
from discord import option
from discord.ext import commands
from discord.ext.pages import Paginator

# Demolizzen
from demolizzen import models
from demolizzen.core.bot import Demolizzen


# Automatische auswahl für Tasche von jeweiligen Discord User
async def get_bag_data(ctx: discord.AutocompleteContext):
    # SQL-Abfrage, um das ausgewählte Item zu finden
    try:
        user = await models.UserProfile.objects.select_related("bags").aget(
            user_id=ctx.interaction.user.id, guild_id=ctx.interaction.guild.id
        )
    except models.UserProfile.DoesNotExist:
        return []
    except models.UserBag.DoesNotExist:
        return []

    return [
        item.item_name
        async for item in user.bags.items.all()
        if item.item_name.lower().startswith(ctx.value.lower())
    ]


class Commands(commands.Cog):
    """
    A list of commands that can help you.
    """

    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.title = "Commands"
        self.alias = "commands"

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        try:
            user = await models.UserProfile.objects.select_related(
                "bank_account", "bags"
            ).aget(user_id=ctx.author.id, guild_id=ctx.guild.id)
            ctx.user_profile = user
            self.bot.logger.debug(f"UserProfile loaded for {ctx.author}.")
        except models.UserProfile.DoesNotExist as exc:
            raise commands.CheckFailure(
                "UserProfile does not exist. Please register first. `/auth register`"
            ) from exc

    async def get_richest_data(self, ctx: discord.ApplicationContext):
        return [
            account
            async for account in models.BankAccount.objects.filter(
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
    @option(
        "plugin_name",
        description="Name a plugin to explore its commands.",
        required=False,
    )
    # pylint: disable=too-many-statements
    async def help(self, ctx, plugin_name=None):
        """
        Get the list of available commands
        """
        server_id = ctx.guild.id
        embed = discord.Embed()
        # Füge das Profilbild des Bots als Thumbnail hinzu
        embed.set_author(
            name=f"{ctx.bot.user.name} Plugin-Commands",
            icon_url=ctx.bot.user.display_avatar.url,
        )
        embed.set_thumbnail(url=ctx.bot.user.display_avatar.url)

        class HelpSelect(discord.ui.View):
            def __init__(self, bot: Demolizzen):
                super().__init__(timeout=30)
                self.value = None
                self.bot = bot

            async def on_timeout(self) -> None:
                try:
                    self.disable_all_items()
                    if isinstance(self.message, discord.Interaction):
                        view.message = await self.message.edit_original_response(
                            view=view
                        )
                        # await self.message.edit_original_response(view=self)
                    else:
                        view.message = await view.message.edit(view=view)
                    # await self.message.edit_original_response(view=self)
                # pylint: disable=broad-except
                except Exception as e:
                    if "Missing Access" in str(e):
                        allowed_channels = [
                            c
                            for c in self.message.guild.channels
                            if isinstance(c, discord.TextChannel)
                            and c.permissions_for(self.message.guild.me).send_messages
                        ]
                        alternative_channel = allowed_channels[0]
                        await alternative_channel.send(
                            f"❌ Permission ERROR: The Help Command couldn't edit Help Status in **<#{self.message.channel.id}>**"
                        )
                        return
                    self.bot.logger.error(e, exc_info=True)

            async def on_error(self, interaction, error, item):
                print(str(interaction))
                print("------------------------")
                print(str(error))
                print("------------------------")
                print(str(item))

            options = []

            for plugin_name, cog in sorted(self.bot.cogs.items()):
                alias = getattr(cog, "alias", "None")
                access = getattr(cog, "access", "None")
                # Überprüfen, ob der Cog geladen werden soll
                if alias == "None":
                    continue
                # Wenn "access" eine einzelne Server-ID ist
                if access != "None" and str(access) != str(server_id):
                    continue
                commands_info = []
                for command in cog.get_commands():
                    commands_info.append(f"{command.name}")

                if commands_info:
                    options.append(
                        discord.SelectOption(label=plugin_name, value=plugin_name)
                    )

            @discord.ui.select(placeholder="", options=options)
            # Verarbeiten Sie die Auswahl des Benutzers
            async def help_select(self, select, interaction):
                selected_item = select.values[0]  # Der ausgewählte Artikel
                plugin_name = select.values[0]
                info = discord.Embed()
                # Füge das Profilbild des Bots als Thumbnail hinzu
                cog = self.bot.get_cog(selected_item)
                commands_info = []

                for command in cog.get_commands():
                    options_info = []
                    if isinstance(
                        command, discord.commands.SlashCommandGroup
                    ):  # check if it has subcommands
                        command.id = command.id
                        for (
                            subcommmand
                        ) in (
                            command.walk_commands()
                        ):  # iterate through all of the command's parents/subcommands
                            if not subcommmand.description == "No description provided":
                                commands_info.append(
                                    f"</{subcommmand}:{command.id}> \n {subcommmand.description}\n"
                                )
                    else:
                        for options in command.options:
                            options_info.append(
                                f"`{'(optional) ' if not options.required else ''}{options.name}`"
                            )
                        options_info_str = " ".join(options_info)
                        commands_info.append(
                            f"</{command.name}:{command.id}> {options_info_str} \n {command.description}\n"
                        )
                info.add_field(
                    name=f"**{plugin_name} Plugin**",
                    value=f"\n {cog.description}",
                    inline=False,
                )
                info.add_field(name="", value="\n".join(commands_info), inline=False)
                await interaction.response.edit_message(content=None, embed=info)
                # await interaction.message.edit(embed=info)

        if plugin_name is None:
            # Loop through the cogs and their commands
            for _, cog in sorted(self.bot.cogs.items()):
                alias = getattr(cog, "alias", "None")
                access = getattr(cog, "access", "None")
                # Überprüfen, ob der Cog geladen werden soll
                if alias == "None":
                    continue
                # Wenn "access" eine einzelne Server-ID ist
                if access != "None" and str(access) != str(server_id):
                    continue
                commands_info = []
                for command in cog.get_commands():
                    commands_info.append(f"{command.name}")

                if commands_info:
                    title = getattr(cog, "title", "None")
                    embed.add_field(
                        name=title,
                        value=f"</help:1146893611506610349> `{alias}`",
                        inline=True,
                    )
        else:
            if plugin_name or plugin_name.capitalize():
                plugin_name = plugin_name.capitalize()
                # Wenn ein Cog-Name angegeben wurde, zeige Befehle und Beschreibungen für dieses Cog
                cog = self.bot.get_cog(plugin_name)
                if cog:
                    commands_info = []
                    title = getattr(cog, "title", "None")
                    for command in cog.get_commands():
                        options_info = []
                        if isinstance(
                            command, discord.commands.SlashCommandGroup
                        ):  # check if it has subcommands
                            command.id = command.id
                            for (
                                subcommmand
                            ) in (
                                command.walk_commands()
                            ):  # iterate through all of the command's parents/subcommands
                                if (
                                    not subcommmand.description
                                    == "No description provided"
                                ):
                                    commands_info.append(
                                        f"</{subcommmand}:{command.id}> \n {subcommmand.description}\n"
                                    )
                        else:
                            for options in command.options:
                                options_info.append(
                                    f"`{'(optional) ' if not options.required else ''}{options.name}`"
                                )
                            options_info_str = " ".join(options_info)
                            commands_info.append(
                                f"</{command.name}:{command.id}> {options_info_str} \n {command.description}\n"
                            )
                    embed.add_field(
                        name=f"**{title} Plugin**",
                        value=f"\n {cog.description}",
                        inline=False,
                    )
                    embed.add_field(
                        name="", value="\n".join(commands_info), inline=False
                    )
                else:
                    title = plugin_name
                    embed.add_field(
                        name="Error", value=f"Cog '{title}' not found", inline=False
                    )
                    embed.add_field(
                        name="", value="Use the Dropdown menu", inline=False
                    )
        view = HelpSelect(self.bot)
        message = await ctx.respond(embed=embed, view=view)
        view.message = message

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
        except (models.BagItems.DoesNotExist, models.UserBag.DoesNotExist):
            em = discord.Embed(
                description=f"{ctx.author.mention}, Your Bag is empty... Buy something with /buy",
                color=discord.Color.teal(),
            )
            await ctx.respond(embed=em)
            return

        await ctx.respond(embed=embed)

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
            user_bag_items = await models.BagItems.objects.aget(
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
        except models.BagItems.DoesNotExist:
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
