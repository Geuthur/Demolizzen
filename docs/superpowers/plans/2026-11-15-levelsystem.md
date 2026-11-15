# Levelsystem – Umsetzungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Das Levelsystem blockiert den Bot nicht mehr, verliert keine XP und liegt mit seinen Regeln in der Fachschicht; Einstellungen im `/panel`.

**Architecture:** `services/levels.py` hält Formeln und XP-Buchung. `cogs/levelsystem/_cards.py` lädt Bilder asynchron und zeichnet Karten als reine Funktionen, die der Cog in einem Thread ausführt.

**Tech Stack:** Python ≥ 3.11, py-cord 2.8.x, Django 5.2 (async ORM), aiohttp, Pillow. Tests: `python runtests.py demolizzen --debug-mode`.

**Spec:** `docs/superpowers/specs/2026-11-15-levelsystem-design.md`

## Global Constraints

- `demolizzen/services/**` importiert nie `discord`; kein Modul unter `demolizzen/cogs/levelsystem` importiert `requests`.
- Level-Formel unverändert: Level `L` ist die kleinste ganze Zahl mit `xp < 50·L·(L+1)` bei `XP_PER_LEVEL = 100`; `xp_for_level(L) = 50·(L−1)·L`.
- Download: Zeitlimit 10 s, höchstens 8 MB; Zwischenspeicher höchstens 64 Einträge.
- Kartenmaße: Level-Up 900×270, Rang 1050×300, PNG.
- Bot-Texte bleiben. Jeder Commit lässt Tests grün (SQLite und `USE_MYSQL=1`); `pre-commit run --all-files` läuft durch.

## Review Focus

1. Zwei Nachrichten desselben Mitglieds direkt nacheinander: beide XP-Mengen landen im Profil. → Aufgabe 1
1. Bild-Server antwortet nicht, liefert einen Fehler oder mehr als 8 MB: keine Karte, kein Absturz, XP gebucht. → Aufgaben 2 und 3
1. Nachricht eines Mitglieds ohne Profil in einem unregistrierten Server: Profil entsteht, XP gebucht. → Aufgabe 1
1. Level-Up ohne Hauptkanal und ohne Systemkanal oder ohne Schreibrecht: nichts gesendet, kein Fehler. → Aufgabe 3
1. `/rank` für Bot oder Mitglied ohne Profil: klare Meldung. → Aufgabe 3

______________________________________________________________________

### Task 1: Fachschicht `levels`

**Files:** Create `demolizzen/services/levels.py`, `demolizzen/tests/services/test_levels.py`

**Interfaces – Produces:**

- `levels.level_for(xp: int) -> int`, `levels.xp_for_level(level: int) -> int`

- `levels.Progress(level, into_level, needed, percent)`; `levels.progress(xp) -> Progress` – `needed = XP_PER_LEVEL × level`, `percent = int(into_level / needed × 100)`

- `levels.message_xp(word_count: int, rng=random) -> int` – `0`, wenn der Chancen-Wurf nicht trifft; sonst nach `XP_TYPE` (`normal`, `words`, `ranrange`)

- `levels.XpResult(experience, level, previous_level, leveled_up)`

- `async levels.add_xp(guild_id, guild_name, user_id, user_name, amount) -> XpResult` – bucht per `F()`-Update, legt Guild/Profil nur bei Bedarf an, gleicht den gespeicherten Namen an, setzt `level`, wenn es sich ändert; `leveled_up`, wenn das neue Level über dem gespeicherten liegt

- `levels.CardData(user_name, experience, level, rank, background, border, xp_colour, blur)`; `async levels.get_card_data(guild_id, user_id) -> CardData | None` – legt fehlende `UserSettings` an; `rank` = Platz nach Level, dann XP

- `async levels.leaderboard(guild_id) -> list[tuple[str, int, int]]` (Name, Level, XP)

- `levels.Announcement(enabled: bool, channel_id: int | None)`; `async levels.get_announcement(guild_id) -> Announcement`; `async levels.set_announcements(guild_id, enabled: bool) -> None`

- [ ] **Step 1: Failing tests**

