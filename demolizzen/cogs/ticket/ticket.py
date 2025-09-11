# Standard Library
import logging

# Discord
import discord
from discord import Embed
from discord.commands import option
from discord.ext import commands
from discord.ui import Button, View

# Demolizzen
from demolizzen.core import checks
from demolizzen.models.guild import GuildSettings

logger = logging.getLogger(__name__)

THREAD_EMBED = Embed(
    title="Private Thread Guide",
    description=(
        "This thread is private between you and the staff team you mentioned.\n"
        "Use the buttons below to manage your ticket.\n"
        "To add a person to this thread simply `@mention` them will also work for `@groups`.\n"
        "Please be patient while waiting for a response from the staff."
    ),
)


class TicketControlView(View):
    def __init__(
        self, thread, opener: discord.User, group: discord.Role, ticket_number
    ):
        super().__init__(timeout=None)
        self.thread = thread
        self.opener = opener
        self.group = group
        self.claimed_by = None
        self.closed_by = None
        self.ticket_number = ticket_number
        self.generate_thread_name()
        self.claim_button = None
        self.close_button = None
        self.reopen_button = None
        self.delete_button = None

    def generate_thread_name(self):
        claimed = self.claimed_by.display_name if self.claimed_by else "unclaimed"
        author = self.opener.display_name
        return f"ticket{self.ticket_number}-{claimed}-{author}"

    async def update_thread_name(self):
        name = self.generate_thread_name()
        try:
            await self.thread.edit(name=name)
        except Exception:
            pass

    async def update_status_message(self, interaction: discord.Interaction = None):
        # Dynamische Status-Nachricht
        msg_parts = ["Type: 📩 **OPEN TICKET**"]
        if self.closed_by:
            msg_parts.append(f"- Closed by: {self.closed_by.mention}")
        if self.claimed_by:
            msg_parts.append(f"- Claimed by: {self.claimed_by.mention}")
        msg_parts.append(
            f"- Created by: {self.opener.mention} - need help from {self.group.mention}"
        )
        content = " ".join(msg_parts)
        # Editiere die erste Nachricht im Thread (angenommen, es ist die erste)
        try:
            first_message = None
            async for m in self.thread.history(limit=1, oldest_first=True):
                first_message = m
                break
            if first_message:
                await first_message.edit(content=content, embed=THREAD_EMBED, view=self)
        except Exception:
            pass
        if interaction:
            await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary, emoji="🛠️")
    async def claim(self, button: Button, interaction: discord.Interaction):
        if interaction.user.id == self.opener.id:
            await interaction.response.send_message(
                "You cannot claim your own ticket!", ephemeral=True
            )
            return
        self.claimed_by = interaction.user
        self.status = "claimed"
        await self.update_thread_name()
        button.disabled = True
        await self.update_status_message(interaction)
        await interaction.followup.send(
            f"Ticket claimed by {interaction.user.mention}."
        )

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close(self, button: Button, interaction: discord.Interaction):
        self.closed_by = interaction.user
        self.status = "closed"
        await self.update_thread_name()
        button.disabled = True
        await self.update_status_message(interaction)
        await interaction.followup.send(
            f"{interaction.user.mention} Ticket closed. You can reopen it if needed."
        )

    @discord.ui.button(label="Reopen", style=discord.ButtonStyle.success, emoji="🔓")
    async def reopen(self, __: Button, interaction: discord.Interaction):
        # Only allow reopening if currently closed
        if not self.closed_by:
            await interaction.response.send_message(
                "Ticket is already open!", ephemeral=True
            )
            return
        self.closed_by = None
        self.claimed_by = None
        self.status = "open"
        await self.update_thread_name()
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = False
        await self.update_status_message(interaction)
        await interaction.followup.send(f"{interaction.user.mention} Ticket reopened.")

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete(self, button: Button, interaction: discord.Interaction):
        button.disabled = True
        await self.update_status_message(interaction)
        await self.thread.delete()
        await interaction.followup.send(f"{interaction.user.mention} Ticket deleted.")


class TicketSystem(commands.Cog):
    """
    Help Ticket Cog Things
    """

    def __init__(self, bot):
        self.bot = bot
        self.title = "Help System"
        self.alias = "ticket"

    @commands.slash_command(name="open_ticket")
    @commands.guild_only()
    @option("group", description="The group you wish to contact", required=True)
    async def open_ticket(
        self,
        ctx: discord.ApplicationContext,
        group: discord.Role,
    ):
        """Ticket system to contact Server staff."""
        try:
            guild_settings = await GuildSettings.objects.aget(
                guild_id=ctx.guild.id,
            )
            channel_name = guild_settings.help_channel
            ticket_number = guild_settings.ticket_count
        except GuildSettings.DoesNotExist:
            guild_settings = await GuildSettings.objects.acreate(
                guild_id=ctx.guild.id, help_channel="help", ticket_count=1
            )
            channel_name = guild_settings.help_channel
            ticket_number = guild_settings.ticket_count

        help_channel = discord.utils.get(ctx.guild.text_channels, name=channel_name)
        if help_channel:
            if group is None:
                return await ctx.respond(
                    content="That group is not found on this server?",
                )
            try:
                th = await help_channel.create_thread(
                    name=f"ticket{ticket_number}-unclaimed-{ctx.user.display_name}",
                    auto_archive_duration=10080,
                    type=discord.ChannelType.private_thread,
                    reason=None,
                )
            except discord.Forbidden:
                return await ctx.respond(
                    content="I do not have permission to create threads in the help channel. Please inform the admins.",
                )
            msg = f"Type: 📩 **OPEN TICKET** - Created by: {ctx.user.mention} - need help from {group.mention}"
            await th.send(
                msg,
                embed=THREAD_EMBED,
                view=TicketControlView(th, ctx.user, group, ticket_number),
            )
            return await ctx.respond(
                content=f"Check the thread created! {th.mention} Ping in the thread for urgent help!",
            )
        return await ctx.respond(
            content=(
                "Help channel not found on this server? Please inform the admins."
            ),
        )

    @commands.slash_command(name="set_help_channel")
    @commands.guild_only()
    @checks.is_admin()
    @option("channel", description="The channel to set as help channel", required=True)
    async def set_help_channel(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel,
    ):
        """Set the help channel for tickets."""
        guild_settings, created = await GuildSettings.objects.aget_or_create(
            guild_id=ctx.guild.id,
            defaults={"help_channel": channel.name, "ticket_count": 1},
        )
        if not created:
            guild_settings.help_channel = channel.name
            await guild_settings.asave()
        await ctx.respond(
            content=f"Help channel set to {channel.mention}.",
        )
