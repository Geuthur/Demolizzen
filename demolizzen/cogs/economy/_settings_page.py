"""The economy's settings page in the server panel."""

# Discord
import discord

# Demolizzen
from demolizzen import config
from demolizzen.core import settings_pages
from demolizzen.services import guilds, missions
from demolizzen.services.missions import Event


def build_economy_settings_embed(event: Event) -> discord.Embed:
    """Show whether the payout event runs and with which factor."""
    embed = discord.Embed(
        title="💰 Economy – Settings",
        description=(
            "During an event, work and mission payouts are multiplied by the "
            "payout factor and a lost ship costs nothing."
        ),
        color=config.DISCORD_EMBED_COLOR_INFO,
    )
    embed.add_field(name="Event", value="✅" if event.active else "❌", inline=True)
    embed.add_field(name="Payout factor", value=f"x{event.factor}", inline=True)
    return embed


class EconomySettingsView(discord.ui.View):
    """Controls for the payout event."""

    def __init__(self, guild_id: int, author_id: int, back, event: Event):
        super().__init__(timeout=180, disable_on_timeout=True)
        self.guild_id = guild_id
        self.author_id = author_id
        self.back = back
        self.event = event
        self._build()

    def _build(self) -> None:
        self.clear_items()
        select = discord.ui.Select(
            placeholder="Payout factor",
            options=[
                discord.SelectOption(
                    label=f"x{factor}",
                    value=str(factor),
                    default=factor == self.event.factor,
                )
                for factor in range(
                    missions.MIN_EVENT_FACTOR, missions.MAX_EVENT_FACTOR + 1
                )
            ],
            row=0,
        )

        async def on_select(interaction: discord.Interaction):
            await self.set_factor(interaction, int(select.values[0]))

        select.callback = on_select
        self.add_item(select)

        state = "On" if self.event.active else "Off"
        for label, callback in (
            (f"Event: {state}", self.toggle),
            ("Back", self.go_back),
        ):
            button = discord.ui.Button(
                label=label, style=discord.ButtonStyle.secondary, row=1
            )
            button.callback = callback
            self.add_item(button)

    def embed(self) -> discord.Embed:
        return build_economy_settings_embed(self.event)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await settings_pages.check_admin(interaction, self.author_id)

    async def _redraw(self, interaction: discord.Interaction) -> None:
        self._build()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def toggle(self, interaction: discord.Interaction) -> None:
        """Start or stop the event."""
        self.event = await missions.set_event(
            self.guild_id, active=not self.event.active
        )
        await self._redraw(interaction)

    async def set_factor(self, interaction: discord.Interaction, factor: int) -> None:
        """Choose the payout factor."""
        self.event = await missions.set_event(self.guild_id, factor=factor)
        await self._redraw(interaction)

    async def go_back(self, interaction: discord.Interaction) -> None:
        """Return to the panel."""
        self.stop()
        await self.back(interaction)


async def economy_settings_page(interaction: discord.Interaction, back) -> None:
    """Settings page of the economy, registered with the panel."""
    await guilds.ensure_guild(interaction.guild.id, interaction.guild.name)
    view = EconomySettingsView(
        interaction.guild.id,
        interaction.user.id,
        back,
        await missions.get_event(interaction.guild.id),
    )
    await interaction.response.edit_message(content=None, embed=view.embed(), view=view)
