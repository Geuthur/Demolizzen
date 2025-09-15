# Standard Library
import logging

# Discord
import discord
from discord import Embed, SlashCommandGroup
from discord.ext import commands

# Demolizzen
from demolizzen.cogs.ticket._ticketview import TicketControlView
from demolizzen.core.bot import Demolizzen
from demolizzen.models.guild import (
    GuildTicket,
    GuildTicketSettings,
)
from demolizzen.utils.functions import get_command_mention

THREAD_EMBED = Embed(
    title="Private Channel Guide",
    description=(
        "This Channel is private between you and the staff team.\n"
        "Use the buttons below to manage your ticket.\n"
        "Please be patient while waiting for a response from the staff."
    ),
)

logger = logging.getLogger(__name__)


class TicketSystem(commands.Cog):
    """Help Ticket Cog Things"""

    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.title = "Ticket System"
        self.alias = "ticket"

    ticket = SlashCommandGroup(
        name="ticket",
        description="Ticket System",
        contexts=[discord.InteractionContextType.guild],
    )

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        guild_settings, created = await GuildTicketSettings.objects.aget_or_create(
            guild_id=ctx.guild.id,
        )
        ctx.guild_settings = guild_settings
        logger.debug(f"GuildSettings loaded for {ctx.guild}.")
        if created:
            logger.info(f"Created new GuildSettings for {ctx.guild}.")

    @ticket.command(name="open", help="Open a help ticket")
    @commands.guild_only()
    async def open_ticket(
        self,
        ctx: discord.ApplicationContext,
    ):
        """Ticket system to contact Server staff."""
        if not ctx.guild_settings.category_id:
            return await ctx.respond(
                content=f"No help category is set for this server. Please inform the admins to set a help category using {get_command_mention(bot=self.bot, cog='TicketSystemConfig', slash_command='ticket_config', slash_command_group='set')} command.",
            )

        ticket_number = ctx.guild_settings.ticket_count
        category_channel = discord.utils.get(
            ctx.guild.categories, id=ctx.guild_settings.category_id
        )

        if not category_channel:
            return await ctx.respond(
                content=f"The configured help category does not exist anymore. Please inform the admins to set a new help category using {get_command_mention(bot=self.bot, cog='TicketSystemConfig', slash_command='ticket_config', slash_command_group='set')} command.",
            )

        # Channel-Name generieren
        channel_name_ticket = f"ticket{ticket_number}-unclaimed-{ctx.user.name}"
        # Channel erstellen mit Sichtbarkeit nur für User und ggf. Staff
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        }

        # Set Permnissions for Channel
        # Staff Members
        staff_role_ids = getattr(ctx.guild_settings, "roles", None)
        if staff_role_ids:
            for staff_role_id in staff_role_ids:
                role = ctx.guild.get_role(staff_role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True, read_message_history=True
                    )
            # Staff-Rollen erwähnen
            staff_mentions = ""
            staff_roles = [
                ctx.guild.get_role(rid)
                for rid in staff_role_ids
                if ctx.guild.get_role(rid)
            ]
            staff_mentions = " ".join(role.mention for role in staff_roles)
        else:
            return await ctx.respond(
                content=f"No staff roles are set for this server. Please inform the admins to set at least one staff role using {get_command_mention(bot=self.bot, cog='TicketSystemConfig', slash_command='ticket_config', slash_command_group='staff')} command.",
            )
        # Bot
        overwrites[ctx.guild.me] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        )
        # Ticket-Ersteller
        overwrites[ctx.user] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            mention_everyone=False,  # block @everyone, @here
        )

        # Create Channel
        try:
            ticket_channel = await ctx.guild.create_text_channel(
                name=channel_name_ticket,
                topic=f"Type: 📩 **OPEN TICKET** - Created by: {ctx.user.mention}",
                category=category_channel,
                overwrites=overwrites,
            )
            ctx.guild_settings.ticket_count += 1
            await ctx.guild_settings.asave()
        except discord.Forbidden:
            return await ctx.respond(
                content="I do not have permission to create ticket channels. Please inform the admins.",
            )

        ticket_view = TicketControlView(ticket_channel, ctx.user, ticket_number)
        await ticket_channel.send(
            content=staff_mentions if staff_mentions else None,
            embed=THREAD_EMBED,
            view=ticket_view,
        )
        # Create GuildTicket entry
        await GuildTicket.objects.acreate(
            guild_id=ctx.guild.id,
            ticket_number=ticket_number,
            channel_id=ticket_channel.id,
            user_id=ctx.user.id,
        )
        return await ctx.respond(
            content=f"Check the ticket channel created! {ticket_channel.mention}!",
            ephemeral=True,
        )
