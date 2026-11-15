# EVE-Online-Cog und Preisabfrage – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/eve price` nutzt den Zwischenspeicher, funktioniert je Handelsplatz und meldet Störungen klar.

**Architecture:** Preislogik in `services/prices.py` (kein discord, kein aiohttp); der Abruf wird als Funktion hineingereicht. `cogs/eveonline/_appraisal.py` spricht mit dem Preisdienst. Der Cog verbindet beides.

**Tech Stack:** py-cord 2.8, Django 5.2 (async ORM), aiohttp.

**Spec:** `docs/superpowers/specs/2026-11-15-eve-prices-design.md`

## Global Constraints

- Zwischenspeicher 1800 s; Zeitlimit Preisdienst 10 s; Zeitlimit Status 10 s; höchstens 10 Vorschläge
- Meldungen wörtlich: `No market price found for **<item>** in <hub>.` und `The price service did not answer for <hub>. Please try again later.`
- Tests: `python runtests.py demolizzen --debug-mode`, auch mit `USE_MYSQL=1`; `pre-commit run --all-files`

## Review Focus

1. Dasselbe Item für zwei Handelsplätze: beide Preise gespeichert, keiner überschreibt den anderen. → Aufgabe 1
1. Itemname in anderer Schreibweise: Treffer im Zwischenspeicher, kein zweiter Eintrag. → Aufgabe 1
1. Preisdienst liefert 200 mit unerwartetem Aufbau: Störungsmeldung, kein Absturz. → Aufgabe 2
1. Preisdienst liefert das Item mit Preisen 0: Meldung „kein Preis“, nichts gespeichert. → Aufgabe 1
1. Abgelaufener Eintrag und Störung: Störungsmeldung, der alte Preis wird nicht gezeigt. → Aufgabe 1

______________________________________________________________________

### Task 1: Preislogik und Zwischenspeicher

**Files:** Create `demolizzen/services/prices.py`, `demolizzen/migrations/0013_price_cache_per_tradehub.py`, `demolizzen/tests/services/test_prices.py`; Modify `demolizzen/services/errors.py`, `demolizzen/models/eveonline.py`

**Interfaces – Produces:**

- `Tradehub(key: str, title: str, station: str)`; `TRADEHUBS: dict[str, Tradehub]` (jita, amarr, dodixie, rens, hek); `tradehub(name: str | None) -> Tradehub`
- `Quote(item_name: str, sell: int, buy: int)`; `Price(item_name: str, hub: Tradehub, sell: int, buy: int, cached: bool)`
- `async get_price(item_name: str, hub: Tradehub, fetch, now=None) -> Price`; `fetch` ist `async (market: str, names: list[str]) -> list[Quote]`
- `async search_item_names(term: str, limit: int = 10) -> list[str]`
- `PriceError(ServiceError)` mit `.message`; `PriceNotFound`, `PriceUnavailable`

- [ ] **Step 1: Failing tests**

```text
test_tradehub_lookup_ignores_case_and_defaults_to_jita
test_fresh_cache_entry_is_used_without_asking
test_missing_entry_is_fetched_and_stored
test_expired_entry_is_fetched_again_and_updated
test_same_item_in_two_tradehubs
test_item_name_case_does_not_matter
test_unknown_item_is_not_found_and_not_stored
test_item_without_orders_is_not_found
test_only_buy_orders_is_a_price
test_unavailable_service_is_passed_on_even_with_an_expired_entry
test_search_prefers_names_that_start_with_the_term
test_search_needs_two_characters_and_skips_unpublished_items
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen, Migration · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `feat: price lookup with per-tradehub cache in service layer`

### Task 2: Anbindung an den Preisdienst

**Files:** Create `demolizzen/cogs/eveonline/_appraisal.py`, `demolizzen/tests/cogs/test_appraisal_client.py`; Delete `demolizzen/utils/pricehandler.py`

**Interfaces – Consumes:** `Quote`, `PriceUnavailable` · **Produces:** `AppraisalClient(get_session, headers=None)`, `async quotes(market: str, names: list[str]) -> list[Quote]`, `URL`, `TIMEOUT` (10 s)

- [ ] **Step 1: Failing tests**

```text
test_quotes_are_read_from_the_answer
test_request_names_market_and_items
test_error_status_is_unavailable
test_timeout_and_connection_error_are_unavailable
test_unreadable_answer_is_unavailable
test_missing_session_is_unavailable
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `feat: appraisal client with timeout and clear failures`

### Task 3: Cog

**Files:** Rewrite `demolizzen/cogs/eveonline/eveonline.py`; Modify `demolizzen/utils/autocomplete.py`, `CHANGELOG.md`; Create `demolizzen/tests/cogs/test_eveonline.py`

- `/eve price`: `defer`, `prices.get_price(...)` mit `AppraisalClient.quotes`, Embed wie bisher (Überschrift mit Stationsname, Felder Sell und Buy), Fehlermeldungen aus `PriceError.message`
- `/eve status`: Zeitlimit 10 s, `Server Offline 🔴`
- `PriceListModal` entfällt; `search_items` nutzt `prices.search_item_names`

- [ ] **Step 1: Failing tests**

```text
test_price_shows_sell_and_buy
test_price_defers_before_asking
test_price_without_tradehub_uses_jita
test_unknown_item_gets_a_clear_message
test_unavailable_service_gets_a_clear_message
test_status_online
test_status_offline
test_status_timeout_counts_as_offline
test_price_list_modal_is_gone
test_autocomplete_returns_matching_names
test_autocomplete_survives_a_database_error
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün (SQLite und `USE_MYSQL=1`), `pre-commit run --all-files` grün
- [ ] **Step 5:** CHANGELOG, Commit `refactor: eve online cog on price service with clear failures`
