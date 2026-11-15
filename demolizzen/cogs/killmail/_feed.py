"""Reads killmails from zKillboard's R2Z2 feed, one sequence number at a time."""

# Standard Library
import logging

# Third Party
import aiohttp

# Demolizzen
from demolizzen.constants import (
    RETRY_DELAY,
    ZKILLBOARD_R2Z2_SEQUENCE_URL,
    ZKILLBOARD_R2Z2_URL,
)

logger = logging.getLogger(__name__)


class Backoff:
    """Waiting times that double with every failure, up to a limit."""

    def __init__(self, first: float = 1, limit: float = 300):
        self.first = first
        self.limit = limit
        self._next = first

    def next(self) -> float:
        value = self._next
        self._next = min(self._next * 2, self.limit)
        return value

    def reset(self) -> None:
        self._next = self.first


class KillmailFeed:
    """Fetches the feed step by step.

    :meth:`step` performs one request and returns how long to wait before the
    next one. The sequence number always moves on after an answer, so one bad
    killmail cannot block the feed; it only stays where it is while the server
    cannot be reached, and the waiting time grows meanwhile.
    """

    SUCCESS_DELAY = 0.2
    IDLE_DELAY = 10
    # After this many "nothing new" answers in a row the feed checks whether it
    # still follows the current sequence.
    RESYNC_AFTER = 30

    def __init__(
        self,
        get_session,
        handle,
        sequence_url: str = ZKILLBOARD_R2Z2_SEQUENCE_URL,
        killmail_url: str = ZKILLBOARD_R2Z2_URL,
        headers: dict | None = None,
        timeout: aiohttp.ClientTimeout | None = None,
    ):
        self._get_session = get_session
        self._handle = handle
        self._sequence_url = sequence_url
        self._killmail_url = killmail_url
        self._headers = headers or {}
        self._timeout = timeout or aiohttp.ClientTimeout(connect=5, total=30)
        self._backoff = Backoff()
        self._idle_steps = 0
        self.sequence: int | None = None
        self.processed = 0

    async def step(self) -> float:
        """Do one request and return the seconds to wait before the next step."""
        try:
            return await self._step()
        except (aiohttp.ClientError, TimeoutError) as error:
            logger.warning("Killmail feed is unreachable: %r", error)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Killmail feed step failed")
        return self._backoff.next()

    async def _get(self, session, url: str):
        """Return status, decoded JSON (or None) and the wait asked for by a 429."""
        async with session.get(
            url, headers=self._headers, timeout=self._timeout
        ) as response:
            data, retry_after = None, None
            if response.status == 200:
                try:
                    data = await response.json(content_type=None)
                except ValueError:
                    data = None
            elif response.status == 429:
                try:
                    retry_after = int(response.headers.get("Retry-After", RETRY_DELAY))
                except (TypeError, ValueError):
                    retry_after = RETRY_DELAY
                # "Retry-After: 0" must not turn into a tight loop.
                retry_after = max(retry_after, 1)
            return response.status, data, retry_after

    async def _current_sequence(self, session):
        """Return (sequence, None) or (None, seconds to wait)."""
        status, data, retry_after = await self._get(session, self._sequence_url)
        if status == 429:
            return None, retry_after
        if status == 200 and isinstance(data, dict) and "sequence" in data:
            try:
                return int(data["sequence"]), None
            except (TypeError, ValueError):
                pass
        logger.info("Killmail feed gave no sequence (status %s).", status)
        return None, None

    async def _step(self) -> float:
        session = self._get_session()
        if session is None:
            return self._backoff.next()

        if self.sequence is None:
            sequence, wait = await self._current_sequence(session)
            if sequence is None:
                return wait if wait is not None else self._backoff.next()
            self.sequence = sequence
            self._backoff.reset()
            return self.SUCCESS_DELAY

        status, data, retry_after = await self._get(
            session, f"{self._killmail_url}{self.sequence}.json"
        )
        if status == 200:
            self._backoff.reset()
            self._idle_steps = 0
            await self._process(data)
            self.sequence += 1
            return self.SUCCESS_DELAY
        if status == 404:
            self._backoff.reset()
            self._idle_steps += 1
            if self._idle_steps >= self.RESYNC_AFTER:
                self._idle_steps = 0
                await self._resync(session)
            return self.IDLE_DELAY
        if status == 429:
            return retry_after
        logger.info("Killmail feed answered with status %s.", status)
        return self._backoff.next()

    async def _process(self, data) -> None:
        """Hand a killmail to the handler. A bad killmail is logged and skipped."""
        if not isinstance(data, dict) or "killmail_id" not in data:
            logger.warning("Sequence %s holds no killmail; skipping it.", self.sequence)
            return
        try:
            await self._handle(data)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception(
                "Killmail %s (sequence %s) could not be processed; skipping it.",
                data.get("killmail_id"),
                self.sequence,
            )
        self.processed += 1

    async def _resync(self, session) -> None:
        """Jump ahead if the feed has moved on without us."""
        current, _ = await self._current_sequence(session)
        if current is not None and current > self.sequence:
            logger.warning(
                "Killmail feed moved from sequence %s to %s; skipping the gap.",
                self.sequence,
                current,
            )
            self.sequence = current
