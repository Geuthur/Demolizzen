# ESI und Killmail-Feed – Umsetzungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ESI blockiert den Bot nicht mehr, Namen werden direkt aufgelöst, und der Killmail-Feed läuft robust und prüft jede Killmail einmal.

**Architecture:** `core/openapi.py` führt ESI-Operationen in Threads aus und löst Namen per Sammelabfrage auf. `services/killmails.py` hält die Abo-Regeln. `cogs/killmail/_feed.py` kapselt den Abruf als Schritt-Funktion; der Cog verbindet Abruf, Regeln und Zustellung.

**Tech Stack:** Python ≥ 3.11, py-cord 2.8.x, Django 5.2 (async ORM), django-esi 10, aiohttp. Tests: `python runtests.py demolizzen --debug-mode`.

**Spec:** `docs/superpowers/specs/2026-11-15-esi-killmail-design.md`

## Global Constraints

- `demolizzen/services/**` importiert nie `discord`.
- Kein `.result(` einer ESI-Operation außerhalb von `OpenAPI._call`.
- Namensauflösung: Zeitlimit 15 s, höchstens 1000 IDs je Abfrage, `Unknown` wird nicht gespeichert.
- Abruf-Wartezeiten: Erfolg 0,2 s; keine neue Killmail 10 s; Fehler 1 → 2 → 4 … ≤ 300 s; `429` nach `Retry-After` (Standard `RETRY_DELAY`); Abgleich nach 30 aufeinanderfolgenden „keine neue Killmail".
- Pausen-Hinweis exakt: `Killmail feed for <#{channel_id}> is paused: I cannot send messages there.`
- Abo-Regeln unverändert gegenüber `Subscription.valid` und der Verlust-Erkennung in `Subscription.mail`.
- Jeder Commit lässt Tests grün (SQLite und `USE_MYSQL=1`); `pre-commit run --all-files` läuft durch.

## Review Focus

1. ESI lehnt die Sammelabfrage wegen einer ungültigen ID ab: die übrigen Namen werden trotzdem aufgelöst. → Aufgabe 1
1. ESI antwortet nicht: nach 15 s geht es mit `Unknown` weiter, nichts hängt. → Aufgabe 1
1. Killmail ohne `killmail_id`, mit kaputtem JSON oder mit Fehler in der Verarbeitung: übersprungen, Nummer rückt weiter. → Aufgabe 3
1. Dauerhafter Verbindungsfehler: Wartezeit wächst bis 300 s, Nummer bleibt. → Aufgabe 3
1. Zwei Abos desselben Kanals passen auf dieselbe Killmail: eine Nachricht. → Aufgabe 4

______________________________________________________________________

### Task 1: ESI in Threads, Namen direkt

**Files:** Modify `demolizzen/core/openapi.py`, `demolizzen/core/bot.py`, `demolizzen/models/eveonline.py`, `demolizzen/tests/core/test_bot.py`; Create `demolizzen/migrations/0012_delete_eveentitytask.py`, `demolizzen/tests/core/test_openapi.py`

**Interfaces – Produces:**

- `async OpenAPI._call(operation)` – `operation` ist eine argumentlose Funktion, die die ESI-Operation baut; `_call` führt `operation().result(use_etag=False)` in einem eigenen Thread-Pool (`max_workers=4`) aus

- `OpenAPI.NAME_TIMEOUT = 15`, `OpenAPI.NAME_BATCH = 1000`

- `async OpenAPI.resolve_names(ids) -> dict[int, str]` – jede angefragte ID im Ergebnis; Reihenfolge: `EveEntityCache`, dann ESI; neue Namen per `abulk_create(ignore_conflicts=True)`

- `get_or_create_character_name/corporation_name/alliance_name(id)` bleiben und nutzen `resolve_names`

- `async OpenAPI.get_region_id(system_id) -> int | None` – je System einmal aus der Datenbank, danach aus dem Speicher

- `OpenAPI.close()` – beendet den Thread-Pool

- Entfällt: `_queue_entity_task`, `_get_or_create_entity_future`, `_entity_name_worker`, `_handle_entity_error`, `_resolve_id_name`, Modell `EveEntityTask`, `Demolizzen._entity_task`

- [ ] **Step 1: Failing tests** (ESI-Client nachgebaut)

```text
call:   Operation läuft nicht im Thread der Event-Loop; ihr Ergebnis kommt zurück; ihre Ausnahme wird durchgereicht
names:  alles im Cache → kein ESI-Aufruf; fehlende IDs → genau ein Aufruf, Ergebnis gespeichert
        leere Eingabe und None/0 → {} ohne Aufruf; doppelte IDs → einmal angefragt
        404 für die Sammelabfrage → Einzelauflösung, ungültige ID wird "Unknown" und nicht gespeichert
        Zeitüberschreitung oder Serverfehler → "Unknown" für die fehlenden, nichts gespeichert, keine Ausnahme
        mehr als NAME_BATCH IDs → mehrere Aufrufe
region: zweiter Aufruf für dasselbe System ohne Datenbankabfrage; unbekanntes System → None
source: kein ".result(" außerhalb von _call; kein EveEntityTask mehr
bot:    start() legt keine Namens-Aufgabe an; close() schließt den Thread-Pool
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen, Migration erzeugen · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `fix: run ESI calls off the event loop and resolve names directly`

### Task 2: Abo-Regeln und Abo-Verwaltung

**Files:** Create `demolizzen/services/killmails.py`, `demolizzen/tests/services/test_killmails.py`

**Interfaces – Produces:**

- `killmails.SubscriptionRule` – `@dataclass(frozen=True)`: `id`, `guild_id`, `channel_id`, `group_id: int | None`, `threshold: int | None`, `losses: bool`; `group_id == 6` gilt als `None`

- `killmails.KillFacts` – `@dataclass(frozen=True)`: `killmail_id`, `total_value`, `solar_system_id`, `region_id`, `victim_corporation_id`, `victim_alliance_id`, `attacker_corporation_ids`, `attacker_alliance_ids`, `attacker_character_ids` (je `frozenset`)

- `killmails.matches(rule, facts) -> bool`, `killmails.is_loss(rule, facts) -> bool`

- `async killmails.load_rules() -> list[SubscriptionRule]`, `async killmails.rules_for_guild(guild_id)`

- `async killmails.add_subscription(guild_id, owner_user_id, channel_id, group_id, threshold, losses) -> tuple[SubscriptionRule, bool]` – wie bisher höchstens ein Abo je Kanal und `group_id`; vorhandenes wird aktualisiert

- `async killmails.remove_subscription(subscription_id) -> bool`, `remove_for_channel(channel_id) -> list[int]`, `remove_for_guild(guild_id) -> list[int]`

- [ ] **Step 1: Failing tests**

```text
matches: jede Zeile aus Subscription.valid als eigener Fall – Schwelle, global, System, Verlust (Corp/Allianz, nur mit losses),
         Angreifer-Corp, -Allianz, Region, Angreifer-Pilot, sonst False; total_value 0 umgeht die Schwelle
