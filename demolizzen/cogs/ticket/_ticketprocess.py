# Standard Library
import asyncio
import logging

# Discord
import discord

# Django
from django.utils import timezone

# Demolizzen
from demolizzen.core.bot import Demolizzen
from demolizzen.models.guild import (
    GuildTicket,
    GuildTicketSettings,
    GuildTicketTask,
)

logger = logging.getLogger(__name__)


# pylint: disable=too-many-statements
class ChannelUpdateProcessor:
    """Helper to process a single GuildTicketTask/channel update."""

    def __init__(
        self,
        bot: Demolizzen,
        channel: discord.TextChannel = None,
        task: GuildTicketTask = None,
    ):
        self.bot = bot
        self.channel = channel
        self.task = task
        self.logger = logger
        self.kwargs = {}
        self.should_archive = False
        self._archiver_task = None
        self._worker_task = None
        self._stopped = False
        # Map of task_id -> asyncio.Task for active per-ticket processors
        self._processing_tasks = {}

    def start(self):
        """Start background loops for archiving and processing."""
        loop = self.bot.loop
        self._stopped = False
        self._archiver_task = loop.create_task(self._ticket_archiver_loop())
        self._worker_task = loop.create_task(self._channel_update_worker_loop())

    def stop(self):
        """Stop background loops."""
        self._stopped = True
        if self._archiver_task:
            self._archiver_task.cancel()
        if self._worker_task:
            self._worker_task.cancel()

    async def run(self):
        """Run the processing for the assigned task."""
        try:
            if not await self._validate_presence():
                return

            await self._collect_basic_updates()
            await self._collect_archive_or_reopen()

            if self.kwargs:
                await self._perform_edit()

            if self.should_archive:
                await self._persist_archive()

            await self._finalize()
        except Exception as e:
            self.logger.info(
                f"Unexpected error in channel update worker for task {self.task}: {e}"
            )
            await self._mark_task_for_retry()

    async def _ticket_archiver_loop(self):
        """Background loop to archive closed tickets."""
        await self.bot.wait_until_ready()
        while not self._stopped:
            try:
                tickets = [
                    ticket
                    async for ticket in GuildTicket.objects.filter(
                        is_closed=True, is_archived=False
                    ).select_related("guild")
                ]
                for ticket in tickets:
                    try:
                        guild_settings = await GuildTicketSettings.objects.aget(
                            guild=ticket.guild
                        )

                        # Skip if no archive category is set
                        if guild_settings.archive_category_id is None:
                            continue

                        # Skip if closed_at is missing
                        if not ticket.closed_at:
                            self.logger.warning(
                                f"Ticket {ticket} has no closed_at; skipping archive task."
                            )
                            continue

                        # Check if the ticket should be archived
                        if (
                            ticket.closed_at
                            + timezone.timedelta(days=guild_settings.auto_archive_days)
                            < timezone.now()
                        ):
                            # Create a GuildTicketTask for archiving.
                            __, created = await GuildTicketTask.objects.aget_or_create(
                                ticket=ticket
                            )
                            if created:
                                self.logger.debug(
                                    f"Created archive task for ticket {ticket}"
                                )
                    except Exception as e:
                        self.logger.error(
                            f"Error creating archive task for ticket {ticket}: {e}"
                        )
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Unexpected error in ticket archiver loop")
            # sleep for 1 day between runs
            await asyncio.sleep(60 * 60 * 24)

    async def _channel_update_worker_loop(self):
        """Background loop to process channel update tasks."""
        await self.bot.wait_until_ready()
        while not self._stopped:
            try:
                c_tasks = [
                    ticket_task
                    async for ticket_task in GuildTicketTask.objects.all().select_related(
                        "ticket", "ticket__guild", "ticket__guild__ticket_settings"
                    )
                ]
                self.logger.debug(
                    f"Running channel update worker... {len(c_tasks)} tasks found."
                )
                for task in c_tasks:
                    try:
                        guild = discord.utils.get(
                            self.bot.guilds, id=task.ticket.guild.guild_id
                        )
                        channel = (
                            discord.utils.get(guild.channels, id=task.ticket.channel_id)
                            if guild
                            else None
                        )
                        # If task not queued -> claim and start processing
                        if not task.is_queued:
                            task.is_queued = True
                            await task.asave()
                            # delegate to per-task processor and track the asyncio.Task
                            task_processor = ChannelUpdateProcessor(
                                self.bot, channel, task
                            )

                            async def _run_and_cleanup(proc, t_id):
                                try:
                                    await proc.run()
                                except Exception:
                                    self.logger.exception(
                                        f"Error running processor for task {t_id}"
                                    )
                                finally:
                                    # remove from active mapping when done
                                    self._processing_tasks.pop(t_id, None)

                            wrapped = _run_and_cleanup(task_processor, task.task_id)
                            async_task = self.bot.loop.create_task(
                                asyncio.wait_for(wrapped, timeout=300)
                            )
                            self._processing_tasks[task.task_id] = async_task
                            continue

                        # Task is marked queued in DB. Check whether we have an active asyncio.Task for it.
                        if task.task_id not in self._processing_tasks:
                            # DB says queued but we have no in-memory worker -> re-enqueue
                            self.logger.warning(
                                f"Task {task} is marked queued but no active worker found; re-enqueueing."
                            )
                            task.is_queued = False
                            task.created_at = timezone.now()
                            await task.asave()
                            continue

                        # Task already being processed - skip
                        if task.is_queued and not task.is_outdated:
                            self.logger.debug(f"{task} is already being processed.")
                            continue
                        # Task is queued but outdated - reset one time
                        if task.is_queued and task.is_outdated and not task.has_error:
                            self.logger.warning(f"{task} is outdated, try again.")
                            task.is_queued = False
                            task.has_error = True
                            task.created_at = timezone.now()
                            await task.asave()
                            continue
                        # Task is queued, outdated and already had an error - delete task
                        if task.is_queued and task.is_outdated and task.has_error:
                            self.logger.error(
                                f"{task} has already failed once, deleting task."
                            )
                            await task.adelete()
                            continue
                        # Unknown state - log error and delete task
                        self.logger.error(f"Unknown state for {task}.")
                        await task.adelete()
                        continue
                    except Exception as e:
                        self.logger.error(f"Error processing ticket task {task}: {e}")
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Unexpected error in channel update worker loop")
            # sleep for 30 seconds between runs
            await asyncio.sleep(30)

    async def _validate_presence(self) -> bool:
        """Ensure that the channel and guild are present; if not, remove the task."""
        if not self.channel:
            self.logger.warning(
                f"Channel for task {self.task} not found, deleting task."
            )
            await self.task.adelete()
            return False

        guild = discord.utils.get(self.bot.guilds, id=self.task.ticket.guild.guild_id)
        if not guild:
            self.logger.warning(f"Guild for task {self.task} not found, deleting task.")
            await self.task.adelete()
            return False

        # store guild for later use
        self.guild = guild
        return True

    async def _collect_basic_updates(self):
        """Collect basic updates like name/topic changes."""
        try:
            if self.task.topic is not None and self.channel.topic != self.task.topic:
                self.kwargs["topic"] = self.task.topic
            if (
                self.task.channel_name is not None
                and self.channel.name != self.task.channel_name
            ):
                self.kwargs["name"] = self.task.channel_name
        except Exception as e:
            self.logger.debug(
                f"Error collecting basic updates for task {self.task}: {e}"
            )

    async def _collect_archive_or_reopen(self):
        """Determine if the ticket should be archived or moved back to help category."""
        try:
            ticket = self.task.ticket

            if (
                ticket.is_closed
                and not ticket.is_archived
                and ticket.closed_at
                and (
                    ticket.closed_at
                    + timezone.timedelta(
                        days=ticket.guild.ticket_settings.auto_archive_days
                    )
                    < timezone.now()
                )
            ):
                archive_category_id = ticket.guild.ticket_settings.archive_category_id
                if archive_category_id:
                    archive_category = discord.utils.get(
                        self.guild.categories, id=archive_category_id
                    )
                    if archive_category:
                        self.kwargs["category"] = archive_category
                        self.should_archive = True
                    else:
                        self.logger.debug(
                            f"Archive category id set ({archive_category_id}) but category not found in guild {self.guild.id}."
                        )
                else:
                    self.logger.debug(
                        f"No archive category configured for guild {self.guild.id}; will not archive ticket {self.task} now."
                    )

            # If the ticket is open (reopened) and not archived, ensure it is moved
            # back to the configured ticket category (help/category) if present.
            if not ticket.is_closed and not ticket.is_archived:
                try:
                    help_category_id = ticket.guild.ticket_settings.category_id
                    if help_category_id:
                        help_category = discord.utils.get(
                            self.guild.categories, id=help_category_id
                        )
                        if help_category:
                            # Only set category if the channel isn't already in the right one
                            if (
                                not self.channel.category
                                or self.channel.category.id != help_category_id
                            ):
                                self.kwargs["category"] = help_category
                        else:
                            self.logger.debug(
                                f"Help category id set ({help_category_id}) but category not found in guild {self.guild.id}."
                            )
                except Exception as e:
                    self.logger.debug(
                        f"Error checking reopen/move-to-help conditions for task {self.task}: {e}"
                    )
        except Exception as e:
            # Be defensive: log and continue with other updates
            self.logger.debug(
                f"Error checking archive conditions for task {self.task}: {e}"
            )

    async def _perform_edit(self):
        """Perform the channel edit with collected kwargs."""
        try:
            await self.channel.edit(**self.kwargs, reason="Ticket channel update task")
            self.logger.debug(
                f"Ticket {self.task} updated successfully with {list(self.kwargs.keys())}."
            )
        except Exception as e:
            self.logger.debug(
                f"Failed to edit channel {self.channel.id} for task {self.task}: {e}"
            )
            # Mark task for retry: clear queue flag and mark error so worker can handle retries
            await self._mark_task_for_retry()
            # Stop further processing
            raise

    async def _persist_archive(self):
        """Mark the ticket as archived in the database."""
        try:
            self.task.ticket.is_archived = True
            await self.task.ticket.asave()
            self.logger.debug(f"Ticket {self.task} archived successfully.")
        except Exception as e:
            self.logger.debug(
                f"Failed to mark ticket archived for task {self.task}: {e}"
            )

    async def _finalize(self):
        # No matter what, remove the task from the queue now that we've attempted updates
        try:
            await self.task.adelete()
        except Exception as e:
            self.logger.debug(f"Failed to delete task {self.task} during finalize: {e}")

    async def _mark_task_for_retry(self):
        try:
            self.task.is_queued = False
            self.task.has_error = True
            self.task.created_at = timezone.now()
            await self.task.asave()
        except Exception:
            self.logger.exception("Failed to mark task for retry.")
