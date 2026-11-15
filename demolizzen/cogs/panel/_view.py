"""The message and controls of the server panel."""

# Discord
import discord

# Demolizzen
from demolizzen import config
from demolizzen.core import registry
from demolizzen.services import cog_settings, guilds
from demolizzen.services.errors import DependencyConflict

ON = "🟢"
OFF = "🔴"


def _mark(enabled: bool) -> str:
    return ON if enabled else OFF


def dependency_notice(key: str, enabled: bool, affected: list[str]) -> str:
    """The question shown before cogs are switched together."""
    titles = ", ".join(registry.get(other).title for other in affected)
    title = registry.get(key).title
    if enabled:
        return f"Enabling {title} will also enable: {titles}."
    return f"Disabling {title} will also disable: {titles}."


def build_embed(
    guild_name: str,
    states: dict[str, bool],
    selected: str | None = None,
    notice: str | None = None,
) -> discord.Embed:
    """Build the panel overview: one field per cog, plus details of the selected one."""
    embed = discord.Embed(
        title=f"⚙️ Demolizzen Panel – {guild_name}",
        color=config.DISCORD_EMBED_COLOR_INFO,
    )
    if notice:
        embed.description = notice
    elif selected is not None and selected in states:
        info = registry.get(selected)
        status = "Enabled" if states[selected] else "Disabled"
        embed.description = (
            f"**{info.title}**\n{info.description}\n"
            f"Status: {_mark(states[selected])} {status}"
        )
    else:
        embed.description = "Select a module to enable or disable it on this server."

    for key, enabled in states.items():
        info = registry.get(key)
        embed.add_field(
            name=f"{_mark(enabled)} {info.title}", value=info.description, inline=True
        )
    return embed


class PanelView(discord.ui.View):
    """Controls to switch cogs for one guild. Only the invoking admin may use them."""

    def __init__(
        self, guild_id: int, guild_name: str, author_id: int, states: dict[str, bool]
    ):
        super().__init__(timeout=180, disable_on_timeout=True)
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.author_id = author_id
        self.states = dict(states)
        self.selected: str | None = None
        # Set while a dependency question is open: (key, enabled, affected cogs).
        self.pending: tuple[str, bool, list[str]] | None = None

        self.select = discord.ui.Select(placeholder="Select a module", row=0)
        self.select.callback = self._on_select
        self.enable_button = discord.ui.Button(
            label="Enable", style=discord.ButtonStyle.success, row=1
        )
        self.enable_button.callback = self._on_enable
        self.disable_button = discord.ui.Button(
            label="Disable", style=discord.ButtonStyle.danger, row=1
        )
        self.disable_button.callback = self._on_disable
        self.confirm_button = discord.ui.Button(
            label="Confirm", style=discord.ButtonStyle.danger, row=0
        )
        self.confirm_button.callback = self.confirm
        self.cancel_button = discord.ui.Button(
            label="Cancel", style=discord.ButtonStyle.secondary, row=0
        )
        self.cancel_button.callback = self.cancel
        self._build()

    def _build(self) -> None:
        """Bring the controls in line with the current state."""
        self.clear_items()
        if self.pending is not None:
            self.add_item(self.confirm_button)
            self.add_item(self.cancel_button)
            return

        self.select.options = [
            discord.SelectOption(
                label=registry.get(key).title,
                value=key,
                description=registry.get(key).description,
                emoji=_mark(enabled),
                default=key == self.selected,
            )
            for key, enabled in self.states.items()
        ]
        chosen = self.selected in self.states
        self.enable_button.disabled = not chosen or self.states[self.selected]
        self.disable_button.disabled = not chosen or not self.states[self.selected]
        self.add_item(self.select)
        self.add_item(self.enable_button)
        self.add_item(self.disable_button)

    def embed(self) -> discord.Embed:
        notice = dependency_notice(*self.pending) if self.pending else None
        return build_embed(self.guild_name, self.states, self.selected, notice)

    async def _redraw(self, interaction: discord.Interaction) -> None:
        self.states = await cog_settings.get_states(self.guild_id)
        self._build()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        user = interaction.user
        guild = interaction.guild
        is_author = user.id == self.author_id
        is_admin = guild is not None and (
            user.id == guild.owner_id or user.guild_permissions.manage_guild
        )
        if is_author and is_admin:
            return True
        await interaction.response.send_message(
            "You are not allowed to use this panel.", ephemeral=True
        )
        return False

    async def choose(self, interaction: discord.Interaction, key: str) -> None:
        """Select the cog the buttons act on."""
        self.selected = key
        await self._redraw(interaction)

    async def toggle(self, interaction: discord.Interaction, enabled: bool) -> None:
        """Switch the selected cog, or ask first when other cogs are affected."""
        if self.selected is not None:
            await self._apply(self.selected, enabled, cascade=False)
        await self._redraw(interaction)

    async def confirm(self, interaction: discord.Interaction) -> None:
        """Switch the cog together with the cogs named in the open question."""
        if self.pending is not None:
            key, enabled, _ = self.pending
            self.pending = None
            await self._apply(key, enabled, cascade=True)
        await self._redraw(interaction)

    async def cancel(self, interaction: discord.Interaction) -> None:
        """Drop the open question without switching anything."""
        self.pending = None
        await self._redraw(interaction)

    async def _apply(self, key: str, enabled: bool, *, cascade: bool) -> None:
        await guilds.ensure_guild(self.guild_id, self.guild_name)
        try:
            await cog_settings.set_enabled(self.guild_id, key, enabled, cascade=cascade)
        except DependencyConflict as conflict:
            self.pending = (conflict.key, conflict.enabled, conflict.affected)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        await self.choose(interaction, self.select.values[0])

    async def _on_enable(self, interaction: discord.Interaction) -> None:
        await self.toggle(interaction, True)

    async def _on_disable(self, interaction: discord.Interaction) -> None:
        await self.toggle(interaction, False)
