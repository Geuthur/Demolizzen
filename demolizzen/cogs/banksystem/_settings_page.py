"""The bank's settings page in the server panel."""

# Discord
import discord

# Demolizzen
from demolizzen import config
from demolizzen.core import settings_pages
from demolizzen.models import GuildBankSettings
from demolizzen.services import bank, guilds
from demolizzen.services.errors import BankError

INTEREST_CHOICES = bank.INTEREST_CHOICES

_SWITCHES = (("Deposits", "allow_deposits"), ("Withdrawals", "allow_withdrawals"))


def _percent(rate: float) -> str:
    return f"{rate * 100:g}%"


def build_bank_settings_embed(
    settings: GuildBankSettings, notice: str | None = None
) -> discord.Embed:
    """Show the bank settings of a guild."""
    embed = discord.Embed(
        title="🏦 Banksystem – Settings",
        description=notice
        or "Interest is paid once a week on the money members keep in the bank.",
        color=config.DISCORD_EMBED_COLOR_INFO,
    )
    embed.add_field(
        name="Interest per week", value=_percent(settings.interest_rate), inline=True
    )
    for label, setting in _SWITCHES:
        embed.add_field(
            name=label, value="✅" if getattr(settings, setting) else "❌", inline=True
        )
    return embed


class BankSettingsView(discord.ui.View):
    """Controls for the bank settings."""

    def __init__(
        self, guild_id: int, author_id: int, back, settings: GuildBankSettings
    ):
        super().__init__(timeout=180, disable_on_timeout=True)
        self.guild_id = guild_id
        self.author_id = author_id
        self.back = back
        self.settings = settings
        self.notice: str | None = None
        self._build()

    def _build(self) -> None:
        self.clear_items()
        current = round(self.settings.interest_rate * 100, 6)
        select = discord.ui.Select(
            placeholder="Interest per week",
            options=[
                discord.SelectOption(
                    label=f"{percent:g}%",
                    value=str(percent),
                    default=percent == current,
                )
                for percent in INTEREST_CHOICES
            ],
            row=0,
        )

        async def on_select(interaction: discord.Interaction):
            await self.set_interest(interaction, float(select.values[0]))

        select.callback = on_select
        self.add_item(select)

        for label, setting in _SWITCHES:
            state = "On" if getattr(self.settings, setting) else "Off"
            button = discord.ui.Button(
                label=f"{label}: {state}", style=discord.ButtonStyle.secondary, row=1
            )
            button.callback = self._toggle_callback(setting)
            self.add_item(button)

        back = discord.ui.Button(
            label="Back", style=discord.ButtonStyle.secondary, row=1
        )
        back.callback = self.go_back
        self.add_item(back)

    def _toggle_callback(self, setting: str):
        async def callback(interaction: discord.Interaction):
            await self.toggle(interaction, setting)

        return callback

    def embed(self) -> discord.Embed:
        return build_bank_settings_embed(self.settings, self.notice)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await settings_pages.check_admin(interaction, self.author_id)

    async def _save(self, interaction: discord.Interaction, **fields) -> None:
        try:
            self.settings = await bank.update_settings(self.guild_id, **fields)
        except BankError as exc:
            self.notice = f"⚠️ {exc.message}"
        self._build()
        await interaction.response.edit_message(embed=self.embed(), view=self)
        self.notice = None

    async def set_interest(self, interaction: discord.Interaction, percent: float):
        """Store the weekly interest rate given in percent."""
        await self._save(interaction, interest_rate=percent / 100)

    async def toggle(self, interaction: discord.Interaction, setting: str) -> None:
        """Flip whether deposits or withdrawals are allowed."""
        await self._save(interaction, **{setting: not getattr(self.settings, setting)})

    async def go_back(self, interaction: discord.Interaction) -> None:
        """Return to the panel."""
        self.stop()
        await self.back(interaction)


async def bank_settings_page(interaction: discord.Interaction, back) -> None:
    """Settings page of the bank, registered with the panel."""
    await guilds.ensure_guild(interaction.guild.id, interaction.guild.name)
    settings = await bank.get_settings(interaction.guild.id)
    view = BankSettingsView(interaction.guild.id, interaction.user.id, back, settings)
    await interaction.response.edit_message(content=None, embed=view.embed(), view=view)
