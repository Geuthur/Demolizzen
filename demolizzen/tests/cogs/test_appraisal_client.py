# Standard Library
import asyncio
import json

# Third Party
import aiohttp

# Django
from django.test import SimpleTestCase

# Demolizzen
from demolizzen.cogs.eveonline._appraisal import TIMEOUT, URL, AppraisalClient
from demolizzen.services.errors import PriceUnavailable
from demolizzen.services.prices import Quote


def item(name="Tritanium", sell="4.56", buy="3.4"):
    return {
        "name": name,
        "typeID": 34,
        "prices": {"sell": {"min": sell}, "buy": {"max": buy}},
    }


class Answer:
    def __init__(self, status=200, data=None, error=None, broken=False):
        self.status = status
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


class FakeSession:
    def __init__(self, answer):
        self.answer = answer
        self.requests = []

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.answer


class AppraisalClientTest(SimpleTestCase):
    def make_client(self, answer):
        self.session = FakeSession(answer)
        return AppraisalClient(lambda: self.session, headers={"User-Agent": "test"})

    async def test_quotes_are_read_from_the_answer(self):
        client = self.make_client(
            Answer(
                data={
                    "appraisal": {
                        "items": [item(), item("Pyerite", sell=10, buy="9.5")]
                    }
                }
            )
        )

        quotes = await client.quotes("jita", ["Tritanium", "Pyerite"])

        self.assertEqual(quotes, [Quote("Tritanium", 5, 3), Quote("Pyerite", 10, 10)])

    async def test_item_without_prices_counts_as_zero(self):
        client = self.make_client(
            Answer(data={"appraisal": {"items": [{"name": "Foo", "prices": {}}]}})
        )

        self.assertEqual(await client.quotes("jita", ["Foo"]), [Quote("Foo", 0, 0)])

    async def test_answer_without_items_is_an_empty_list(self):
        client = self.make_client(Answer(data={"appraisal": {"items": []}}))

        self.assertEqual(await client.quotes("jita", ["Foo"]), [])

    async def test_request_names_market_and_items(self):
        client = self.make_client(Answer(data={"appraisal": {"items": []}}))

        await client.quotes("amarr", ["Tritanium", "Pyerite"])

        ((url, kwargs),) = self.session.requests
        self.assertEqual(url, URL)
        self.assertEqual(url, "https://appraise.gnf.lt/appraisal/structured.json")
        self.assertEqual(
            kwargs["json"],
            {
                "market_name": "amarr",
                "items": [{"name": "Tritanium"}, {"name": "Pyerite"}],
            },
        )
        self.assertEqual(kwargs["headers"], {"User-Agent": "test"})
        self.assertIs(kwargs["timeout"], TIMEOUT)
        self.assertEqual(TIMEOUT.total, 10)

    async def test_error_status_is_unavailable(self):
        for status in (400, 404, 429, 500, 503):
            with self.subTest(status=status):
                client = self.make_client(Answer(status=status))

                with (
                    self.assertRaises(PriceUnavailable),
                    self.assertLogs("demolizzen.cogs.eveonline._appraisal", "WARNING"),
                ):
                    await client.quotes("jita", ["Tritanium"])

    async def test_timeout_and_connection_error_are_unavailable(self):
        errors = (
            asyncio.TimeoutError(),
            aiohttp.ClientConnectionError("down"),
            aiohttp.ServerTimeoutError(),
        )
        for error in errors:
            with self.subTest(error=type(error).__name__):
                client = self.make_client(Answer(error=error))

                with (
                    self.assertRaises(PriceUnavailable),
                    self.assertLogs("demolizzen.cogs.eveonline._appraisal", "WARNING"),
                ):
                    await client.quotes("jita", ["Tritanium"])

    async def test_unreadable_answer_is_unavailable(self):
        answers = {
            "broken json": Answer(broken=True),
            "no appraisal": Answer(data={"something": 1}),
            "a list": Answer(data=[1, 2]),
            "items are no list": Answer(data={"appraisal": {"items": 5}}),
            "item without name": Answer(
                data={"appraisal": {"items": [{"prices": {}}]}}
            ),
            "price is text": Answer(
                data={"appraisal": {"items": [item(sell="a lot")]}}
            ),
        }
        for name, answer in answers.items():
            with self.subTest(case=name):
                client = self.make_client(answer)

                with (
                    self.assertRaises(PriceUnavailable),
                    self.assertLogs("demolizzen.cogs.eveonline._appraisal", "WARNING"),
                ):
                    await client.quotes("jita", ["Tritanium"])

    async def test_missing_session_is_unavailable(self):
        client = AppraisalClient(lambda: None)

        with self.assertRaises(PriceUnavailable):
            await client.quotes("jita", ["Tritanium"])
