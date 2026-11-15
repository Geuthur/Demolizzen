"""Plain-text record of a ticket, written when the ticket is deleted."""

# Demolizzen
from demolizzen.models import GuildTicket

# A transcript holds at most this many messages, oldest first.
MAX_MESSAGES = 5000


def render_transcript(
    ticket: GuildTicket, messages, deleted_by: str | None = None
) -> str:
    """Render the ticket's messages as text.

    ``messages`` are Discord messages, oldest first. Attachments are listed by
    their link; the files themselves are not kept.
    """
    lines = [f"Ticket #{ticket.ticket_number:04d}"]
    if ticket.subject:
        lines.append(f"Subject: {ticket.subject}")
    lines.append(f"Created by: {ticket.user_id}")
    if ticket.claimed_by:
        lines.append(f"Claimed by: {ticket.claimed_by}")
    if ticket.closed_by:
        lines.append(f"Closed by: {ticket.closed_by}")
    if deleted_by:
        lines.append(f"Deleted by: {deleted_by}")
    lines.append("")

    for message in messages:
        stamp = message.created_at.strftime("%Y-%m-%d %H:%M")
        lines.append(
            f"[{stamp}] {message.author.name}: {message.content or ''}".rstrip()
        )
        for attachment in message.attachments:
            lines.append(f"    [attachment] {attachment.url}")
    return "\n".join(lines) + "\n"
