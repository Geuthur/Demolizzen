"""The ticket system's settings page in the server panel."""

# Discord
import discord

# Demolizzen
from demolizzen import config
from demolizzen.cogs.ticket._views import OpenTicketView
from demolizzen.core import settings_pages
from demolizzen.models import GuildTicketSettings
from demolizzen.services import guilds, tickets
from demolizzen.services.errors import TicketError

ARCHIVE_DAY_CHOICES = (1, 3, 7, 14, 30)
OPEN_TICKET_CHOICES = (1, 2, 3, 5)


def _channel(channel_id: int | None, required: bool = False) -> str:
    if channel_id:
        return f"<#{channel_id}>"
    return "⚠️ not set" if required else "not set"


def _flag(value: bool) -> str:
    return "✅" if value else "❌"


def build_settings_embed(
    settings: GuildTicketSettings, notice: str | None = None
) -> discord.Embed:
    """Show every ticket setting; missing required ones are marked."""
    roles = tickets.staff_role_ids(settings)
    embed = discord.Embed(
        title="🎫 Ticket System – Settings",
        description=notice or "Choose a section to change its settings.",
        color=config.DISCORD_EMBED_COLOR_INFO,
    )
    values = [
        ("Ticket category", _channel(settings.category_id, required=True)),
        ("Archive category", _channel(settings.archive_category_id)),
        ("Log channel", _channel(settings.log_channel_id)),
        (
            "Staff roles",
            " ".join(f"<@&{role}>" for role in roles) if roles else "⚠️ not set",
        ),
        ("Members may close", _flag(settings.allow_user_close)),
        ("Members may reopen", _flag(settings.allow_user_reopen)),
        ("Archive after", f"{settings.auto_archive_days} days"),
        ("Open tickets per member", str(settings.max_open_tickets)),
    ]
    for name, value in values:
        embed.add_field(name=name, value=value, inline=True)
    return embed


