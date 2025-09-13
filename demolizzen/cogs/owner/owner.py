# Standard Library
import logging
import subprocess
import sys
from pathlib import Path

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands

# Demolizzen
from demolizzen.cogs.banksystem import Bank
from demolizzen.cogs.economy import Economy
from demolizzen.core.bot import Demolizzen


class Owner(commands.Cog):
    """Owner Only Commands."""

    def __init__(self, bot: Demolizzen):
        self.bot = bot

    owner = SlashCommandGroup(
        "owner", "Owner Commands", contexts=[discord.InteractionContextType.bot_dm]
    )

    guild = SlashCommandGroup(
        "guild", "Guild Commands", contexts=[discord.InteractionContextType.guild]
    )

    @owner.command(name="force-deposits-update")
    @commands.is_owner()
    async def trigger_deposit_update(self, ctx: discord.ApplicationContext):
        """Force a deposit update."""
        banksystem_cog: Bank = self.bot.get_cog("Bank")
        await banksystem_cog.process_daily_interest()
        await ctx.respond("Deposit Update Triggered.", ephemeral=True)

    @owner.command(name="force-ship-update")
    @commands.is_owner()
    async def trigger_ship_update(self, ctx: discord.ApplicationContext):
        """Force a ship data update."""
        shopsystem_cog: Economy = self.bot.get_cog("Eco")
        await shopsystem_cog.fetch_ship_data()
        await ctx.respond("Ship Data Update Triggered.", ephemeral=True)

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

    @owner.command(
        name="load",
        description="Load a cog",
    )
    @commands.is_owner()
    async def load(self, ctx: discord.ApplicationContext, cog: str) -> None:
        """
        The bot will load the given cog.

        :param context: The application context.
        :param cog: The name of the cog to load.
        """
        try:
            self.bot.load_extension(f"demolizzen.cogs.{cog}")
        except Exception:
            embed = discord.Embed(
                description=f"Could not load the `{cog}` cog.", color=0xE02B2B
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(
            description=f"Successfully loaded the `{cog}` cog.", color=0xBEBEFE
        )
        await ctx.respond(embed=embed, ephemeral=True)

    @owner.command(
        name="unload",
        description="Unloads a cog.",
    )
    @commands.is_owner()
    async def unload(self, ctx: discord.ApplicationContext, cog: str) -> None:
        """
        The bot will unload the given cog.

        :param context: The application context.
        :param cog: The name of the cog to unload.
        """
        try:
            self.bot.unload_extension(f"demolizzen.cogs.{cog}")
        except Exception:
            embed = discord.Embed(
                description=f"Could not unload the `{cog}` cog.", color=0xE02B2B
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(
            description=f"Successfully unloaded the `{cog}` cog.", color=0xBEBEFE
        )
        await ctx.respond(embed=embed, ephemeral=True)

    @owner.command(
        name="reload",
        description="Reloads a cog.",
    )
    @commands.is_owner()
    async def reload(self, ctx: discord.ApplicationContext, cog: str) -> None:
        """
        The bot will reload the given cog.

        :param context: The application context.
        :param cog: The name of the cog to reload.
        """
        try:
            self.bot.reload_extension(f"demolizzen.cogs.{cog}")
        except Exception as e:
            self.bot.logger.error(e, exc_info=True)
            embed = discord.Embed(
                description=f"Could not reload the `{cog}` cog.", color=0xE02B2B
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(
            description=f"Successfully reloaded the `{cog}` cog.", color=0xBEBEFE
        )
        await ctx.respond(embed=embed, ephemeral=True)

    @owner.command(name="migrate", description="Trigger database migrations")
    @commands.is_owner()
    async def trigger_migrations(self, ctx: discord.ApplicationContext):
        """Trigger database migrations (runs 'python manage.py migrate')"""
        await ctx.defer(ephemeral=True)
        project_root = Path(__file__).resolve().parents[3]
        cwd = str(project_root)
        try:
            # Run the migration command and capture output
            result = subprocess.run(
                [sys.executable, "manage.py", "migrate"],
                check=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            output = result.stdout.strip() or result.stderr.strip() or "No output."
            # Discord message limit is 2000 chars
            if len(output) > 1900:
                output = output[:1900] + "\n...output truncated."
            await ctx.respond(f"```\n{output}\n```", ephemeral=True)
        except Exception as e:
            self.bot.logger.error(f"Error running migrations: {e}")
            await ctx.respond(
                "Something went wrong while running migrations", ephemeral=True
            )

    @owner.command(name="setloglevel", description="Set the bot's log level")
    @commands.is_owner()
    @option(
        "level",
        description="Choose Log Level",
        choices=["debug", "info", "warning", "error", "critical"],
    )
    async def setloglevel(self, ctx: discord.ApplicationContext, level: str):
        """Set log level dynamically."""
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

        self.bot.logger.setLevel(log_level)
        await ctx.respond(f"Log level set to {level.upper()}.", ephemeral=True)

    @owner.command(name="activity", description="Set the bot's activity")
    @commands.is_owner()
    async def activity(
        self,
        ctx: discord.ApplicationContext,
        *,
        activity: discord.Game = None,
    ):
        """Set bot activity."""
        await self.bot.change_presence(status="online", activity=activity)
        await ctx.respond(
            f"Activity set to {activity}.", ephemeral=True, delete_after=10
        )

    @owner.command(name="status", description="Set the bot's status")
    @commands.is_owner()
    @option("status", description="Change Status", choices=["online", "idle", "dnd"])
    async def status(
        self,
        ctx: discord.ApplicationContext,
        *,
        status: str,
    ):
        """Set bot status to online, idle or dnd."""
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
