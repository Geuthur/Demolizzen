import json
import logging

import discord
from core import checks
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands
from discord.ext.pages import Paginator
from settings.functions import application_cooldown

log = logging.getLogger("main")

PERMS_MAP = {
    "create_instant_invite": 0,
    "kick_members": 1,
    "ban_members": 2,
    "administrator": 3,
    "manage_channels": 4,
    "manage_guild": 5,
    "add_reactions": 6,
    "view_audit_log": 7,
    "priority_speaker": 8,
    "stream": 9,
    "read_messages": 10,
    "send_messages": 11,
    "send_tts_messages": 12,
    "manage_messages": 13,
    "embed_links": 14,
    "attach_files": 15,
    "read_message_history": 16,
    "mention_everyone": 17,
    "use_external_emojis": 18,
    "view_guild_insights": 19,
    "connect": 20,
    "speak": 21,
    "mute_members": 22,
    "deafen_members": 23,
    "move_members": 24,
    "use_voice_activation": 25,
    "change_nickname": 26,
    "manage_nicknames": 27,
    "manage_roles": 28,
    "manage_webhooks": 29,
    "manage_emojis": 30,
    "use_application_commands": 31,
    "request_to_speak": 32,
    "manage_events": 33,
    "manage_threads": 34,
    "create_public_threads": 35,
    "create_private_threads": 36,
    "use_external_stickers": 37,
    "send_messages_in_threads": 38,
    "use_embedded_activities": 39,
    "moderate_members": 40,
}


class Core(commands.Cog):
    """General bot functions."""

    def __init__(self, bot):
        self.session = bot.session
        self.bot = bot

    botsettings = SlashCommandGroup("bot", "Bot Settings")

    async def get_data(self, url, ctx: discord.ApplicationContext):
        """
        Base data retrieval method.
        """
        pages = []
        try:
            header = {"Accepts": "application/json"}
            async with self.session.get(url, headers=header) as r:
                try:
                    changelog_data = await r.json()
                    changelog_data = changelog_data[::-1]
                    for entry in changelog_data:
                        version = entry["version"]
                        changes = "\n".join(entry["changes"])

                        embed = discord.Embed(
                            title=f"Changelog Demo Bot {version}",
                            description=f"\n{changes}",
                            color=discord.Color.blurple(),
                        )

                        pages.append(embed)
                except json.JSONDecodeError:
                    return None
            paginator = Paginator(pages=pages, timeout=30)
            message = await paginator.respond(ctx.interaction)
            return message
        # pylint: disable=broad-except
        except Exception as e:
            # Handle the connection error here
            log.error(f"Error on Get Data: {e}")
            return None

    @botsettings.command()
    @checks.is_owner()
    async def activity(
        self: discord.ApplicationContext,
        ctx: discord.ApplicationContext,
        *,
        activity: discord.Game = None,
    ):
        """
        Set bot activity
        """
        await self.bot.change_presence(status="online", activity=activity)
        await ctx.respond(
            f"Activity set to {activity}.", ephemeral=True, delete_after=10
        )

    @botsettings.command()
    @checks.is_owner()
    @option("status", description="Change Status", choices=["online", "idle", "dnd"])
    async def status(
        self: discord.ApplicationContext,
        ctx: discord.ApplicationContext,
        *,
        status: str,
    ):
        """
        Set bot status to online, idle or dnd
        """
        try:
            status = discord.Status[status.lower()]
        except KeyError:
            await ctx.error(
                "Invalid Status",
                "Only `online`, `idle` or `dnd` statuses are available.",
            )
        else:
            await self.bot.change_presence(status=status, activity=ctx.me.activity)
            await ctx.respond(
                f"Status changed to `{status}`.", ephemeral=True, delete_after=10
            )

    @botsettings.command()
    @commands.cooldown(
        3, 600, commands.BucketType.user
    )  # 3 Mal alle 10 Minuten pro Benutzer
    async def uptime(self: discord.ApplicationContext, ctx: discord.ApplicationContext):
        """
        Show how long the bot has been running for
        """
        # https://i.imgur.com/82Cqf1x.png
        em = discord.Embed(
            title="Uptime",
            color=discord.Color.blue(),
            description=f"{self.bot.uptime_str}",
        )
        guilds = len(self.bot.guilds)
        users = len(list(self.bot.get_all_members()))
        if guilds:
            em.add_field(
                name="", value=f"Servers: {guilds} - Members: {users}", inline=False
            )
        if ctx.user.id == 240850566002114561:
            log.error(self.bot.guilds)
        await ctx.respond(embed=em)

    @uptime.error
    async def command_cooldown(self, ctx, error):
        await application_cooldown(ctx, error)

    @botsettings.command(contexts=[discord.InteractionContextType.guild])
    @commands.cooldown(
        3, 600, commands.BucketType.user
    )  # 3 Mal alle 10 Minuten pro Benutzer
    async def changelog(self, ctx: discord.ApplicationContext):
        """
        Show the bot's changelog
        """
        await ctx.defer()
        try:
            await self.get_data("https://hell-rider.de/api/discord_changelog", ctx)
        # pylint: disable=broad-except
        except Exception:
            await ctx.respond("Failed to fetch changelog. Try again later.")

    @changelog.error
    async def changelog_cooldown(self, ctx, error):
        await application_cooldown(ctx, error)

    @botsettings.command(contexts=[discord.InteractionContextType.guild])
    @commands.is_owner()
    @option(
        "level",
        description="Choose Log Level",
        choices=["debug", "info", "warning", "error", "critical"],
    )
    @option(
        "logname",
        description="Choose Log Type",
        choices=["main", "demolizzen", "discord", "killboard", "testing", "db"],
    )
    async def setloglevel(
        self, ctx: discord.ApplicationContext, level: str, logname: str
    ):
        """
        Set log level dynamically
        """
        log_level_map = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }

        log_level = log_level_map.get(level.lower())

        if log_level is None:
            await ctx.respond("Invalid log level.")
            return

        def change_logger_specific(logname, log_level=logging.INFO):
            logger_dict = {
                "discord": logging.getLogger("discord"),
                "demolizzen": logging.getLogger("demolizzen"),
                "main": logging.getLogger("main"),
                "killboard": logging.getLogger("killboard"),
                "testing": logging.getLogger("testing"),
                "db": logging.getLogger("db"),
            }

            if logname in logger_dict:
                logger_name = logger_dict[logname]
                logger_name.setLevel(log_level)
            else:
                ctx.respond(f"Logger with name '{logname}' not found.")

        change_logger_specific(logname, log_level)
        await ctx.respond(f"Log level for '{logname}' set to {level.upper()}.")

    @botsettings.command()
    @checks.is_admin()
    async def perms_guild(
        self: discord.ApplicationContext, ctx: discord.ApplicationContext
    ):
        """
        Show permissions for Demolizzen for this Server.
        """

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


def setup(bot):
    bot.add_cog(Core(bot))
