# Standard Library
from datetime import timedelta

# Django
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

# Demolizzen
from demolizzen.models import EvePricecache, InvTypes
from demolizzen.services import prices
from demolizzen.services.errors import PriceNotFound, PriceUnavailable
from demolizzen.services.prices import Price, Quote

JITA = prices.TRADEHUBS["jita"]
AMARR = prices.TRADEHUBS["amarr"]
NOW = timezone.now()


def fetcher(*quotes, error=None):
    """A stand-in for the price service that remembers what it was asked."""

    async def fetch(market, names):
        fetch.calls.append((market, list(names)))
        if error is not None:
            raise error
        return list(quotes)

    fetch.calls = []
    return fetch


class TradehubTest(SimpleTestCase):
    def test_tradehub_lookup_ignores_case_and_defaults_to_jita(self):
        self.assertEqual(prices.tradehub("Amarr"), AMARR)
        self.assertEqual(prices.tradehub("amarr"), AMARR)
        self.assertEqual(prices.tradehub(None), JITA)
        self.assertEqual(prices.tradehub("nowhere"), JITA)

    def test_tradehubs(self):
        # Only markets the price service knows: it answers 400 for Rens and Hek.
        self.assertEqual(sorted(prices.TRADEHUBS), ["amarr", "dodixie", "jita"])
        self.assertEqual(
            (JITA.key, JITA.title, JITA.station),
            ("jita", "Jita", "Jita IV - Moon 4 - Caldari Navy Assembly Plant"),
        )