is_loss: Opfer-Corp oder -Allianz gleich group_id; global → False
rules:   add legt an, zweites add mit gleichem Kanal und group_id aktualisiert; remove_* geben die entfernten IDs zurück
         load_rules liefert alle; group_id 6 wird None
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `feat: killmail subscription rules in service layer`

### Task 3: Abruf als Schritt-Funktion

**Files:** Create `demolizzen/cogs/killmail/_feed.py`, `demolizzen/tests/cogs/test_killmail_feed.py`

**Interfaces – Produces:**

- `_feed.Backoff(first=1, limit=300)` mit `next() -> float` (verdoppelt) und `reset()`

- `_feed.KillmailFeed(get_session, handle, sequence_url, killmail_url, headers, timeout)` mit `SUCCESS_DELAY = 0.2`, `IDLE_DELAY = 10`, `RESYNC_AFTER = 30`; Attribute `sequence: int | None`, `processed: int`

- `async KillmailFeed.step() -> float` – ein Abruf; ruft bei gültiger Killmail `await handle(data)`; gibt die Wartezeit bis zum nächsten Schritt zurück; wirft nie (außer `CancelledError`)

- [ ] **Step 1: Failing tests** (Session nachgebaut)

```text
erste Nummer wird geholt; schlägt das fehl → Backoff
200 mit Killmail → handle aufgerufen, Nummer +1, 0.2
200 ohne killmail_id, kaputtes JSON, handle wirft → Nummer +1, 0.2, Fehler protokolliert
404 → Nummer bleibt, 10; nach 30× 404: aktueller Stand größer → Sprung dorthin, sonst bleibt die Nummer
500/502/503/504, Zeitüberschreitung, Verbindungsfehler → Nummer bleibt, 1, 2, 4 … 300; Erfolg setzt zurück
429 mit Retry-After 42 → 42; ohne Kopfzeile → RETRY_DELAY
CancelledError wird durchgereicht
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `feat: resilient killmail feed step`

### Task 4: Cog auf Feed, Regeln und einmalige Anreicherung umstellen

**Files:** Rewrite `demolizzen/cogs/killmail/killmail.py`; Modify `demolizzen/cogs/killmail/killmailmanager.py`, `demolizzen/tests/cogs/test_killmail.py`, `CHANGELOG.md`

- `Killmail.rules: dict[int, SubscriptionRule]`, geladen bei `on_ready`, gepflegt durch die Befehle und die tägliche Prüfung

- `async Killmail.handle_killmail(data)`: parsen, NPC überspringen, `KillFacts` bilden (Region über `get_region_id`), passende Regeln aktiver Guilds bestimmen, je Kanal höchstens eine Zustellung; ohne Treffer keine Anreicherung

- Zustellung als verfolgte Hintergrundaufgabe (höchstens 5 gleichzeitig): einmal anreichern (`resolve_names` für Opfer und letzten Angreifer in einem Aufruf), je Kanal senden

- Schreibrecht fehlt oder `Forbidden`: Abo pausiert, einmaliger Hinweis; `NotFound`: Abos des Kanals entfernt

- `KillmailManager.facts()`; `send_embed` postet nicht mehr in andere Kanäle; `Subscription` entfällt

- Schleifen: Abruf (`tasks.loop`, ruft `step()` und wartet), tägliche Abo-Prüfung; die 6-Stunden-Bereinigung entfällt

- Befehle `/killmail …` unverändert in Bedienung, Datenbankzugriffe über die Fachschicht

- [ ] **Step 1: Failing tests**

```text
test_matching_killmail_is_posted_once_per_channel
test_non_matching_killmail_is_not_enriched
test_npc_killmail_is_ignored
test_killmails_are_not_delivered_to_guilds_that_disabled_the_module   (bleibt)
test_names_are_resolved_in_one_call
test_missing_permission_pauses_and_notifies_once
test_feed_resumes_when_permission_returns
test_deleted_channel_loses_its_subscriptions
test_subscriptions_are_removed_even_when_module_is_disabled            (bleibt)
test_add_and_remove_commands_update_rules
test_delivery_failure_does_not_stop_other_channels
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün (SQLite und `USE_MYSQL=1`), `pre-commit run --all-files` grün
- [ ] **Step 5:** CHANGELOG, Commit `refactor: killmail feed checks and enriches each killmail once`
