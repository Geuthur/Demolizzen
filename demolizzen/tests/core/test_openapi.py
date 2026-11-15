# Standard Library
import asyncio
import inspect
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Third Party
from esi.exceptions import HTTPClientError, HTTPServerError

# Django
from django.apps import apps
from django.test import SimpleTestCase, TestCase

# Demolizzen
from demolizzen.core import openapi
from demolizzen.core.openapi import OpenAPI
from demolizzen.models import EveEntityCache, MapSolarSystems

NAMES = {
    10: ("character", "Alice"),
    20: ("corporation", "Alpha Corp"),
    30: ("alliance", "Alpha Alliance"),
}


class FakeOperation:
    def __init__(self, run):
        self._run = run

    def result(self, **kwargs):
        return self._run()


class FakeUniverse:
    """Stands in for esi.client.Universe; records calls and the thread they ran in."""

    def __init__(self, names=None, invalid=(), error=None, delay=0.0):
        self.names = dict(names or NAMES)
        self.invalid = set(invalid)
        self.error = error
        self.delay = delay
        self.calls = []
        self.threads = []

    def PostUniverseNames(self, body):  # pylint: disable=invalid-name
        def run():
            self.calls.append(list(body))
            self.threads.append(threading.current_thread())
            if self.delay:
                time.sleep(self.delay)
            if self.error is not None:
                raise self.error
            if self.invalid & set(body):
                raise HTTPClientError(404, {}, None)
            return [
                SimpleNamespace(id=i, category=self.names[i][0], name=self.names[i][1])
                for i in body
                if i in self.names
            ]

        return FakeOperation(run)


def fake_esi(universe):
    return SimpleNamespace(client=SimpleNamespace(Universe=universe))


class OpenAPITestCase(TestCase):
    def setUp(self):
        self.api = OpenAPI(MagicMock())
        self.addCleanup(self.api.close)

    def use(self, universe):
        patcher = patch.object(openapi, "esi", fake_esi(universe))
        patcher.start()
        self.addCleanup(patcher.stop)
        return universe


class CallTest(OpenAPITestCase):
    async def test_operation_runs_off_the_event_loop(self):
        loop_thread = threading.current_thread()
        seen = []

        def run():
            seen.append(threading.current_thread())
            return "data"

        result = await self.api._call(lambda: FakeOperation(run))

        self.assertEqual(result, "data")
        self.assertIsNot(seen[0], loop_thread)

    async def test_event_loop_keeps_running_during_a_slow_call(self):
        ticks = []

        async def ticker():
            for _ in range(5):
                ticks.append(1)
                await asyncio.sleep(0.01)

        def slow():
            time.sleep(0.1)
            return "done"

        result, _ = await asyncio.gather(
            self.api._call(lambda: FakeOperation(slow)), ticker()
        )

        self.assertEqual(result, "done")
        self.assertEqual(len(ticks), 5)

    async def test_operation_errors_are_passed_on(self):
        def boom():
            raise HTTPServerError(503, {}, None)

        with self.assertRaises(HTTPServerError):
            await self.api._call(lambda: FakeOperation(boom))


