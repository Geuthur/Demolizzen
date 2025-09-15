# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands

# Django
from django.utils import timezone

# Demolizzen
from demolizzen.config import EVENTS_SERVER
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen


class Admin(commands.Cog):
    """
    Secure the Server with automated Moderation Tools
    """

    def __init__(self, bot: Demolizzen):
        self.bot = bot
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
    economy = admin.create_subgroup(
        "economy", contexts=[discord.InteractionContextType.guild]
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
        # await ctx.defer(ephemeral=True)

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

    # ---------------------------- Mission System ----------------------------
    # ---------------------------- Mission System ----------------------------
    # ---------------------------- Mission System ----------------------------

    @economy.command(
        name="mode", description="Start or Stop the Event for the Economy System"
    )
    @commands.guild_only()
    @checks.is_admin()
    @option(
        "action",
        description="Start or Stop the Event for the Economy System",
        choices=["On", "Off", "Status"],
    )
    async def mode(self, ctx, action: str):
        """Start or Stop the Event for the Economy System."""

        server_id = ctx.guild.id

        if server_id in EVENTS_SERVER:
            events, event_factor = EVENTS_SERVER[server_id]
        else:
            EVENTS_SERVER[server_id] = (False, 0)
            events, event_factor = EVENTS_SERVER[server_id]

        if action == "Status":
            if events:
                await ctx.respond(f"🟢 Event ist aktiv.\n Faktor: {event_factor}")
            else:
                await ctx.respond(f"🔴 Event ist nicht aktiv.\n Faktor: {event_factor}")

        if action == "On":
            EVENTS_SERVER[server_id] = (True, int(event_factor))
            await ctx.respond("🟢 Event wurde aktiviert.")
            return

        if action == "Off":
            EVENTS_SERVER[server_id] = (False, int(event_factor))
            await ctx.respond("🔴 Event wurde deaktiviert.")
            return

    @economy.command(name="set", description="Set the Event Faktor as Multiplier")
    @checks.is_admin()
    @option("amount", description="Multiply the Loan")
    async def set(self, ctx, amount: int):
        """Set the Event Faktor as Multiplier."""
        server_id = ctx.guild.id

        EVENTS_SERVER[server_id] = (True, int(amount))
        await ctx.respond(f"🟢 Event has been set to x {amount}.")
        return