```text
formula: level_for 0→1, 99→1, 100→2, 299→2, 300→3, 600→4; xp_for_level 1→0, 2→100, 3→300
         progress(150) → Progress(2, 50, 200, 25)
message_xp: Chance trifft nicht → 0; normal → XP_NORMAL_AMOUNT; words → Wortzahl; ranrange → Wert des Würfels
add_xp:  neues Mitglied in unregistrierter Guild → Profil, XP gebucht, Level 1
         zwei Buchungen nacheinander auf veraltetem Stand → Summe stimmt
         99 → +1 → Level 2, leveled_up; weiteres +1 → nicht leveled_up; Name wird angeglichen
card:    ohne Profil → None; legt UserSettings an; rank nach Level/XP
leaderboard: Reihenfolge nach Level, dann XP; nur diese Guild
announcement: Standard an; abschalten; Kanal aus main_channel_id
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `feat: levels service with atomic xp bookings`

### Task 2: Bilder laden und Karten zeichnen

**Files:** Create `demolizzen/cogs/levelsystem/_cards.py`, `demolizzen/tests/cogs/test_level_cards.py`

**Interfaces – Produces:**

- `_cards.AssetError(Exception)`

- `_cards.AssetLoader(get_session)` mit `TIMEOUT = 10`, `MAX_BYTES = 8 * 1024 * 1024`, `CACHE_SIZE = 64`; `async load(source: str, cache: bool = True) -> bytes` – `http(s)` über die aiohttp-Session mit Zeitlimit, sonst lokale Datei im Thread; `AssetError` bei Status ≥ 400, Zeitüberschreitung, Verbindungsfehler, zu großem Bild, fehlender Session oder Datei

- `_cards.render_level_up_card(background, shade, avatar, border, *, name, level, xp_into_level) -> BytesIO`

- `_cards.render_rank_card(background, avatar, border, *, name, experience, level, into_level, needed, percent, colour, blur, rank) -> BytesIO`

- [ ] **Step 1: Failing tests** (Session nachgebaut, Bilder im Test mit Pillow erzeugt)

```text
loader: lädt Bytes; zweiter Aufruf ohne neue Anfrage; cache=False fragt erneut
        Status 404, Zeitüberschreitung, ClientError, > MAX_BYTES, keine Session → AssetError
        Zeitlimit wird an die Session übergeben; lokale Datei wird gelesen; Cache verdrängt den ältesten Eintrag
cards:  beide Funktionen liefern ein PNG der geforderten Größe; kaputte Bytes → Ausnahme
```

- [ ] **Step 2:** → FAIL · **Step 3:** Zeichencode aus `_functions.py` übernehmen · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `feat: non-blocking asset loader and pure level card rendering`

### Task 3: Cog, Einstellungsseite, Aufräumen

**Files:** Rewrite `demolizzen/cogs/levelsystem/levelsystem.py`, `demolizzen/cogs/levelsystem/__init__.py`; Create `demolizzen/cogs/levelsystem/_settings_page.py`, `demolizzen/tests/cogs/test_levelsystem.py`; Delete `demolizzen/cogs/levelsystem/_functions.py`; Modify `demolizzen/services/guilds.py` (`get_main_channel`), `CHANGELOG.md`

- `on_message`: Bot/DM → nichts; `levels.message_xp` → bei `0` Ende ohne Datenbank; `levels.add_xp`; bei `leveled_up` Ankündigung

- Ankündigung und `/rank`: Daten aus der Fachschicht, Bilder über `AssetLoader`, Zeichnen über `asyncio.to_thread`; jeder Fehler wird protokolliert und beendet nur die Karte

- `/leaderboard` über `levels.leaderboard`

- `on_guild_channel_delete`: wie bisher, über `guilds.get_main_channel` / `set_main_channel`

- Einstellungsseite `levelsystem`: `Level up posts: On/Off`, Kanalauswahl `Level up channel`, `Use system channel`, `Back`

- Kein `/levelsystem_config`

- [ ] **Step 1: Failing tests**

```text
test_bot_and_dm_messages_earn_nothing
test_message_without_xp_touches_no_database            assertNumQueries(0)
test_message_adds_xp_and_creates_profile
test_level_up_posts_card_to_main_channel
test_level_up_is_silent_when_announcements_are_off
test_level_up_without_channel_or_permission_is_silent
test_failed_asset_download_keeps_the_xp
test_rank_sends_card
test_rank_for_unknown_member_tells_user
test_leaderboard_lists_members_in_order
test_settings_page_toggles_announcements_and_sets_channel
test_levelsystem_has_no_config_command_and_registers_page
test_levelsystem_does_not_import_requests
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün (SQLite und `USE_MYSQL=1`), `pre-commit run --all-files` grün
- [ ] **Step 5:** CHANGELOG, Commit `refactor: level system on service layer with non-blocking cards`
