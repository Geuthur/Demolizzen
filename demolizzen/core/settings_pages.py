"""Settings pages that modules contribute to the server panel.

A module registers a page under its registry key. The panel then offers a
"Settings" button for that module without knowing anything about it.

A page is ``async def page(interaction, back)``. It replaces the panel message
with its own embed and controls; ``back`` is ``async def back(interaction)`` and
shows the panel again.
"""

# Demolizzen
from demolizzen.core import registry

NOT_ALLOWED = "You are not allowed to use this panel."

_pages: dict = {}


def register(key: str, page) -> None:
    """Offer ``page`` as the settings page of the module ``key``."""
    registry.get(key)
    _pages[key] = page


def unregister(key: str) -> None:
    """Withdraw the settings page of the module ``key``."""
    _pages.pop(key, None)


def get(key: str | None):
    """Return the settings page of the module, or None."""
    return _pages.get(key)


async def check_admin(interaction, author_id: int) -> bool:
    """Whether the interaction comes from the admin who opened the panel.

    Tells the user when it does not. Panel and settings pages share this rule.
    """
    user = interaction.user
    guild = interaction.guild
    is_admin = guild is not None and (
        user.id == guild.owner_id or user.guild_permissions.manage_guild
    )
    if user.id == author_id and is_admin:
        return True
    await interaction.response.send_message(NOT_ALLOWED, ephemeral=True)
    return False
