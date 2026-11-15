# Standard Library
import logging
from datetime import timedelta

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands

# Demolizzen
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog

logger = logging.getLogger(__name__)

# Discord deletes at most 100 messages at once, none older than 14 days.
MAX_CLEAR = 100
MAX_MESSAGE_AGE = timedelta(days=14)

NO_PERMISSION = "❌ I have no permission to do that..."
FAILED = "❌ Something went wrong try later."
# Discord's error code for "a message is too old to bulk delete".
TOO_OLD_CODE = 50034


class Admin(BaseCog):
    """
    Secure the Server with automated Moderation Tools
    """

    key = "admin"

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
        self.title = "Admin"
        self.alias = "admin"

    mod = SlashCommandGroup(
        "moderation",
        "Moderation System",
        contexts=[discord.InteractionContextType.guild],
        default_member_permissions=discord.Permissions(manage_messages=True),
    )

    @mod.command()
    @commands.guild_only()
    @checks.is_mod()
    @option("limit", description="How many", min_value=1, max_value=MAX_CLEAR)
    async def clear(self, ctx: discord.ApplicationContext, limit: int):
        """Clear Message from a Channel."""
        await ctx.defer(ephemeral=True)
        embed = discord.Embed(description=await self._clear(ctx.channel, limit))
        await ctx.respond(embed=embed, ephemeral=True, delete_after=10)

    @staticmethod
    async def _clear(channel, limit: int) -> str:
        """Delete the newest messages of the channel and say what happened."""
        if not 1 <= limit <= MAX_CLEAR:
            return f"❌ Between 1 and {MAX_CLEAR} messages can be deleted at a time."

        try:
            messages = await channel.history(
                limit=limit,
                after=discord.utils.utcnow() - MAX_MESSAGE_AGE,
                oldest_first=False,
            ).flatten()
            if not messages:
                return "❌ No messages from the last 14 days to delete."
            await channel.delete_messages(messages)
        except discord.Forbidden:
            return NO_PERMISSION
        except discord.HTTPException as error:
            if error.code == TOO_OLD_CODE:
                return (
                    "❌ You can only bulk delete messages that are under 14 days old."
                )
            logger.error("Clearing channel %s failed: %r", channel.id, error)
            return FAILED
        return f"✅ Deleted {len(messages)} message(s)."
