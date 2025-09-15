# Discord
import discord
from discord.ext import commands

# Demolizzen
from demolizzen.core.bot import Demolizzen


class CommandsHelp:
    """Help command to list all available commands."""

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
        self.bot = bot

    @commands.slash_command(contexts=[discord.InteractionContextType.guild])
    async def help(self, ctx: discord.ApplicationContext):
        """
        Get the list of available commands
        """
        await ctx.defer()
        server_id = ctx.guild.id
        embed = discord.Embed()
        embed.set_author(
            name=f"{ctx.bot.user.name} Plugin-Commands",
            icon_url=ctx.bot.user.display_avatar.url,
        )
        embed.set_thumbnail(url=ctx.bot.user.display_avatar.url)
        embed.color = discord.Color.blurple()
        embed.description = (
            "Select a category from the dropdown below to see its commands."
        )

        # Dynamisch Optionen für die Kategorien generieren
        options = []
        for plugin_name, cog in sorted(self.bot.cogs.items()):
            if hasattr(cog, "hidden") and cog.hidden:
                continue
            alias = getattr(cog, "alias", "None")
            access = getattr(cog, "access", "None")
            if alias == "None":
                continue
            if access != "None" and str(access) != str(server_id):
                continue

            # Check if the user has permission to view any command in the cog
            show_cog = True
            for command in cog.get_commands():
                if isinstance(command, discord.SlashCommandGroup):
                    perms = getattr(command, "default_member_permissions", None)
                    if perms is not None and isinstance(perms, discord.Permissions):
                        if (
                            not ctx.author.guild_permissions.value & perms.value
                            == perms.value
                        ):
                            show_cog = False
                            break

            if not show_cog:
                continue

            commands_info = [f"{command.name}" for command in cog.get_commands()]
            if commands_info:
                options.append(
                    discord.SelectOption(label=plugin_name, value=plugin_name)
                )

        if not options:
            embed.description = "No plugins/categories found."

        view = HelpSelect(self.bot, options)
        return await ctx.respond(embed=embed, view=view)


class HelpSelect(discord.ui.View):
    def __init__(self, bot: Demolizzen, options):
        super().__init__(timeout=30, disable_on_timeout=True)
        self.bot = bot
        self.value = None
        self.add_item(CategorySelect(bot, options))


class CategorySelect(discord.ui.Select):
    def __init__(self, bot: Demolizzen, options):
        super().__init__(
            placeholder="Choose a category", min_values=1, max_values=1, options=options
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        selected_item = self.values[0]
        plugin_name = selected_item
        info = discord.Embed()
        cog = self.bot.get_cog(selected_item)
        commands_info = []
        for command in cog.get_commands():
            options_info = []
            if isinstance(command, discord.commands.SlashCommandGroup):
                for subcommand in command.walk_commands():
                    if not subcommand.description == "No description provided":
                        commands_info.append(
                            f"</{subcommand}:{command.id}> \n {subcommand.description}\n"
                        )
            else:
                for opt in command.options:
                    options_info.append(
                        f"`{'(optional) ' if not opt.required else ''}{opt.name}`"
                    )
                options_info_str = " ".join(options_info)
                commands_info.append(
                    f"</{command.name}:{command.id}> {options_info_str} \n {command.description}\n"
                )
        info.add_field(
            name=f"**{plugin_name} Plugin**",
            value=f"\n {getattr(cog, 'description', '')}",
            inline=False,
        )
        info.add_field(name="", value="\n".join(commands_info), inline=False)
        await interaction.response.edit_message(content=None, embed=info)
