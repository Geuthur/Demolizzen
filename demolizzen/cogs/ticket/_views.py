"""What a ticket looks like in Discord: status message, buttons and forms."""

# Discord
import discord

# Demolizzen
from demolizzen import config
from demolizzen.models import GuildTicket
from demolizzen.services.tickets import MAX_SUBJECT_LENGTH, Action

CLAIM_ID = "ticket:claim"
CLOSE_ID = "ticket:close"
REOPEN_ID = "ticket:reopen"
DELETE_ID = "ticket:delete"
OPEN_ID = "ticket:open"

MAX_DESCRIPTION_LENGTH = 1000
DELETE_QUESTION = "Delete this ticket? This cannot be undone."


def build_status_embed(ticket: GuildTicket) -> discord.Embed:
    """The binding display of a ticket's state."""
    title = f"🎫 Ticket #{ticket.ticket_number:04d}"
    if ticket.subject:
        title += f" – {ticket.subject}"

    if ticket.is_archived:
        status, color = "📦 Archived", config.DISCORD_EMBED_COLOR_WARNING
    elif ticket.is_closed:
        status, color = "🔒 Closed", config.DISCORD_EMBED_COLOR_DANGER
    else:
        status, color = "🟢 Open", config.DISCORD_EMBED_COLOR_SUCCESS

    lines = [f"Status: {status}"]
    if ticket.claimed_by:
        lines.append(f"Claimed by: <@{ticket.claimed_by}>")
    if ticket.is_closed and ticket.closed_by:
        lines.append(f"Closed by: <@{ticket.closed_by}>")
    lines.append(f"Created by: <@{ticket.user_id}>")
    return discord.Embed(title=title, description="\n".join(lines), color=color)


class TicketControlView(discord.ui.View):
    """The four ticket buttons.

    The buttons carry fixed ids, so one instance registered with the bot
    (``handler`` given) receives the clicks of every ticket message. Instances
    built for a message (``ticket`` given) only describe which buttons are
    active and are not stored.
    """

    def __init__(self, ticket: GuildTicket | None = None, handler=None):
        super().__init__(timeout=None, store=handler is not None)
        self.handler = handler
        is_open = ticket is None or not ticket.is_closed
        is_closed = ticket is None or ticket.is_closed
        unclaimed = ticket is None or ticket.claimed_by is None
        buttons = [
            (
                "Claim",
                "🛠️",
                discord.ButtonStyle.primary,
                CLAIM_ID,
                Action.CLAIM,
                is_open and unclaimed,
            ),
            (
                "Close",
                "🔒",
                discord.ButtonStyle.danger,
                CLOSE_ID,
                Action.CLOSE,
                is_open,
            ),
            (
                "Reopen",
                "🔓",
                discord.ButtonStyle.success,
                REOPEN_ID,
                Action.REOPEN,
                is_closed,
            ),
            (
                "Delete",
                "🗑️",
                discord.ButtonStyle.secondary,
                DELETE_ID,
                Action.DELETE,
                True,
            ),
        ]
        for label, emoji, style, custom_id, action, active in buttons:
            button = discord.ui.Button(
                label=label,
                emoji=emoji,
                style=style,
                custom_id=custom_id,
                disabled=not active,
            )
            button.callback = self._callback_for(action)
            self.add_item(button)

    def _callback_for(self, action: Action):
        async def callback(interaction: discord.Interaction):
            if self.handler is not None:
                await self.handler(interaction, action)

        return callback


class OpenTicketView(discord.ui.View):
    """The "Open ticket" button of the ticket panel message."""

    def __init__(self, handler=None):
        super().__init__(timeout=None, store=handler is not None)
        self.handler = handler
        button = discord.ui.Button(
            label="Open ticket",
            emoji="🎫",
            style=discord.ButtonStyle.primary,
            custom_id=OPEN_ID,
        )
        button.callback = self._callback
        self.add_item(button)

    async def _callback(self, interaction: discord.Interaction):
        if self.handler is not None:
            await self.handler(interaction)


class OpenTicketModal(discord.ui.Modal):
    """Asks what the ticket is about."""

    def __init__(self, on_submit):
        super().__init__(title="Open a ticket")
        self.on_submit = on_submit
        self.add_item(
            discord.ui.InputText(
                label="Subject",
                placeholder="What is it about?",
                max_length=MAX_SUBJECT_LENGTH,
                required=True,
            )
        )
        self.add_item(
            discord.ui.InputText(
                label="Description",
                style=discord.InputTextStyle.long,
                placeholder="Describe your request (optional)",
                max_length=MAX_DESCRIPTION_LENGTH,
                required=False,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        subject = (self.children[0].value or "").strip()
        description = (self.children[1].value or "").strip()
        await self.on_submit(interaction, subject, description)


class ConfirmDeleteView(discord.ui.View):
    """Asks before a ticket is deleted for good."""

    def __init__(self, on_confirm):
        super().__init__(timeout=60, disable_on_timeout=True)
        self.on_confirm = on_confirm
        delete = discord.ui.Button(label="Delete", style=discord.ButtonStyle.danger)
        delete.callback = self._confirm
        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel.callback = self._cancel
        self.add_item(delete)
        self.add_item(cancel)

    async def _confirm(self, interaction: discord.Interaction):
        self.stop()
        await self.on_confirm(interaction)

    async def _cancel(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(content="Cancelled.", view=None)
