# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands

# Demolizzen
from demolizzen import models
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen
from demolizzen.utils.constants import PERMS_MAP


class Guild(commands.Cog):
    """
    Manage your Guild with automated Tools
    """

    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.title = "Guild"
        self.alias = "guild"
        self.command_ids = {}

    guild = SlashCommandGroup(
        "guild",
        "Guild Commands",
        contexts=[discord.InteractionContextType.guild],
        default_member_permissions=discord.Permissions(manage_guild=True),
    )

    @guild.command(
        name="sync",
        description="Synchonizes the slash commands.",
    )
    @commands.is_owner()
    @option(
        "scope",
        description="The scope of the sync. Can be `global` or `guild`.",
        choices=["global", "guild"],
    )
    async def sync(self, context: discord.ApplicationContext, scope: str) -> None:
        """
        Synchonizes the slash commands.

        :param context: The command context.
        :param scope: The scope of the sync. Can be `global` or `guild`.
        """

        if scope == "global":
            await context.bot.sync_commands()
            embed = discord.Embed(
                description="Slash commands have been globally synchronized.",
                color=0xBEBEFE,
            )
            await context.respond(embed=embed)
            return
        await context.bot.sync_commands(guild_ids=[context.guild.id])
        embed = discord.Embed(
            description="Slash commands have been synchronized in this guild.",
            color=0xBEBEFE,
        )
        await context.respond(embed=embed, ephemeral=True)
        return

    @guild.command()
    @commands.guild_only()
    @checks.is_guild_manager()
    async def set_channel(
        self, ctx: discord.ApplicationContext, channel: discord.TextChannel
    ):
        """Set Main Channel for Bots Interactions. Only for Server Manager or higher."""
        guild_profile = await models.GuildProfile.objects.aget(guild_id=ctx.guild.id)
        guild_profile.main_channel = channel.id
        await guild_profile.asave()
        embed = discord.Embed(
            description=f"🟢 **SUCCESS**: `📢 Main Channel set to: {guild_profile.main_channel}`"
        )
        return await ctx.respond(embed=embed)

    @guild.command()
    @commands.guild_only()
    @checks.is_guild_manager()
    async def unset_channel(self, ctx: discord.ApplicationContext):
        """Remove Main Channel for Bots Interactions. Only for Server Manager or higher."""
        guild_profile = await models.GuildProfile.objects.aget(guild_id=ctx.guild.id)

        if guild_profile.main_channel is None:
            embed = discord.Embed(
                description="🟡 **INFO**: `📢 Bot already react to all Channels`"
            )
            await ctx.respond(embed=embed)
            return

        # Remove all channels from the levelling server base
        guild_profile.main_channel = None
        await guild_profile.asave()
        embed = discord.Embed(
            description="🟢 **SUCCESS**: `📢 Bot react to all Channels`"
        )
        await ctx.respond(embed=embed)

    @guild.command()
    @commands.guild_only()
    @checks.is_guild_manager()
    async def perms_guild(self, ctx: discord.ApplicationContext):
        """Show permissions for Demolizzen for this Server."""

        guild_perms = ctx.guild.me.guild_permissions
        perms_compare = guild_perms >= self.bot.req_perms
        msg = f"Server Permissions: {guild_perms.value}\n"
        msg += f"Met Minimum Permissions: {perms_compare}\n\n"

        if not perms_compare:
            msg += (
                "You can reconfigure the bot role by\n"
                f"[reauthorising the permissions here]({self.bot.invite_url}).\n\n"
                "The new auth will update the existing\n"
                "bot role automatically.\n\n"
            )

        for perm, bitshift in PERMS_MAP.items():
            if bool((self.bot.req_perms.value >> bitshift) & 1):
                if bool((guild_perms.value >> bitshift) & 1):
                    msg += f":white_small_square:  {perm}\n"
                else:
                    msg += f":black_small_square:  {perm}\n"

        embed = discord.Embed(
            title="Guild Permissions", color=discord.Color.blue(), description=f"{msg}"
        )

        try:
            if guild_perms.embed_links:
                await ctx.respond(embed=embed)
            else:
                await ctx.respond(msg)

        except discord.errors.Forbidden:
            await ctx.respond(embed=embed)
