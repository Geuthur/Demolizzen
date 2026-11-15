# Standard Library
import logging

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks

# Demolizzen
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog
from demolizzen.services import guilds
from demolizzen.utils.constants import PERMS_MAP

logger = logging.getLogger(__name__)


class Guild(BaseCog):
    """
    Manage your Guild with automated Tools
    """

    key = "guild"

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
        self.title = "Guild"
        self.alias = "guild"
        self.command_ids = {}
        self.check_guild.start()

    guild = SlashCommandGroup(
        "guild",
        "Guild Commands",
        contexts=[discord.InteractionContextType.guild],
        default_member_permissions=discord.Permissions(manage_guild=True),
    )
    # Check for new Guild or Members every 2 Hours

    @tasks.loop(minutes=120)
    async def check_guild(self):
        """Periodic check for guilds and members in the bot's presence."""
        await self.check()

    @check_guild.before_loop
    async def before_check_guild(self):
        await self.bot.wait_until_ready()
        self.bot.logger.info("Guild and Member worker starting...")

    def cog_unload(self):
        self.check_guild.cancel()

    async def check(self):
        """Bring the database in line with the guilds and members the bot can see."""
        self.bot.logger.debug("Starting periodic check for guilds and members...")
        for guild in self.bot.guilds:
            _, created = await guilds.ensure_guild(guild.id, guild.name)
            if created:
                self.bot.logger.info(f"Added Guild {guild.name} to Database.")
            added = await guilds.ensure_members(
                guild.id,
                [
                    (member.id, member.display_name)
                    for member in guild.members
                    if not member.bot
                ],
            )
            if added:
                self.bot.logger.info(
                    f"Added {added} member(s) of {guild.name} to Database."
                )

        removed = await guilds.remove_missing_guilds(
            [guild.id for guild in self.bot.guilds]
        )
        for guild_id in removed:
            self.bot.logger.info(f"Removed Guild ID {guild_id} from Database.")

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

        # Registering takes longer than Discord waits for an answer.
        await context.defer(ephemeral=True)
        if scope == "global":
            await context.bot.sync_commands()
            embed = discord.Embed(
                description="Slash commands have been globally synchronized.",
                color=0xBEBEFE,
            )
            await context.respond(embed=embed)
            return
        # Only this server: its modules decide which commands it gets.
        if await context.bot.command_scope.sync_guild(context.guild.id):
            description = "Slash commands have been synchronized in this guild."
        else:
            description = (
                "Slash commands could not be synchronized in this guild. "
                "The log says why."
            )
        embed = discord.Embed(description=description, color=0xBEBEFE)
        await context.respond(embed=embed, ephemeral=True)
        return

    @guild.command()
    @commands.guild_only()
    @checks.is_guild_manager()
    async def set_channel(
        self, ctx: discord.ApplicationContext, channel: discord.TextChannel
    ):
        """Set Main Channel for Bots Interactions This not include Application Commands."""
        await guilds.ensure_guild(ctx.guild.id, ctx.guild.name)
        await guilds.set_main_channel(ctx.guild.id, channel.id)
        embed = discord.Embed(
            description=f"🟢 **SUCCESS**: `📢 Main Channel set to: {channel.name}`"
        )
        return await ctx.respond(embed=embed)

    @guild.command()
    @commands.guild_only()
    @checks.is_guild_manager()
    async def unset_channel(self, ctx: discord.ApplicationContext):
        """Remove Main Channel for Bots Interactions."""
        await guilds.ensure_guild(ctx.guild.id, ctx.guild.name)
        if not await guilds.set_main_channel(ctx.guild.id, None):
            embed = discord.Embed(
                description="🟡 **INFO**: `📢 Bot already react to all Channels`"
            )
            await ctx.respond(embed=embed)
            return

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

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Register the guild and its human members."""
        guild_profile, _ = await guilds.ensure_guild(guild.id, guild.name)
        added = await guilds.ensure_members(
            guild.id,
            [(member.id, member.name) for member in guild.members if not member.bot],
        )
        logger.info(f"{guild_profile} has joined and created with {added} members.")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        """Delete the guild and everything that belongs to it."""
        if await guilds.remove_guild(guild.id):
            logger.info(f"Guild {guild.name} ({guild.id}) has left and was deleted.")
        else:
            logger.debug(f"Guild {guild.name} ({guild.id}) does not exist.")

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        """Keep the stored guild name current."""
        if await guilds.rename_guild(after.id, after.name):
            logger.info(f"Guild {before.name} ({after.id}) changed to {after.name}.")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Keep the stored member name current."""
        if before.name == after.name:
            return
        if await guilds.rename_member(after.guild.id, after.id, after.name):
            logger.info(
                f"User {before.name} ({after.id}) changed to {after.name} "
                f"in guild {after.guild.name} ({after.guild.id})."
            )
