"""Renames ticket channels without running into Discord's rename limit."""

# Standard Library
import asyncio
import logging
import time
from collections import deque

# Discord
import discord

logger = logging.getLogger(__name__)


class ChannelRenamer:
    """Brings channel names to their wanted value in the background.

    Discord allows two name changes per channel in ten minutes. py-cord would
    sleep inside the request when that limit is hit and block every other edit
    of the channel meanwhile, so the renamer keeps count itself and waits before
    sending. While it waits, only the most recent wanted name is kept.
    """

    LIMIT = 2
    WINDOW = 600

    def __init__(self, clock=time.monotonic, sleep=asyncio.sleep):
        self._clock = clock
        self._sleep = sleep
        self._sent: dict[int, deque[float]] = {}
        self._wanted: dict[int, tuple[discord.abc.GuildChannel, str]] = {}
        self._tasks: dict[int, asyncio.Task] = {}

    def request(self, channel, name: str) -> None:
        """Ask for ``channel`` to be called ``name``. Returns immediately."""
        if channel.id not in self._tasks and channel.name == name:
            return
        self._wanted[channel.id] = (channel, name)
        if channel.id not in self._tasks:
            self._tasks[channel.id] = asyncio.create_task(self._run(channel.id))

    async def wait(self, channel_id: int) -> None:
        """Wait until nothing is pending for the channel."""
        task = self._tasks.get(channel_id)
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)

    def cancel_all(self) -> None:
        """Drop all pending renames."""
        for task in list(self._tasks.values()):
            task.cancel()
        self._tasks.clear()
        self._wanted.clear()

    def _delay(self, channel_id: int) -> float:
        """Seconds to wait before the next rename of the channel may be sent."""
        sent = self._sent.setdefault(channel_id, deque())
        now = self._clock()
        while sent and now - sent[0] >= self.WINDOW:
            sent.popleft()
        if len(sent) < self.LIMIT:
            return 0.0
        return sent[0] + self.WINDOW - now

    async def _run(self, channel_id: int) -> None:
        try:
            while channel_id in self._wanted:
                delay = self._delay(channel_id)
                if delay > 0:
                    await self._sleep(delay)
                    continue
                channel, name = self._wanted.pop(channel_id)
                if channel.name == name:
                    continue
                self._sent[channel_id].append(self._clock())
                try:
                    await channel.edit(name=name, reason="Ticket status changed")
                except discord.HTTPException as exc:
                    logger.warning(
                        "Could not rename ticket channel %s to %s: %s",
                        channel_id,
                        name,
                        exc,
                    )
        finally:
            if self._tasks.get(channel_id) is asyncio.current_task():
                del self._tasks[channel_id]
