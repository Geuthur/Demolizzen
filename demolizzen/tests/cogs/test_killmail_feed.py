# Standard Library
import asyncio
import json
from unittest.mock import AsyncMock

# Third Party
import aiohttp

# Django
from django.test import SimpleTestCase

# Demolizzen
from demolizzen.cogs.killmail._feed import Backoff, KillmailFeed
from demolizzen.constants import RETRY_DELAY

SEQUENCE_URL = "https://feed.example/sequence.json"
KILL_URL = "https://feed.example/"


class Answer:
    """One HTTP answer of the fake feed."""

    def __init__(self, status=200, data=None, headers=None, error=None, broken=False):
        self.status = status
        self.headers = headers or {}
        self._data = data
        self._error = error
        self._broken = broken

    async def __aenter__(self):
        if self._error is not None:
            raise self._error
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def json(self, **kwargs):
        if self._broken:
            raise json.JSONDecodeError("bad", "{", 0)
        return self._data


class FakeFeedSession:
    def __init__(self):
        self.sequence = Answer(data={"sequence": 100})
        self.kills = {}
        self.default = Answer(status=404)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        if url == SEQUENCE_URL:
            return self.sequence
        number = int(url.removeprefix(KILL_URL).removesuffix(".json"))
        return self.kills.get(number, self.default)


def kill(killmail_id=1):
    return Answer(data={"killmail_id": killmail_id, "hash": "abc"})


class BackoffTest(SimpleTestCase):
    def test_doubles_up_to_the_limit_and_resets(self):
        backoff = Backoff(first=1, limit=300)

        self.assertEqual(
            [backoff.next() for _ in range(11)],
            [1, 2, 4, 8, 16, 32, 64, 128, 256, 300, 300],
        )
        backoff.reset()
        self.assertEqual(backoff.next(), 1)


