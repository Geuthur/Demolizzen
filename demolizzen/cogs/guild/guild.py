# Standard Library
import logging

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks

# Django
from django.db import close_old_connections

# Demolizzen
from demolizzen import models
from demolizzen.config import DEFAULT_BACKGROUND, DEFAULT_BORDER, DEFAULT_XP_COLOUR
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen
from demolizzen.utils.constants import PERMS_MAP

logger = logging.getLogger(__name__)


class Guild(commands.Cog):
    """
    Manage your Guild with automated Tools
    """

    def __init__(self, bot: Demolizzen):
        self.bot = bot
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
        close_old_connections()
        await self.check()

    @check_guild.before_loop
    async def before_check_guild(self):
        await self.bot.wait_until_ready()
        self.bot.logger.info("Guild and Member worker starting...")

    def cog_unload(self):
        self.check_guild.cancel()

    async def check(self):
        self.bot.logger.debug("Starting periodic check for guilds and members...")
        database_guilds = [
            obj.guild_id async for obj in models.GuildProfile.objects.all()
        ]
        bot_guild_ids = [guild.id for guild in self.bot.guilds]
        missing_guilds = set(database_guilds) - set(bot_guild_ids)

        for guild in self.bot.guilds:
            try:
                guild_profile = await models.GuildProfile.objects.aget(
                    guild_id=guild.id
                )
            except models.GuildProfile.DoesNotExist:
                # Create GuildProfile
                guild_profile = await models.GuildProfile.objects.acreate(
                    guild_id=guild.id, guild_name=guild.name
                )
                self.bot.logger.info(f"Added Guild {guild.name} to Database.")
            for member in guild.members:
                if not member.bot:
                    try:
                        user_profile = await models.UserProfile.objects.aget(
                            user_id=member.id, guild=guild_profile
                        )
                    except models.UserProfile.DoesNotExist:
                        user_profile = await models.UserProfile.objects.acreate(
                            user_id=member.id,
                            guild=guild_profile,
                            user_name=member.display_name,
                        )
                        await models.UserSettings.objects.acreate(
                            user=user_profile,
                            background=DEFAULT_BACKGROUND,
                            border=DEFAULT_BORDER,
                            xp_colour=DEFAULT_XP_COLOUR,
                            blur=5,
                        )
                        self.bot.logger.info(f"Added Member {member.name} to Database.")

        for guild_id in missing_guilds:
            try:
                guild_profile = await models.GuildProfile.objects.aget(
                    guild_id=guild_id
                )
                await guild_profile.adelete()
                self.bot.logger.info(f"Removed Guild ID {guild_id} from Database.")
            except models.GuildProfile.DoesNotExist:
                continue

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
        """Set Main Channel for Bots Interactions This not include Application Commands."""
        guild_profile = await models.GuildProfile.objects.aget(guild_id=ctx.guild.id)
        guild_profile.main_channel_id = channel.id
        await guild_profile.asave()
        embed = discord.Embed(
            description=f"🟢 **SUCCESS**: `📢 Main Channel set to: {channel.name}`"
        )
        return await ctx.respond(embed=embed)

    @guild.command()
    @commands.guild_only()
    @checks.is_guild_manager()
    async def unset_channel(self, ctx: discord.ApplicationContext):
        """Remove Main Channel for Bots Interactions."""
        guild_profile = await models.GuildProfile.objects.aget(guild_id=ctx.guild.id)

        if guild_profile.main_channel_id is None:
            embed = discord.Embed(
                description="🟡 **INFO**: `📢 Bot already react to all Channels`"
            )
            await ctx.respond(embed=embed)
            return

        # Remove all channels from the levelling server base
        guild_profile.main_channel_id = None
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

    # on guild join
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        # Check if Guild Profile already exists
        try:
            guild_profile = await models.GuildProfile.objects.aget(guild_id=guild.id)
            if guild_profile:
                logger.debug(
                    f"Levelling Serverbase for {guild.name} already exists, skipping creation."
                )
                return
        except models.GuildProfile.DoesNotExist:
            # Create GuildProfile
            guild_profile = await models.GuildProfile.objects.acreate(
                guild_id=guild.id, guild_name=guild.name
            )

            # Create levelling records for all members
            member_ids = [member.id for member in guild.members if not member.bot]
            existing_ids = [
                existing.user_id
                async for existing in models.UserProfile.objects.filter(
                    user_id__in=member_ids, guild_id=guild.id
                )
            ]

            new_members = [
                member
                for member in guild.members
                if member.id not in existing_ids and not member.bot
            ]
            new_user_profiles = []
            for member in new_members:
                new_user_profiles.append(
                    models.UserProfile(
                        user_id=member.id, guild_id=guild.id, user_name=member.name
                    )
                )
            if new_user_profiles:
                await models.UserProfile.objects.abulk_create(new_user_profiles)
                # Get the UserProfile objects from the DB to use them for UserSettings
                created_profiles = [
                    up
                    async for up in models.UserProfile.objects.filter(
                        user_id__in=[member.id for member in new_members],
                        guild_id=guild.id,
                    )
                ]
                new_settings = []
                for user_profile in created_profiles:
                    new_settings.append(
                        models.UserSettings(
                            user=user_profile,
                            background=DEFAULT_BACKGROUND,
                            border=DEFAULT_BORDER,
                            xp_colour=DEFAULT_XP_COLOUR,
                            blur=5,
                        )
                    )
                if new_settings:
                    await models.UserSettings.objects.abulk_create(new_settings)
            logger.info(
                f"{guild_profile} has joined and created with {len(new_user_profiles)} members successfully."
            )

        # Bank System - only execute if Bank cog is loaded
        bank_cog = self.bot.get_cog("Bank")
        if bank_cog is not None:
            try:
                guild_profile = await models.GuildProfile.objects.aget(
                    guild_id=guild.id
                )
                # TODO: Add bank system initialization logic here
            except models.GuildProfile.DoesNotExist:
                logger.warning(
                    f"Guild profile for guild {guild} ({guild.id}) does not exist."
                )
                return

    # on guild leave
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        # Delete GuildProfile and related data
        try:
            guild_profile = await models.GuildProfile.objects.aget(guild_id=guild.id)
            if guild_profile is not None:
                logger.info(f"Guild {guild_profile} has left and deleted successfully.")
                await guild_profile.adelete()
        except models.GuildProfile.DoesNotExist:
            logger.debug(f"Guild {guild.name} ({guild.id}) does not exist.")
            return
