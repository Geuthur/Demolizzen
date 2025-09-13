# Standard Library
import logging

# Discord
import discord
from discord.ui import Button, View

# Django
from django.utils import timezone

# Demolizzen
from demolizzen.models.guild import GuildTicket, GuildTicketTask

logger = logging.getLogger(__name__)


class TicketControlView(View):
    def __init__(
        self,
        channel: discord.TextChannel,
        ticket_owner: discord.User,
        ticket_number,
    ):
        super().__init__(timeout=None)
        self.channel = channel
        self.ticket_owner = ticket_owner
        self.ticket_number = ticket_number
        self.guild_id = channel.guild.id

        if not self.ticket_owner:
            raise ValueError("Ticket owner cannot be None")
        if not self.guild_id:
            raise ValueError("Guild ID cannot be None")
        if not self.ticket_number:
            raise ValueError("Ticket number cannot be None")

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

    async def get_guild_member(
        self, interaction: discord.Interaction, user_id: int
    ) -> discord.Member | None:
        """Get a member by user ID in the guild of the ticket channel."""
        guild = interaction.channel.guild
        member = guild.get_member(user_id)
        if member:
            return member
        return None

    async def get_closed_by(
        self, interaction: discord.Interaction
    ) -> discord.User | None:
        """Get the user who closed the ticket, if any."""
        try:
            ticket = await GuildTicket.objects.aget(
                guild_id=self.guild_id, ticket_number=self.ticket_number
            )
            if ticket.closed_by:
                user = await self.get_guild_member(
                    interaction=interaction, user_id=ticket.closed_by
                )
                return user
        except GuildTicket.DoesNotExist:
            return interaction.user
        return None

    async def get_claimed_by(
        self, interaction: discord.Interaction
    ) -> discord.User | None:
        """Get the user who claimed the ticket, if any."""
        try:
            ticket = await GuildTicket.objects.aget(
                guild_id=self.guild_id, ticket_number=self.ticket_number
            )
            if ticket.claimed_by:
                user = await self.get_guild_member(
                    interaction=interaction, user_id=ticket.claimed_by
                )
                return user
        except GuildTicket.DoesNotExist:
            return interaction.user
        return None

    async def create_update_task(self, interaction: discord.Interaction) -> bool:
        """Update the channel topic und name based on ticket status."""
        closed_by = await self.get_closed_by(interaction)
        claimed_by = await self.get_claimed_by(interaction)
        channel_name = f"ticket{self.ticket_number}"
        topic_parts = ["Type: 📩 **OPEN TICKET**"]
        if closed_by:
            topic_parts.append(f"- Closed by: {closed_by.mention}")
        if claimed_by:
            topic_parts.append(f"- Claimed by: {claimed_by.mention}")
            channel_name += f"-claimed-{claimed_by.name}"
        else:
            channel_name += "-unclaimed"
        topic_parts.append(f"- Created by: {self.ticket_owner.mention}")
        channel_name += f"-{self.ticket_owner.name}"
        topic = " ".join(topic_parts)

        # Check for changes
        new_channel = None
        new_description = None
        if interaction.channel != topic:
            new_description = topic
        if interaction.channel.name != channel_name:
            new_channel = channel_name

        # Check if update is needed
        if not new_channel and not new_description:
            return False  # No update needed
        # Queue the update
        try:
            ticket = await GuildTicket.objects.aget(
                guild_id=self.guild_id, ticket_number=self.ticket_number
            )
            await GuildTicketTask.objects.aupdate_or_create(
                ticket=ticket,
                defaults={
                    "channel_name": new_channel,
                    "topic": new_description,
                    "is_queued": False,
                    "created_at": timezone.now(),
                    "completed_at": None,
                },
            )
        except Exception as e:
            logger.exception(f"Error queueing channel update: {e}")
            return False

        await interaction.message.edit(view=self)
        return True

    async def change_send_messages(
        self, interaction: discord.Interaction, allow_send_messages: bool
    ):
        """Change send messages permission for the ticket owner."""
        try:
            perms = interaction.channel.overwrites_for(self.ticket_owner)
            perms.send_messages = allow_send_messages
            await interaction.channel.set_permissions(
                self.ticket_owner, overwrite=perms
            )
            return
        except Exception as e:
            print(f"Error changing send messages permission: {e}")
            return

    async def claim_callback(self, interaction: discord.Interaction):
        if interaction.user == self.ticket_owner:
            return await interaction.response.send_message(
                "You cannot claim your own ticket!", ephemeral=True
            )
        self.claim_button.disabled = True
        try:
            ticket = await GuildTicket.objects.aget(
                guild_id=interaction.guild.id, ticket_number=self.ticket_number
            )
            ticket.claimed_by = interaction.user.id
            await ticket.asave()
        except GuildTicket.DoesNotExist:
            return await interaction.response.send_message(
                "Ticket record not found in database. Please contact an admin.",
                ephemeral=True,
            )
        except Exception as e:
            print(f"Error closing ticket: {e}")
            return await interaction.response.send_message(
                "An error occurred while closing the ticket. Please contact an admin.",
                ephemeral=True,
            )
        success = await self.create_update_task(interaction)
        if not success:
            return await interaction.response.send_message(
                "Failed to update the ticket channel. Please try again later.",
                ephemeral=True,
            )
        return await interaction.response.send_message(
            f"{interaction.user.mention} claimed the ticket."
        )

    async def close_callback(self, interaction: discord.Interaction):
        self.close_button.disabled = True
        self.claim_button.disabled = True
        try:
            ticket = await GuildTicket.objects.aget(
                guild_id=interaction.guild.id, ticket_number=self.ticket_number
            )
            ticket.closed_by = interaction.user.id
            ticket.closed_at = timezone.now()
            ticket.is_closed = True
            await ticket.asave()
        except GuildTicket.DoesNotExist:
            return await interaction.response.send_message(
                "Ticket record not found in database. Please contact an admin.",
                ephemeral=True,
            )
        except Exception as e:
            logger.exception(f"Error closing ticket: {e}")
            return await interaction.response.send_message(
                "An error occurred while closing the ticket. Please contact an admin.",
                ephemeral=True,
            )

        # Update After Saving
        success = await self.create_update_task(interaction)
        if not success:
            return await interaction.response.send_message(
                "Failed to update the ticket channel. Please try again later.",
                ephemeral=True,
            )
        await self.change_send_messages(
            interaction=interaction, allow_send_messages=False
        )
        return await interaction.response.send_message(
            f"{interaction.user.mention} closed the ticket."
        )

    async def reopen_callback(self, interaction: discord.Interaction):
        self.status = "open"
        self.close_button.disabled = False
        self.claim_button.disabled = False
        try:
            ticket = await GuildTicket.objects.aget(
                guild_id=interaction.guild.id, ticket_number=self.ticket_number
            )
            ticket.closed_by = None
            ticket.closed_at = None
            ticket.is_closed = False
            ticket.claimed_by = None
            await ticket.asave()
        except GuildTicket.DoesNotExist:
            return await interaction.response.send_message(
                "Ticket record not found in database. Please contact an admin.",
                ephemeral=True,
            )
        except Exception as e:
            logger.exception(f"Error reopening ticket: {e}")
            return await interaction.response.send_message(
                "An error occurred while reopening the ticket. Please contact an admin.",
                ephemeral=True,
            )

        # Update After Saving
        success = await self.create_update_task(interaction)
        if not success:
            return await interaction.response.send_message(
                "Failed to update the ticket channel. Please try again later.",
                ephemeral=True,
            )
        await self.change_send_messages(
            interaction=interaction, allow_send_messages=True
        )
        return await interaction.response.send_message(
            f"{interaction.user.mention} reopened the ticket."
        )

    async def delete_callback(self, interaction: discord.Interaction):
        permissions = interaction.channel.permissions_for(interaction.user)
        if permissions.manage_threads or permissions.manage_channels:
            try:
                ticket = await GuildTicket.objects.aget(
                    guild_id=interaction.guild.id, ticket_number=self.ticket_number
                )
                await ticket.adelete()
                return await interaction.channel.delete()
            except GuildTicket.DoesNotExist:
                return await interaction.response.send_message(
                    "Ticket record not found in database. Please contact an admin.",
                    ephemeral=True,
                )
            except discord.errors.HTTPException as e:
                if e.code == 10003:  # Unknown Channel
                    return
                logger.exception(f"Failed to delete thread: {e}")
                return await interaction.response.send_message(
                    "Failed to delete thread, please try again later.",
                    ephemeral=True,
                )
            except Exception as e:
                logger.exception(f"Error deleting ticket: {e}")
                return await interaction.response.send_message(
                    "An error occurred while deleting the ticket. Please contact an admin.",
                    ephemeral=True,
                )
        return await interaction.response.send_message(
            "You do not have permission to delete this thread!",
            ephemeral=True,
        )