class KillmailFeedTest(SimpleTestCase):
    def setUp(self):
        self.session = FakeFeedSession()
        self.handle = AsyncMock()
        self.feed = KillmailFeed(
            lambda: self.session,
            self.handle,
            sequence_url=SEQUENCE_URL,
            killmail_url=KILL_URL,
        )

    async def started(self):
        await self.feed.step()
        self.assertEqual(self.feed.sequence, 100)

    async def test_first_step_fetches_the_sequence(self):
        delay = await self.feed.step()

        self.assertEqual(self.feed.sequence, 100)
        self.assertEqual(delay, KillmailFeed.SUCCESS_DELAY)
        self.handle.assert_not_awaited()

    async def test_failing_sequence_backs_off(self):
        self.session.sequence = Answer(status=503)

        delays = [await self.feed.step() for _ in range(3)]

        self.assertEqual(delays, [1, 2, 4])
        self.assertIsNone(self.feed.sequence)

    async def test_sequence_answer_without_number_backs_off(self):
        self.session.sequence = Answer(data={"nope": 1})

        self.assertEqual(await self.feed.step(), 1)
        self.assertIsNone(self.feed.sequence)

    async def test_killmail_is_handled_and_sequence_advances(self):
        await self.started()
        self.session.kills[100] = kill(7)

        delay = await self.feed.step()

        self.handle.assert_awaited_once_with({"killmail_id": 7, "hash": "abc"})
        self.assertEqual(self.feed.sequence, 101)
        self.assertEqual(self.feed.processed, 1)
        self.assertEqual(delay, 0.2)

    async def test_bad_killmails_are_skipped(self):
        cases = {
            "no killmail id": Answer(data={"something": 1}),
            "not an object": Answer(data=[1, 2]),
            "broken json": Answer(broken=True),
        }
        for name, answer in cases.items():
            with self.subTest(case=name):
                self.feed.sequence = 100
                self.session.kills[100] = answer

                with self.assertLogs("demolizzen.cogs.killmail._feed", "WARNING"):
                    delay = await self.feed.step()

                self.assertEqual(self.feed.sequence, 101)
                self.assertEqual(delay, 0.2)
        self.handle.assert_not_awaited()

    async def test_failing_handler_does_not_block_the_feed(self):
        await self.started()
        self.session.kills[100] = kill(7)
        self.session.kills[101] = kill(8)
        self.handle.side_effect = [RuntimeError("boom"), None]

        with self.assertLogs("demolizzen.cogs.killmail._feed", "ERROR"):
            await self.feed.step()
        await self.feed.step()

        self.assertEqual(self.feed.sequence, 102)
        self.assertEqual(self.handle.await_count, 2)

    async def test_no_new_killmail_waits(self):
        await self.started()

        delay = await self.feed.step()

        self.assertEqual(delay, KillmailFeed.IDLE_DELAY)
        self.assertEqual(delay, 10)
        self.assertEqual(self.feed.sequence, 100)

    async def test_long_silence_resyncs_with_the_current_sequence(self):
        await self.started()
        self.session.sequence = Answer(data={"sequence": 250})

        for _ in range(KillmailFeed.RESYNC_AFTER - 1):
            await self.feed.step()
        self.assertEqual(self.feed.sequence, 100)
        with self.assertLogs("demolizzen.cogs.killmail._feed", "WARNING"):
            await self.feed.step()

        self.assertEqual(self.feed.sequence, 250)
        self.assertEqual(KillmailFeed.RESYNC_AFTER, 30)

    async def test_resync_never_goes_backwards(self):
        await self.started()
        self.session.sequence = Answer(data={"sequence": 90})

        for _ in range(KillmailFeed.RESYNC_AFTER):
            await self.feed.step()

        self.assertEqual(self.feed.sequence, 100)

    async def test_errors_back_off_and_keep_the_sequence(self):
        errors = [
            Answer(status=500),
            Answer(status=502),
            Answer(status=503),
            Answer(status=504),
            Answer(error=asyncio.TimeoutError()),
            Answer(error=aiohttp.ClientConnectionError("down")),
            Answer(error=aiohttp.ServerTimeoutError()),
        ]
        await self.started()
        delays = []
        for answer in errors:
            self.session.kills[100] = answer
            delays.append(await self.feed.step())

        self.assertEqual(delays, [1, 2, 4, 8, 16, 32, 64])
        self.assertEqual(self.feed.sequence, 100)

    async def test_backoff_grows_to_the_limit(self):
        await self.started()
        self.session.kills[100] = Answer(status=503)

        delays = [await self.feed.step() for _ in range(12)]

        self.assertEqual(max(delays), 300)
        self.assertEqual(delays[-1], 300)

    async def test_success_resets_the_backoff(self):
        await self.started()
        self.session.kills[100] = Answer(status=503)
        await self.feed.step()
        await self.feed.step()
        self.session.kills[100] = kill()
        await self.feed.step()
        self.session.kills[101] = Answer(status=503)

        self.assertEqual(await self.feed.step(), 1)

    async def test_rate_limit_waits_as_told(self):
        await self.started()
        self.session.kills[100] = Answer(status=429, headers={"Retry-After": "42"})
        self.assertEqual(await self.feed.step(), 42)

        self.session.kills[100] = Answer(status=429)
        self.assertEqual(await self.feed.step(), RETRY_DELAY)

        self.session.kills[100] = Answer(status=429, headers={"Retry-After": "soon"})
        self.assertEqual(await self.feed.step(), RETRY_DELAY)
        self.assertEqual(self.feed.sequence, 100)

    async def test_rate_limited_sequence_request(self):
        self.session.sequence = Answer(status=429, headers={"Retry-After": "7"})

        self.assertEqual(await self.feed.step(), 7)

    async def test_missing_session_backs_off(self):
        feed = KillmailFeed(lambda: None, self.handle)

        self.assertEqual(await feed.step(), 1)

    async def test_cancellation_is_passed_on(self):
        await self.started()
        self.session.kills[100] = Answer(error=asyncio.CancelledError())

        with self.assertRaises(asyncio.CancelledError):
            await self.feed.step()

    async def test_requests_never_repeat_faster_than_the_delays(self):
        await self.started()
        self.session.kills[100] = Answer(status=503)

        for _ in range(5):
            self.assertGreaterEqual(await self.feed.step(), 1)