class TicketSettingsView(discord.ui.View):
    """Controls for the ticket settings, split into sections.

    Discord allows five rows of controls per message, so the settings are spread
    over an overview and three sections.
    """

    def __init__(
        self,
        guild_id: int,
        author_id: int,
        back,
        settings: GuildTicketSettings,
        section: str = "overview",
    ):
        super().__init__(timeout=180, disable_on_timeout=True)
        self.guild_id = guild_id
        self.author_id = author_id
        self.back = back
        self.settings = settings
        self.section = section
        self.notice: str | None = None
        self._build()

    # ------------------------------------------------------------------ building

    def _button(self, label: str, callback, row: int, style=None) -> None:
        button = discord.ui.Button(
            label=label, style=style or discord.ButtonStyle.secondary, row=row
        )
        button.callback = callback
        self.add_item(button)

    def _picker(self, select: discord.ui.Select, convert, setting: str) -> None:
        async def callback(interaction: discord.Interaction):
            await self.set_value(interaction, setting, convert(select.values))

        select.callback = callback
        self.add_item(select)

    def _section_button(self, label: str, section: str, row: int) -> None:
        async def callback(interaction: discord.Interaction):
            await self.show_section(interaction, section)

        self._button(label, callback, row)

    def _build(self) -> None:
        self.clear_items()
        builder = {
            "channels": self._build_channels,
            "staff": self._build_staff,
            "limits": self._build_limits,
        }.get(self.section, self._build_overview)
        builder()

    def _build_overview(self) -> None:
        self._section_button("Channels", "channels", 0)
        self._section_button("Staff & permissions", "staff", 0)
        self._section_button("Limits", "limits", 0)
        self._button(
            "Post ticket button", self.post_button, 1, discord.ButtonStyle.primary
        )
        self._button("Back", self.go_back, 1)

    def _build_channels(self) -> None:
        def first_id(values):
            return values[0].id

        pickers = [
            ("Ticket category", discord.ChannelType.category, "category_id"),
            ("Archive category", discord.ChannelType.category, "archive_category_id"),
            ("Log channel", discord.ChannelType.text, "log_channel_id"),
        ]
        for row, (placeholder, channel_type, setting) in enumerate(pickers):
            self._picker(
                discord.ui.Select(
                    select_type=discord.ComponentType.channel_select,
                    placeholder=placeholder,
                    channel_types=[channel_type],
                    row=row,
                ),
                first_id,
                setting,
            )

        async def clear_archive(interaction: discord.Interaction):
            await self.set_value(interaction, "archive_category_id", None)

        async def clear_log(interaction: discord.Interaction):
            await self.set_value(interaction, "log_channel_id", None)

        self._button("Clear archive category", clear_archive, 3)
        self._button("Clear log channel", clear_log, 3)
        self._section_button("Back", "overview", 3)

    def _build_staff(self) -> None:
        self._picker(
            discord.ui.Select(
                select_type=discord.ComponentType.role_select,
                placeholder="Staff roles",
                min_values=1,
                max_values=25,
                row=0,
            ),
            lambda values: [role.id for role in values],
            "roles",
        )
        for label, setting in (
            ("Members may close", "allow_user_close"),
            ("Members may reopen", "allow_user_reopen"),
        ):
            state = "On" if getattr(self.settings, setting) else "Off"
            self._button(f"{label}: {state}", self._toggle_callback(setting), 1)
        self._section_button("Back", "overview", 1)

    def _toggle_callback(self, setting: str):
        async def callback(interaction: discord.Interaction):
            await self.toggle(interaction, setting)

        return callback

    def _build_limits(self) -> None:
        def first_number(values):
            return int(values[0])

        choices = [
            ("Archive after … days", "auto_archive_days", ARCHIVE_DAY_CHOICES),
            ("Open tickets per member", "max_open_tickets", OPEN_TICKET_CHOICES),
        ]
        for row, (placeholder, setting, numbers) in enumerate(choices):
            self._picker(
                discord.ui.Select(
                    placeholder=placeholder,
                    options=[
                        discord.SelectOption(
                            label=str(number),
                            value=str(number),
                            default=number == getattr(self.settings, setting),
                        )
                        for number in numbers
                    ],
                    row=row,
                ),
                first_number,
                setting,
            )
        self._section_button("Back", "overview", 2)

    # ------------------------------------------------------------------ behaviour

    def embed(self) -> discord.Embed:
        return build_settings_embed(self.settings, self.notice)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await settings_pages.check_admin(interaction, self.author_id)

    async def _redraw(self, interaction: discord.Interaction) -> None:
        self._build()
        await interaction.response.edit_message(embed=self.embed(), view=self)
        self.notice = None

    async def show_section(
        self, interaction: discord.Interaction, section: str
    ) -> None:
        """Switch between the overview and the sections."""
        self.section = section
        await self._redraw(interaction)

    async def set_value(self, interaction: discord.Interaction, setting: str, value):
        """Store one setting and show the result."""
        try:
            self.settings = await tickets.update_settings(
                self.guild_id, **{setting: value}
            )
        except TicketError as exc:
            self.notice = f"⚠️ {exc.message}"
        await self._redraw(interaction)

    async def toggle(self, interaction: discord.Interaction, setting: str) -> None:
        """Flip an on/off setting."""
        await self.set_value(interaction, setting, not getattr(self.settings, setting))

    async def post_button(self, interaction: discord.Interaction) -> None:
        """Put the "Open ticket" message into the channel the panel was used in."""
        embed = discord.Embed(
            title="🎫 Need help?",
            description="Open a ticket and the staff team will take care of it.",
            color=config.DISCORD_EMBED_COLOR_INFO,
        )
        try:
            await interaction.channel.send(embed=embed, view=OpenTicketView())
        except discord.HTTPException:
            self.notice = "⚠️ I cannot send messages in this channel."
        else:
            self.notice = "✅ Ticket button posted in this channel."
        self._build()
        await interaction.response.edit_message(
            content=self.notice, embed=self.embed(), view=self
        )
        self.notice = None

    async def go_back(self, interaction: discord.Interaction) -> None:
        """Return to the panel."""
        self.stop()
        await self.back(interaction)


async def ticket_settings_page(interaction: discord.Interaction, back) -> None:
    """Settings page of the ticket system, registered with the panel."""
    await guilds.ensure_guild(interaction.guild.id, interaction.guild.name)
    settings = await tickets.get_settings(interaction.guild.id)
    view = TicketSettingsView(interaction.guild.id, interaction.user.id, back, settings)
    await interaction.response.edit_message(content=None, embed=view.embed(), view=view)
