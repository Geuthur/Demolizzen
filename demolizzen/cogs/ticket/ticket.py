# Discord
import discord
from discord import Embed
from discord.commands import option
from discord.ext import commands
from discord.ui import Button, View

# Demolizzen
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen
from demolizzen.models.guild import GuildSettings, GuildTicket

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
        self,
        thread: discord.Thread,
        opener: discord.User,
        group: discord.Role,
        ticket_number,
    ):
        super().__init__(timeout=None)
        self.thread = thread
        self.opener = opener
        self.group = group
        self.claimed_by = None
        self.closed_by = None
        self.ticket_number = ticket_number
        self.guild_id = thread.guild.id
        self.generate_thread_name()

        # Dynamische custom_ids
        claim_id = f"claim:{self.guild_id}:{self.ticket_number}"
        close_id = f"close:{self.guild_id}:{self.ticket_number}"
        reopen_id = f"reopen:{self.guild_id}:{self.ticket_number}"
        delete_id = f"delete:{self.guild_id}:{self.ticket_number}"

        self.claim_button = Button(
            label="Claim",
            style=discord.ButtonStyle.primary,
            emoji="🛠️",
            custom_id=claim_id,
        )
        self.close_button = Button(
            label="Close",
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            custom_id=close_id,
        )
        self.reopen_button = Button(
            label="Reopen",
            style=discord.ButtonStyle.success,
            emoji="🔓",
            custom_id=reopen_id,
        )
        self.delete_button = Button(
            label="Delete",
            style=discord.ButtonStyle.danger,
            emoji="🗑️",
            custom_id=delete_id,
        )

        self.claim_button.callback = self.claim_callback
        self.close_button.callback = self.close_callback
        self.reopen_button.callback = self.reopen_callback
        self.delete_button.callback = self.delete_callback

        self.add_item(self.claim_button)
        self.add_item(self.close_button)
        self.add_item(self.reopen_button)
        self.add_item(self.delete_button)

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

    async def claim_callback(self, interaction: discord.Interaction):
        if interaction.user.id == self.opener.id:
            await interaction.response.send_message(
                "You cannot claim your own ticket!", ephemeral=True
            )
            return
        self.claimed_by = interaction.user
        self.status = "claimed"
        await self.update_thread_name()
        self.claim_button.disabled = True
        await self.update_status_message(interaction)
        await interaction.followup.send(
            f"Ticket claimed by {interaction.user.mention}."
        )

    async def close_callback(self, interaction: discord.Interaction):
        self.closed_by = interaction.user
        self.status = "closed"
        await self.update_thread_name()
        self.close_button.disabled = True
        await self.update_status_message(interaction)
        await interaction.followup.send(
            f"{interaction.user.mention} Ticket closed. You can reopen it if needed."
        )
        ticket = await GuildTicket.objects.aget(
            guild_id=self.group.guild.id, ticket_number=self.ticket_number
        )
        ticket.closed_at = discord.utils.utcnow()
        ticket.is_closed = True
        await ticket.asave()

    async def reopen_callback(self, interaction: discord.Interaction):
        self.closed_by = None
        self.claimed_by = None
        self.status = "open"
        await self.update_thread_name()
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = False
        await self.update_status_message(interaction)
        await interaction.followup.send(f"{interaction.user.mention} Ticket reopened.")
        ticket = await GuildTicket.objects.aget(
            guild_id=self.group.guild.id, ticket_number=self.ticket_number
        )
        ticket.closed_at = None
        ticket.is_closed = False
        await interaction.message.edit(view=self)
        await ticket.asave()

    async def delete_callback(self, interaction: discord.Interaction):
        self.delete_button.disabled = True
        await self.update_status_message(interaction)
        try:
            await self.thread.delete()
            ticket = await GuildTicket.objects.aget(
                guild_id=self.group.guild.id, ticket_number=self.ticket_number
            )
            await ticket.adelete()
        except discord.errors.HTTPException as e:
            if e.code == 10003:  # Unknown Channel
                pass
            else:
                self.opener.bot.logger.error(f"Failed to delete thread: {e}")


class TicketSystem(commands.Cog):
    """
    Help Ticket Cog Things
    """

    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.title = "Help System"
        self.alias = "ticket"
        self.persisted_views = self.bot.loop.create_task(self.load_persistent_tickets())

    def cog_unload(self):
        self.persisted_views.cancel()

    async def load_persistent_tickets(self):
        await self.bot.wait_until_ready()
        self.bot.logger.debug("Loading persistent tickets...")
        tickets = [ticket async for ticket in GuildTicket.objects.all()]
        self.bot.logger.info(f"Loaded {len(tickets)} persistent tickets.")
        for ticket in tickets:
            guild = discord.utils.get(self.bot.guilds, id=ticket.guild_id)
            opener = discord.utils.get(guild.members, id=ticket.user_id)
            thread = discord.utils.get(opener.guild.threads, id=ticket.thread_id)
            # Ensure not adding views for deleted threads
            if not thread:
                self.bot.logger.debug(
                    f"Thread {ticket.thread_id} not found, deleting ticket {ticket.ticket_number}"
                )
                await ticket.adelete()
                return
            group = discord.utils.get(thread.guild.roles, id=ticket.group_id)
            if group:
                view = TicketControlView(thread, opener, group, ticket.ticket_number)
                self.bot.logger.debug(
                    f"Adding view for ticket {ticket.ticket_number} in thread {ticket.thread_id}, user {ticket.user_id}, group {ticket.group_id}"
                )
                self.bot.add_view(view)

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
                guild_settings.ticket_count += 1
                await guild_settings.asave()
            except discord.Forbidden:
                return await ctx.respond(
                    content="I do not have permission to create threads in the help channel. Please inform the admins.",
                )
            msg = f"Type: 📩 **OPEN TICKET** - Created by: {ctx.user.mention} - need help from {group.mention}"
            ticket_view = TicketControlView(th, ctx.user, group, ticket_number)
            await th.send(
                msg,
                embed=THREAD_EMBED,
                view=ticket_view,
            )
            # Create GuildTicket entry
            await GuildTicket.objects.acreate(
                guild_id=ctx.guild.id,
                ticket_number=ticket_number,
                thread_id=th.id,
                user_id=ctx.user.id,
                group_id=group.id,
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
