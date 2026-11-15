"""Market prices of EVE Online items, cached per trade hub."""

# Standard Library
from dataclasses import dataclass
from datetime import timedelta

# Django
from django.utils import timezone

# Demolizzen
from demolizzen.models import EvePricecache, InvTypes
from demolizzen.services.errors import PriceNotFound, PriceUnavailable

# A fetched price is reused for this long.
CACHE_SECONDS = 1800
MIN_SEARCH_LENGTH = 2


@dataclass(frozen=True)
class Tradehub:
    """A market. ``key`` is the name the price service knows it by."""

    key: str
    title: str
    station: str


# Only markets the price service knows: it answers 400 for Rens and Hek.
TRADEHUBS = {
    hub.key: hub
    for hub in (
        Tradehub("jita", "Jita", "Jita IV - Moon 4 - Caldari Navy Assembly Plant"),
        Tradehub("amarr", "Amarr", "Amarr VIII (Oris) - Emperor Family Academy"),
        Tradehub(
            "dodixie",
            "Dodixie",
            "Dodixie IX - Moon 20 - Federation Navy Assembly Plant",
        ),
    )
}
DEFAULT_TRADEHUB = TRADEHUBS["jita"]


def tradehub(name: str | None) -> Tradehub:
    """Return the trade hub of that name; Jita when it is unknown or missing."""
    return TRADEHUBS.get((name or "").strip().lower(), DEFAULT_TRADEHUB)


@dataclass(frozen=True)
class Quote:
    """What the price service says about one item: lowest sell, highest buy."""

    item_name: str
    sell: int
    buy: int


@dataclass(frozen=True)
class Price:
    item_name: str
    hub: Tradehub
    sell: int
    buy: int
    cached: bool


def _pick(quotes: list[Quote], item_name: str) -> Quote | None:
    wanted = item_name.casefold()
    for quote in quotes:
        if quote.item_name.casefold() == wanted:
            return quote
    return quotes[0] if quotes else None


async def get_price(item_name: str, hub: Tradehub, fetch, now=None) -> Price:
    """Return the price of an item in a trade hub.

    A cached price that has not expired is used as it is. Otherwise ``fetch``
    asks the price service – ``await fetch(market, names)`` returns a list of
    :class:`Quote` or raises :class:`PriceUnavailable` – and the answer is
    cached. An item nobody sells or buys raises :class:`PriceNotFound`.
    """
    now = now or timezone.now()
    name = item_name.strip()
    if not name:
        raise PriceNotFound(item_name, hub.title)

    entry = await EvePricecache.objects.filter(
        item_name__iexact=name, tradehub=hub.key
    ).afirst()
    if entry is not None and entry.expiration > now:
        return Price(entry.item_name, hub, entry.price, entry.buy, cached=True)

    try:
        quotes = await fetch(hub.key, [name])
    except PriceUnavailable as error:
        raise PriceUnavailable(hub.title) from error

    quote = _pick(quotes, name)
    if quote is None or (quote.sell <= 0 and quote.buy <= 0):
        raise PriceNotFound(name, hub.title)

    values = {
        "price": quote.sell,
        "buy": quote.buy,
        "expiration": now + timedelta(seconds=CACHE_SECONDS),
    }
    stored_name = quote.item_name[:255]
    await EvePricecache.objects.aupdate_or_create(
        item_name__iexact=stored_name,
        tradehub=hub.key,
        defaults=values,
        create_defaults={"item_name": stored_name, **values},
    )
    return Price(stored_name, hub, quote.sell, quote.buy, cached=False)


async def search_item_names(term: str, limit: int = 10) -> list[str]:
    """Names of published items matching ``term``: those starting with it
    first, then those containing it."""
    term = term.strip()
    if len(term) < MIN_SEARCH_LENGTH:
        return []

    published = InvTypes.objects.filter(published=True).order_by("typeName")
    names = [
        name
        async for name in published.filter(typeName__istartswith=term).values_list(
            "typeName", flat=True
        )[:limit]
    ]
    if len(names) < limit:
        names += [
            name
            async for name in published.filter(typeName__icontains=term)
            .exclude(typeName__istartswith=term)
            .values_list("typeName", flat=True)[: limit - len(names)]
        ]
    return names
