# Discord
import discord

# Demolizzen
from demolizzen.services import prices


async def search_items(ctx: discord.AutocompleteContext) -> list[str]:
    """Suggest item names for what was typed so far: names that start with it
    first, then names that contain it."""
    try:
        return await prices.search_item_names(ctx.value or "")
    except Exception as e:  # pylint: disable=broad-exception-caught
        ctx.bot.logger.error(f"Error fetching items for autocomplete: {e}")
        return []
