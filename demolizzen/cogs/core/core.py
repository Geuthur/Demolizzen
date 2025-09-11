# Standard Library
import json

# Discord
import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands
from discord.ext.pages import Paginator

# Demolizzen
from demolizzen import models
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen
from demolizzen.utils.constants import PERMS_MAP
from demolizzen.utils.functions import application_cooldown


class Core(commands.Cog):
    """General bot functions."""

    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.title = "Core"
        self.alias = "core"

    botsettings = SlashCommandGroup(
        "bot", "Bot Settings", contexts=[discord.InteractionContextType.guild]
    )
    auth = SlashCommandGroup(
        "auth",
        "Authentication Commands",
        contexts=[discord.InteractionContextType.guild],
    )

    async def get_data(self, url, ctx: discord.ApplicationContext):
        """
        Base data retrieval method.
        """
        pages = []
        try:
            header = {"Accepts": "application/json"}
            async with self.bot.session.get(url, headers=header) as r:
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
            self.bot.logger.error(f"Error on Get Data: {e}")
            return None

    @auth.command(contexts=[discord.InteractionContextType.guild])
    async def register(self, ctx: discord.ApplicationContext):
        """Register User Profile for further use of the Bot"""
        # Erstelle eine Embed-Nachricht, um die Items anzuzeigen
        __, created = await models.UserProfile.objects.aget_or_create(
            user_id=ctx.author.id, guild_id=ctx.guild.id
        )

        if not created:
            embed = discord.Embed(
                title="Registration Failed",
                description=f"{ctx.author.mention}, you are already registered!",
                color=discord.Color.red(),
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(
            title="Registration Successful",
            description=f"Welcome {ctx.author.mention}! Your profile has been created.",
            color=discord.Color.green(),
        )
        await ctx.respond(embed=embed, ephemeral=True)

    @botsettings.command()
    @commands.cooldown(
        3, 600, commands.BucketType.user
    )  # 3 Mal alle 10 Minuten pro Benutzer
    async def uptime(self, ctx: discord.ApplicationContext):
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
            self.bot.logger.error(self.bot.guilds)
        await ctx.respond(embed=em)

    @uptime.error
    async def command_cooldown(self, ctx, error):
        await application_cooldown(ctx, error)

    @botsettings.command()
    async def changelog(self, ctx: discord.ApplicationContext):
        """
        Show the bot's changelog
        """
        em = discord.Embed(
            title="Changelog",
            color=discord.Color.blue(),
            description="Here is the changelog for the bot: [CHANGELOG.md](https://github.com/Geuthur/Demolizzen/blob/master/CHANGELOG.md)",
        )
        return await ctx.respond(embed=em)

    @botsettings.command()
    @commands.guild_only()
    @checks.is_guild_owner()
    async def set_channel(
        self, ctx: discord.ApplicationContext, channel: discord.TextChannel
    ):
        """Set Main Channel for Bots Interactions. Only for Server Owner."""
        guild_profile = await models.GuildProfile.objects.aget(guild_id=ctx.guild.id)
        guild_profile.main_channel = channel.id
        await guild_profile.asave()
        embed = discord.Embed(
            description=f"🟢 **SUCCESS**: `📢 Main Channel set to: {guild_profile.main_channel}`"
        )
        return await ctx.respond(embed=embed)

    @botsettings.command()
    @commands.guild_only()
    @checks.is_guild_owner()
    async def unset_channel(self, ctx: discord.ApplicationContext):
        """Remove Main Channel for Bots Interactions. Only for Server Owner."""
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

    @botsettings.command()
    @commands.guild_only()
    @checks.is_admin()
    async def perms_guild(self, ctx: discord.ApplicationContext):
        """Show permissions for Demolizzen for this Server. needs at Least Admin Permission."""

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
