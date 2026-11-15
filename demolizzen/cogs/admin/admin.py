# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands

# Django
from django.utils import timezone

# Demolizzen
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog


class Admin(BaseCog):
    """
    Secure the Server with automated Moderation Tools
    """

    key = "admin"

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
        self.title = "Admin"
        self.alias = "admin"
        self.command_ids = {}

    admin = SlashCommandGroup(
        "admin",
        "Adminsystem",
        contexts=[discord.InteractionContextType.guild],
        default_member_permissions=discord.Permissions(manage_guild=True),
    )
    mod = SlashCommandGroup(
        "moderation",
        "Moderation System",
        contexts=[discord.InteractionContextType.guild],
        default_member_permissions=discord.Permissions(manage_messages=True),
    )

    # ---------------------------- Moderation ----------------------------
    # ---------------------------- Moderation ----------------------------
    # ---------------------------- Moderation ----------------------------

    @mod.command()
    @commands.guild_only()
    @checks.is_mod()
    @option("limit", description="How many")
    async def clear(self, ctx: discord.ApplicationContext, limit: int):
        """Clear Message from a Channel."""
        await ctx.defer(ephemeral=True)

        if limit > 100:
            embed = discord.Embed(
                description="❌ No more than 100 messages can be purged at a time."
            )
            await ctx.respond(embed=embed, ephemeral=True, delete_after=20)
            return

        # Fetching the messages to delete
        # messages = await ctx.channel.history(limit=limit).flatten()
        # Fetching the messages to delete, only considering messages within the last 14 days
        try:
            messages = await ctx.channel.history(
                limit=limit,
                after=timezone.datetime.now() - timezone.timedelta(days=14),
                oldest_first=False,
            ).flatten()
        except discord.HTTPException as e:
            if e.code == 50001:  # Messages are older than 14 days
                pass
                # embed = discord.Embed(description="❌ I have no permission to see that channel...")
            else:
                self.bot.logger.error(e, exc_info=True)
                embed = discord.Embed(description="❌ Something went wrong try later.")
            return False

        if messages:
            try:
                # Try bulk deleting the messages
                await ctx.channel.delete_messages(messages)
                embed = discord.Embed(
                    description=f"✅ Deleted {len(messages)} message(s) bulk delete."
                )
            except discord.HTTPException as e:
                if e.code == 50034:  # Messages are older than 14 days
                    embed = discord.Embed(
                        description="❌ You can only bulk delete messages that are under 14 days old."
                    )
                elif e.code == 50013:  # No Permission
                    embed = discord.Embed(
                        description="❌ I have no permission to do that..."
                    )
                else:
                    self.bot.logger.error(e, exc_info=True)
                    embed = discord.Embed(
                        description="❌ Something went wrong try later."
                    )
        else:
            embed = discord.Embed(
                description="❌ No messages older than 14 days to delete."
            )
        await ctx.respond(embed=embed, ephemeral=True, delete_after=10)
