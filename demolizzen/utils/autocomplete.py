# Third Party
from asgiref.sync import sync_to_async

# Discord
import discord

# Demolizzen
from demolizzen import models


async def search_items(ctx: discord.AutocompleteContext):
    """Returns a list of items from invTypes that match the entered characters, prioritizing those that start with the search term."""
    search_term = ctx.value.lower()
    if len(search_term) < 2:
        return []

    try:

        @sync_to_async
        def get_results() -> list[str]:
            return list(
                models.InvTypes.objects.filter(
                    published=1, typeName__icontains=search_term
                )
                .order_by("typeName")
                .values_list("typeName", flat=True)[:50]
            )

        results = await get_results()
        if not results:
            return []

        # Sort: first items that start with the search term, then the rest
        startswith = [item for item in results if item.lower().startswith(search_term)]
        others = [item for item in results if not item.lower().startswith(search_term)]
        sorted_items = startswith + others

        return sorted_items[:10]

    except Exception as e:
        ctx.bot.logger.error(f"Error fetching items for autocomplete: {e}")
        return []
