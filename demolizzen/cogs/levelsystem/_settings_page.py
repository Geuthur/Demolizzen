"""The level system's settings page in the server panel."""

# Discord
import discord

# Demolizzen
from demolizzen import config
from demolizzen.core import settings_pages
from demolizzen.services import guilds, levels
from demolizzen.services.levels import Announcement


def build_level_settings_embed(announcement: Announcement) -> discord.Embed:
    """Show whether and where level-ups are announced."""
    embed = discord.Embed(
        title="📈 Levelsystem – Settings",
        description="Members earn experience by chatting. A card is posted when they reach a new level.",
        color=config.DISCORD_EMBED_COLOR_INFO,
    )
    embed.add_field(
        name="Level up posts", value="✅" if announcement.enabled else "❌", inline=True
    )
    embed.add_field(
        name="Channel",
        value=(
            f"<#{announcement.channel_id}>"
            if announcement.channel_id
            else "System channel"
        ),
        inline=True,
    )
    return embed


class LevelSettingsView(discord.ui.View):
    """Controls for the level-up announcements."""

    def __init__(self, guild_id: int, author_id: int, back, announcement: Announcement):
        super().__init__(timeout=180, disable_on_timeout=True)
        self.guild_id = guild_id
        self.author_id = author_id
        self.back = back
        self.announcement = announcement
        self._build()

    def _build(self) -> None:
        self.clear_items()
        select = discord.ui.Select(
            select_type=discord.ComponentType.channel_select,
            placeholder="Level up channel",
            channel_types=[discord.ChannelType.text],
            row=0,
        )

        async def on_select(interaction: discord.Interaction):
            await self.set_channel(interaction, select.values[0].id)

        async def use_system_channel(interaction: discord.Interaction):
            await self.set_channel(interaction, None)

        select.callback = on_select
        self.add_item(select)

        state = "On" if self.announcement.enabled else "Off"
        buttons = [
            (f"Level up posts: {state}", self.toggle),
            ("Use system channel", use_system_channel),
            ("Back", self.go_back),
        ]
        for label, callback in buttons:
            button = discord.ui.Button(
                label=label, style=discord.ButtonStyle.secondary, row=1
            )
            button.callback = callback
            self.add_item(button)

    def embed(self) -> discord.Embed:
        return build_level_settings_embed(self.announcement)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await settings_pages.check_admin(interaction, self.author_id)

    async def _redraw(self, interaction: discord.Interaction) -> None:
        self.announcement = await levels.get_announcement(self.guild_id)
        self._build()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def toggle(self, interaction: discord.Interaction) -> None:
        """Switch the level-up posts on or off."""
        await levels.set_announcements(self.guild_id, not self.announcement.enabled)
        await self._redraw(interaction)

    async def set_channel(
        self, interaction: discord.Interaction, channel_id: int | None
    ) -> None:
        """Choose the channel for level-up posts; None means the system channel."""
        await guilds.set_main_channel(self.guild_id, channel_id)
        await self._redraw(interaction)

    async def go_back(self, interaction: discord.Interaction) -> None:
        """Return to the panel."""
        self.stop()
        await self.back(interaction)


async def level_settings_page(interaction: discord.Interaction, back) -> None:
    """Settings page of the level system, registered with the panel."""
    await guilds.ensure_guild(interaction.guild.id, interaction.guild.name)
    view = LevelSettingsView(
        interaction.guild.id,
        interaction.user.id,
        back,
        await levels.get_announcement(interaction.guild.id),
    )
    await interaction.response.edit_message(content=None, embed=view.embed(), view=view)