class GetPriceTest(TestCase):
    async def cache(self, name="Tritanium", hub=JITA, sell=5, buy=4, minutes=10):
        return await EvePricecache.objects.acreate(
            item_name=name,
            tradehub=hub.key,
            price=sell,
            buy=buy,
            expiration=NOW + timedelta(minutes=minutes),
        )

    async def test_fresh_cache_entry_is_used_without_asking(self):
        await self.cache()
        fetch = fetcher()

        price = await prices.get_price("Tritanium", JITA, fetch, now=NOW)

        self.assertEqual(price, Price("Tritanium", JITA, 5, 4, cached=True))
        self.assertEqual(fetch.calls, [])

    async def test_missing_entry_is_fetched_and_stored(self):
        fetch = fetcher(Quote("Tritanium", 5, 4))

        price = await prices.get_price("Tritanium", JITA, fetch, now=NOW)

        self.assertEqual(price, Price("Tritanium", JITA, 5, 4, cached=False))
        self.assertEqual(fetch.calls, [("jita", ["Tritanium"])])
        entry = await EvePricecache.objects.aget()
        self.assertEqual(
            (entry.item_name, entry.tradehub, entry.price, entry.buy),
            ("Tritanium", "jita", 5, 4),
        )
        self.assertEqual(entry.expiration, NOW + timedelta(seconds=1800))
        self.assertEqual(prices.CACHE_SECONDS, 1800)

    async def test_expired_entry_is_fetched_again_and_updated(self):
        await self.cache(minutes=-1)
        fetch = fetcher(Quote("Tritanium", 9, 8))

        price = await prices.get_price("Tritanium", JITA, fetch, now=NOW)

        self.assertEqual((price.sell, price.buy, price.cached), (9, 8, False))
        entry = await EvePricecache.objects.aget()
        self.assertEqual((entry.price, entry.buy), (9, 8))
        self.assertGreater(entry.expiration, NOW)

    async def test_same_item_in_two_tradehubs(self):
        await prices.get_price("Tritanium", JITA, fetcher(Quote("Tritanium", 5, 4)))
        await prices.get_price("Tritanium", AMARR, fetcher(Quote("Tritanium", 7, 6)))

        nobody = fetcher()
        jita = await prices.get_price("Tritanium", JITA, nobody)
        amarr = await prices.get_price("Tritanium", AMARR, nobody)

        self.assertEqual((jita.sell, jita.buy, jita.cached), (5, 4, True))
        self.assertEqual((amarr.sell, amarr.buy, amarr.cached), (7, 6, True))
        self.assertEqual(await EvePricecache.objects.acount(), 2)

    async def test_item_name_case_does_not_matter(self):
        first = await prices.get_price(
            " tritanium ", JITA, fetcher(Quote("Tritanium", 5, 4))
        )
        again = await prices.get_price("TRITANIUM", JITA, fetcher())

        self.assertEqual(first.item_name, "Tritanium")
        self.assertEqual(again, Price("Tritanium", JITA, 5, 4, cached=True))
        self.assertEqual(await EvePricecache.objects.acount(), 1)

    async def test_unknown_item_is_not_found_and_not_stored(self):
        with self.assertRaises(PriceNotFound) as raised:
            await prices.get_price("Foo", JITA, fetcher())

        self.assertEqual(
            raised.exception.message, "No market price found for **Foo** in Jita."
        )
        self.assertEqual(await EvePricecache.objects.acount(), 0)

    async def test_empty_name_is_not_asked(self):
        fetch = fetcher()

        with self.assertRaises(PriceNotFound):
            await prices.get_price("  ", JITA, fetch)

        self.assertEqual(fetch.calls, [])

    async def test_item_without_orders_is_not_found(self):
        with self.assertRaises(PriceNotFound):
            await prices.get_price("Foo", JITA, fetcher(Quote("Foo", 0, 0)))

        self.assertEqual(await EvePricecache.objects.acount(), 0)

    async def test_only_buy_orders_is_a_price(self):
        price = await prices.get_price("Foo", JITA, fetcher(Quote("Foo", 0, 7)))

        self.assertEqual((price.sell, price.buy), (0, 7))

    async def test_unavailable_service_is_passed_on_even_with_an_expired_entry(self):
        await self.cache(hub=AMARR, minutes=-1)
        fetch = fetcher(error=PriceUnavailable("amarr"))

        with self.assertRaises(PriceUnavailable) as raised:
            await prices.get_price("Tritanium", AMARR, fetch, now=NOW)

        self.assertEqual(
            raised.exception.message,
            "The price service did not answer for Amarr. Please try again later.",
        )

    async def test_entry_stored_by_someone_else_meanwhile_is_no_error(self):
        fetch = fetcher(Quote("Tritanium", 5, 4))

        async def racing_fetch(market, names):
            quotes = await fetch(market, names)
            await self.cache(sell=1, buy=1, minutes=-1)
            return quotes

        price = await prices.get_price("Tritanium", JITA, racing_fetch, now=NOW)

        self.assertEqual((price.sell, price.buy), (5, 4))
        self.assertEqual(await EvePricecache.objects.acount(), 1)


class SearchItemNamesTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        names = ["Raven", "Raven Navy Issue", "Caldari Navy Raven"]
        names += [f"Asteroid Ore {number:02}" for number in range(60)]
        names += ["Ore Thing"]
        InvTypes.objects.bulk_create(
            [
                InvTypes(typeID=number, typeName=name, published=True)
                for number, name in enumerate(names, start=1)
            ]
            + [InvTypes(typeID=900, typeName="Raven Prototype", published=False)]
        )

    async def test_search_prefers_names_that_start_with_the_term(self):
        self.assertEqual(
            await prices.search_item_names("rav"),
            ["Raven", "Raven Navy Issue", "Caldari Navy Raven"],
        )

    async def test_starting_names_win_over_many_containing_names(self):
        names = await prices.search_item_names("ore")

        self.assertEqual(names[0], "Ore Thing")
        self.assertEqual(len(names), 10)

    async def test_search_needs_two_characters_and_skips_unpublished_items(self):
        self.assertEqual(await prices.search_item_names("r"), [])
        self.assertEqual(await prices.search_item_names(" r "), [])
        self.assertNotIn("Raven Prototype", await prices.search_item_names("raven"))

    async def test_limit(self):
        self.assertEqual(len(await prices.search_item_names("asteroid", limit=3)), 3)