class ResolveNamesTest(OpenAPITestCase):
    async def cached(self) -> dict[int, str]:
        return {e.entity_id: e.entity_name async for e in EveEntityCache.objects.all()}

    async def test_cached_names_need_no_esi_call(self):
        universe = self.use(FakeUniverse())
        await EveEntityCache.objects.acreate(
            entity_id=10, entity_name="Alice", category="character"
        )

        self.assertEqual(await self.api.resolve_names([10]), {10: "Alice"})
        self.assertEqual(universe.calls, [])

    async def test_missing_names_are_fetched_in_one_call_and_stored(self):
        universe = self.use(FakeUniverse())
        await EveEntityCache.objects.acreate(
            entity_id=10, entity_name="Alice", category="character"
        )

        names = await self.api.resolve_names([10, 20, 30])

        self.assertEqual(names, {10: "Alice", 20: "Alpha Corp", 30: "Alpha Alliance"})
        self.assertEqual([sorted(call) for call in universe.calls], [[20, 30]])
        self.assertEqual(
            await self.cached(), {10: "Alice", 20: "Alpha Corp", 30: "Alpha Alliance"}
        )
        self.assertEqual(
            (await EveEntityCache.objects.aget(entity_id=20)).category, "corporation"
        )

    async def test_empty_and_falsy_ids(self):
        universe = self.use(FakeUniverse())

        self.assertEqual(await self.api.resolve_names([]), {})
        self.assertEqual(await self.api.resolve_names([None, 0]), {})
        self.assertEqual(universe.calls, [])

    async def test_duplicate_ids_are_asked_once(self):
        universe = self.use(FakeUniverse())

        names = await self.api.resolve_names([20, 20, 20])

        self.assertEqual(names, {20: "Alpha Corp"})
        self.assertEqual(universe.calls, [[20]])

    async def test_invalid_id_does_not_poison_the_batch(self):
        universe = self.use(FakeUniverse(invalid={99}))

        names = await self.api.resolve_names([20, 99, 30])

        self.assertEqual(names, {20: "Alpha Corp", 99: "Unknown", 30: "Alpha Alliance"})
        self.assertNotIn(99, await self.cached())
        self.assertIn(20, await self.cached())
        self.assertEqual(len(universe.calls), 4)  # the batch, then one call per id

    async def test_id_esi_does_not_know(self):
        self.use(FakeUniverse())

        self.assertEqual(await self.api.resolve_names([555]), {555: "Unknown"})
        self.assertEqual(await self.cached(), {})

    async def test_server_error_gives_unknown_without_raising(self):
        self.use(FakeUniverse(error=HTTPServerError(503, {}, None)))

        with self.assertLogs("esi", "WARNING"):
            names = await self.api.resolve_names([20])

        self.assertEqual(names, {20: "Unknown"})
        self.assertEqual(await self.cached(), {})

    async def test_timeout_gives_unknown_without_hanging(self):
        self.use(FakeUniverse(delay=0.3))

        with patch.object(OpenAPI, "NAME_TIMEOUT", 0.05):
            with self.assertLogs("esi", "WARNING"):
                started = time.monotonic()
                names = await self.api.resolve_names([20])

        self.assertEqual(names, {20: "Unknown"})
        self.assertLess(time.monotonic() - started, 0.25)

    async def test_large_requests_are_split(self):
        ids = list(range(1000, 3500))
        universe = self.use(
            FakeUniverse(names={i: ("character", f"Pilot {i}") for i in ids})
        )

        names = await self.api.resolve_names(ids)

        self.assertEqual(len(names), 2500)
        self.assertEqual(
            sorted(len(call) for call in universe.calls), [500, 1000, 1000]
        )
        self.assertEqual(OpenAPI.NAME_BATCH, 1000)
        self.assertEqual(OpenAPI.NAME_TIMEOUT, 15)

    async def test_single_name_helpers_use_the_same_path(self):
        universe = self.use(FakeUniverse())

        self.assertEqual(await self.api.get_or_create_character_name(10), "Alice")
        self.assertEqual(
            await self.api.get_or_create_corporation_name(20), "Alpha Corp"
        )
        self.assertEqual(
            await self.api.get_or_create_alliance_name(30), "Alpha Alliance"
        )
        self.assertIsNone(await self.api.get_or_create_character_name(None))
        self.assertEqual(len(universe.calls), 3)
        self.assertEqual(await self.api.get_or_create_character_name(10), "Alice")
        self.assertEqual(len(universe.calls), 3)


class RegionTest(OpenAPITestCase):
    async def test_region_is_read_once_per_system(self):
        await MapSolarSystems.objects.acreate(
            solarSystemID=30000142,
            solarSystemName="Jita",
            regionID=10000002,
            constellationID=20000020,
        )

        self.assertEqual(await self.api.get_region_id(30000142), 10000002)
        await MapSolarSystems.objects.all().adelete()
        self.assertEqual(await self.api.get_region_id(30000142), 10000002)

    async def test_unknown_system(self):
        self.assertIsNone(await self.api.get_region_id(1))
        self.assertIsNone(await self.api.get_region_id(None))


class OpenAPISourceTest(SimpleTestCase):
    def test_esi_results_are_only_awaited_through_call(self):
        source = inspect.getsource(openapi)
        call_body = inspect.getsource(OpenAPI._call)

        self.assertEqual(source.count(".result("), call_body.count(".result("))
        self.assertEqual(call_body.count(".result("), 1)

    def test_entity_task_table_is_gone(self):
        with self.assertRaises(LookupError):
            apps.get_model("demolizzen", "EveEntityTask")
        self.assertFalse(hasattr(OpenAPI, "_entity_name_worker"))
