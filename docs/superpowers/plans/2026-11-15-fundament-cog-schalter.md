# Fundament, Cog-Schalter und Panel – Umsetzungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Der Bot wird testbar, Fachlogik wandert in eine discord-freie Schicht, und Guild-Admins schalten Cogs pro Guild über `/panel`.

**Architecture:** `demolizzen/services/` enthält Fachlogik auf Basis des asynchronen Django-ORM und importiert nie `discord`. Cogs erben von `BaseCog`, das vor jedem Befehl und Event den Schalter der Guild prüft. Ein Verzeichnis (`registry`) beschreibt die angebotenen Cogs; Schalter und Panel lesen nur daraus.

**Tech Stack:** Python ≥ 3.10, py-cord 2.8.x (nicht discord.py), Django 5.2 (nur ORM, async-Methoden `aget`/`acreate`/…), Tests mit Django-Testrunner (`python runtests.py demolizzen`) gegen SQLite.

**Spec:** `docs/superpowers/specs/2026-11-15-fundament-cog-schalter-design.md`

## Global Constraints

- `demolizzen/services/**` und `demolizzen/core/registry.py` importieren nie `discord`.
- Keine Schema-Änderung, keine neue Migration. Speicher sind `GuildSettings.disabled_cogs` und `GuildSettings.enabled_cogs` (JSON-Listen von Schlüsseln, dürfen `null` sein).
- Bestehende Guilds: leere/`null`-Felder bedeuten „alles aktiv".
- Nicht abschaltbar: genau `core`, `owner`, `guild`, `panel`.
- Cog-Schlüssel = Name des Erweiterungsordners unter `demolizzen/cogs/` (`banksystem`, `ticket`, …).
- Abhängigkeiten: `economy`, `shop`, `games` brauchen `banksystem`. Ohne `cascade` verweigert die Fachschicht, mit `cascade=True` schaltet sie alle Betroffenen gemeinsam.
- Hinweistext exakt: `This module is disabled on this server.`
- Bot-Texte englisch. Zwischenspeicher-Frist 60 s.
- Nach jeder Aufgabe: `python runtests.py demolizzen` grün, Bot startbar.
- Commits auf `development`, mit den Attributionszeilen der Sitzung.

### py-cord-Eigenheiten (an 2.8.1 geprüft)

- Kein `setup_hook`. Ressourcen, die eine laufende Loop brauchen, entstehen in einem überschriebenen `async def start()`; aufgeräumt wird in `close()`.
- `Client.__init__` besorgt `self.loop` selbst; nicht überschreiben. `run()` ruft `start()` und danach `close()`.
- `load_extensions(*names)` existiert bereits auf dem Bot – der Name ist belegt.
- Slash-Befehle prüfen `Cog.cog_check(ctx)` in `ApplicationCommand.can_run`, **vor** `cog_before_invoke`. Gibt der Check `False` zurück, entsteht ein `discord.errors.CheckFailure`, den `on_application_command_error` stumm verschluckt. Nur `discord.ext.commands.CheckFailure` wird dem Nutzer als Text gezeigt – `CogDisabled` muss davon erben und im Check **geworfen** werden.
- Listener werden über das Attribut `__cog_listener__` erkannt, das `commands.Cog.listener()` auf die Funktion setzt; ein eigener Dekorator muss die umhüllte Funktion durch `commands.Cog.listener(name)` schicken.
- UI: `discord.ui.View(timeout=…, disable_on_timeout=True)`, `discord.ui.string_select`, `discord.ui.button`; Callback-Signatur `(self, item, interaction)`.

## Review Focus

1. Befehl oder Event ohne Guild (DM): Schalter lässt durch, kein Fehler. → Aufgabe 5
2. Guild ohne `GuildProfile`/`GuildSettings`-Zeile oder mit `null`-Feldern: gilt als „alles aktiv"; Lesen legt keine Zeilen an. → Aufgabe 4
3. Unbekannte Schlüssel oder Müll in den JSON-Feldern (entferntes Cog, kein Listen-Typ): werden ignoriert, Panel und Schalter laufen weiter. → Aufgabe 4
4. Zwei Admins schalten kurz nacheinander verschiedene Cogs: beide Änderungen bleiben erhalten (kein Überschreiben aus altem Zwischenspeicher). → Aufgabe 4
5. Panel-Nachricht wird von jemand anderem bedient oder vom Aufrufer, der inzwischen die Berechtigung verloren hat: Klick wird abgewiesen, nichts geschaltet. → Aufgabe 6

## Dateien

| Datei | Aufgabe | Verantwortung |
|---|---|---|
| `testenv/settings.py`, `tox.ini`, `demolizzen/config.py` | 1 | DB-Schalter, Cog `test` entfernen |
| `demolizzen/tests/helpers.py` | 1 | Nachbauten für Guild, Member, ctx, Interaction |
| `demolizzen/core/bot.py`, `demolizzen/launch.py` | 2 | Start entflochten |
| `demolizzen/services/__init__.py`, `services/errors.py`, `services/guilds.py` | 3 | Guild- und Mitglieder-Logik |
| `demolizzen/cogs/guild/guild.py` | 3 | dünnes Pilot-Cog |
| `demolizzen/core/registry.py`, `services/cog_settings.py` | 4 | Verzeichnis und Schalter-Logik |
| `demolizzen/core/errors.py`, `demolizzen/core/cog.py`, alle geladenen Cogs | 5 | `BaseCog`, `CogDisabled`, `guild_listener` |
| `demolizzen/cogs/panel/{__init__,panel,_view}.py` | 6 | `/panel` |
| `demolizzen/tests/{core,services,cogs}/…` | 1–6 | Tests je Aufgabe |

---

### Task 1: Testgerüst und DB-Schalter

**Files:**
- Modify: `testenv/settings.py`, `tox.ini`, `demolizzen/config.py` (`"test"` aus `PRELOAD_EXTENSIONS`), `CHANGELOG.md`
- Create: `demolizzen/tests/helpers.py`, `demolizzen/tests/core/__init__.py`, `demolizzen/tests/services/__init__.py`, `demolizzen/tests/cogs/__init__.py`, `demolizzen/tests/test_settings.py`

**Interfaces – Produces:**
- `helpers.make_guild(guild_id: int = 1, name: str = "Test Guild", members: list | None = None) -> MagicMock` (spec `discord.Guild`; `.id`, `.name`, `.members`, `.owner`)
- `helpers.make_member(user_id: int = 10, name: str = "tester", *, bot: bool = False, manage_guild: bool = False, guild=None) -> MagicMock` (spec `discord.Member`; `.guild_permissions.manage_guild`)
- `helpers.make_ctx(guild=None, author=None) -> MagicMock` (`.respond`, `.defer`, `.followup.send` als `AsyncMock`; `.guild`, `.author`, `.user`; `guild=None` bleibt `None` für DM-Fälle)
- `helpers.make_interaction(guild=None, user=None) -> MagicMock` (`.response.edit_message`, `.response.send_message` als `AsyncMock`)
- `testenv.settings.use_mysql(value: str | None) -> bool`

- [ ] **Step 1: Failing test** `demolizzen/tests/test_settings.py`

```python
class UseMysqlTest(SimpleTestCase):
    def test_values(self):
        for value in ("1", "true", "TRUE", "yes"):
            self.assertTrue(use_mysql(value))
        for value in (None, "", "0", "false", "no"):
            self.assertFalse(use_mysql(value))
```

- [ ] **Step 2:** `python runtests.py demolizzen.tests.test_settings` → FAIL (ImportError `use_mysql`)
- [ ] **Step 3:** `use_mysql` in `testenv/settings.py` einführen und `DATABASES` damit aus `os.environ.get("USE_MYSQL")` wählen. In `tox.ini` in **beiden** `set_env`-Blöcken (`[testenv]` neu, `[testenv:demolizzen-latest]` ergänzen) `USE_MYSQL = {env:USE_MYSQL:1}` setzen, damit tox/CI weiter MySQL nutzt.
- [ ] **Step 4:** `"test"` aus `PRELOAD_EXTENSIONS` entfernen; `helpers.py` und die drei Test-Pakete anlegen.
- [ ] **Step 5:** `python runtests.py demolizzen` → OK, ohne `USE_MYSQL` in der Umgebung, kein `ExtensionNotFound` im Log.
- [ ] **Step 6:** CHANGELOG (`Changed`), Commit `test: add test scaffold and fix USE_MYSQL switch`

### Task 2: Bot-Start entflechten

**Files:**
- Modify: `demolizzen/core/bot.py:26-66`, `demolizzen/launch.py`
- Create: `demolizzen/tests/core/test_bot.py`; Delete: `demolizzen/tests/test_bot.py`

**Interfaces – Produces:**
- `Demolizzen.__init__(**kwargs)`: nur Intents, `command_prefix="$"`, `config`, `token`, `req_perms`, `preload_ext`, `counter`, `logger`, `launch_time`; `self.session = None`, `self.esi_data = None`, `self._entity_task = None`. Kein Laden von Cogs, kein Netzwerk, kein `sys.exit`.
- `Demolizzen.load_preload_extensions() -> dict[str, Exception | None]` – lädt `demolizzen.cogs.<ext>` je Eintrag, protokolliert Fehler, bricht nicht ab; Konsolenausgabe wie bisher.
- `async Demolizzen.start(token: str | None = None, *, reconnect: bool = True)` – wirft `RuntimeError("Token must be set in order to login.")` ohne Token; erzeugt `aiohttp.ClientSession()`, `OpenAPI(session)`, startet `_entity_name_worker` als Task; dann `super().start(...)`.
- `async Demolizzen.close()` – bricht `_entity_task` ab, schließt die Session, dann `super().close()`; mehrfach aufrufbar.
- `launch.run_bot()`: `bot = Demolizzen(); bot.load_preload_extensions(); bot.run()`.

- [ ] **Step 1: Failing tests** (`SimpleTestCase`, `aiohttp.ClientSession` und `demolizzen.core.bot.OpenAPI` gepatcht)

```python
def test_init_has_no_side_effects(self):
    with patch("aiohttp.ClientSession") as session, patch.object(Demolizzen, "load_extension") as load:
        bot = Demolizzen()
    session.assert_not_called(); load.assert_not_called()
    self.assertIsNone(bot.session); self.assertIsNone(bot.esi_data)

def test_load_preload_extensions_reports_failures(self):
    bot = Demolizzen(); bot.preload_ext = ["core", "does_not_exist"]
    result = bot.load_preload_extensions()
    self.assertIsNone(result["core"])
    self.assertIsInstance(result["does_not_exist"], Exception)

async def test_start_without_token_raises(self):
    bot = Demolizzen(); bot.token = None
    with self.assertRaisesMessage(RuntimeError, "Token must be set"):
        await bot.start()

async def test_start_creates_resources_then_connects(self):
    # patch discord.ext.commands.Bot.start (AsyncMock), ClientSession, OpenAPI
    await bot.start("tok")
    self.assertIsNotNone(bot.session); self.assertIsNotNone(bot.esi_data)
    parent_start.assert_awaited_once()

async def test_close_is_idempotent(self): ...  # zweimal close(), Session.close einmal awaited
```

- [ ] **Step 2:** Tests laufen lassen → FAIL
- [ ] **Step 3:** Umsetzen wie in Interfaces. `self.loop = asyncio.get_event_loop()` und `self.bot_users`, `self.core_dir` entfallen, sofern `grep` keine Nutzer findet.
- [ ] **Step 4:** `python runtests.py demolizzen` → OK
- [ ] **Step 5:** CHANGELOG, Commit `refactor: separate bot construction from startup`

### Task 3: Guild-Fachlogik und Pilot-Cog

**Files:**
- Create: `demolizzen/services/__init__.py`, `demolizzen/services/errors.py`, `demolizzen/services/guilds.py`, `demolizzen/tests/services/test_guilds.py`, `demolizzen/tests/cogs/test_guild.py`
- Modify: `demolizzen/cogs/guild/guild.py` (`check`, alle vier Listener), `demolizzen/core/bot.py` (`on_ready`: Umbenennung über Service)

**Interfaces – Produces** (`demolizzen/services/guilds.py`, alles `async`):
- `ensure_guild(guild_id: int, name: str) -> tuple[GuildProfile, bool]` – legt Profil und die Zeilen aus `GuildProfile.create_settings()` an; zweiter Wert = neu angelegt
- `rename_guild(guild_id: int, name: str) -> bool` – `True` nur bei tatsächlicher Änderung; unbekannte Guild → `False`
- `remove_guild(guild_id: int) -> bool`
- `remove_missing_guilds(present_ids: Iterable[int]) -> list[int]` – löscht Profile, die nicht in `present_ids` sind, gibt deren IDs zurück
- `ensure_members(guild_id: int, members: Iterable[tuple[int, str]]) -> int` – legt fehlende `UserProfile` samt `UserSettings` (Standardwerte aus `config`, `blur=5`) per `abulk_create` an; Rückgabe = Anzahl neuer Profile; wirft `GuildNotRegistered`, wenn das Profil fehlt
- `rename_member(guild_id: int, user_id: int, name: str) -> bool`
- `services/errors.py`: `ServiceError(Exception)`, `GuildNotRegistered(ServiceError)`, `UnknownCog(ServiceError)`, `CogNotToggleable(ServiceError)`

Das Cog filtert Bots heraus und reicht dieselben Namen weiter wie heute (`display_name` im Zeitabgleich, `name` beim Beitritt und bei Mitglieds-Updates). Der bisherige Vergleich `before.name is not after.name` wird zu `!=`.

- [ ] **Step 1: Failing tests** `test_guilds.py` (`TestCase`, async-Methoden)

```python
async def test_ensure_guild_creates_profile_and_settings(self):
    profile, created = await guilds.ensure_guild(1, "Alpha")
    self.assertTrue(created)
    self.assertTrue(await GuildSettings.objects.filter(guild_id=1).aexists())
    _, created = await guilds.ensure_guild(1, "Alpha")
    self.assertFalse(created)

async def test_rename_guild(self):       # True bei Änderung, False bei gleichem Namen, False bei unbekannter Guild
async def test_remove_missing_guilds(self):  # Guilds 1,2,3; present=[1,3] → [2]; Profil 2 weg, UserProfile der Guild 2 weg
async def test_ensure_members_is_idempotent(self):
    await guilds.ensure_guild(1, "Alpha")
    self.assertEqual(await guilds.ensure_members(1, [(10, "a"), (11, "b")]), 2)
    self.assertEqual(await guilds.ensure_members(1, [(10, "a"), (12, "c")]), 1)
    self.assertEqual(await UserSettings.objects.filter(user__guild_id=1).acount(), 3)
async def test_ensure_members_unknown_guild_raises(self):  # GuildNotRegistered
async def test_rename_member(self):
```

- [ ] **Step 2:** → FAIL (Modul fehlt)
- [ ] **Step 3:** `services/errors.py` und `services/guilds.py` umsetzen
- [ ] **Step 4:** → PASS
- [ ] **Step 5: Failing tests** `test_guild.py` – Cog mit `MagicMock`-Bot, `check_guild.start` gepatcht:

```python
async def test_on_guild_join_registers_guild_and_humans(self):
    guild = make_guild(1, "Alpha", members=[make_member(10, "a"), make_member(11, "bot", bot=True)])
    await cog.on_guild_join(guild)
    self.assertEqual(await UserProfile.objects.filter(guild_id=1).acount(), 1)
async def test_on_guild_remove_deletes_profile(self): ...
async def test_check_removes_guilds_the_bot_left(self): ...
```

- [ ] **Step 6:** Cog auf Service-Aufrufe umstellen; danach enthält `guild.py` kein `.objects.` mehr (`grep -c "\.objects\." demolizzen/cogs/guild/guild.py` → 0). `bot.on_ready` nutzt `rename_guild`.
- [ ] **Step 7:** `python runtests.py demolizzen` → OK
- [ ] **Step 8:** CHANGELOG, Commit `refactor: move guild logic into service layer`

### Task 4: Verzeichnis und Schalter-Logik

**Files:**
- Create: `demolizzen/core/registry.py`, `demolizzen/services/cog_settings.py`, `demolizzen/tests/core/test_registry.py`, `demolizzen/tests/services/test_cog_settings.py`

**Interfaces – Consumes:** `services.errors.*`, `services.guilds.ensure_guild`

**Interfaces – Produces:**
- `registry.CogInfo` – `@dataclass(frozen=True)`: `key: str`, `title: str`, `description: str`, `toggleable: bool = True`, `default_enabled: bool = True`, `requires: tuple[str, ...] = ()`
- `registry.requirements(key: str) -> list[str]` (alle benötigten Cogs, transitiv), `registry.dependents(key: str) -> list[str]` (alle abhängigen Cogs, transitiv), beide in Verzeichnis-Reihenfolge
- `services.errors.DependencyConflict(ServiceError)` mit `.key: str`, `.enabled: bool`, `.affected: list[str]`
- `registry.REGISTRY: dict[str, CogInfo]` mit genau diesen Schlüsseln in dieser Reihenfolge: `core`, `owner`, `guild`, `panel` (alle `toggleable=False`), dann `admin`, `general`, `commands`, `levelsystem`, `banksystem`, `economy`, `shop`, `games`, `eveonline`, `killmail`, `ticket`. Titel aus dem bisherigen `self.title` des jeweiligen Cogs, Beschreibung ein englischer Satz.
- `registry.get(key: str) -> CogInfo` (wirft `UnknownCog`), `registry.toggleable() -> list[CogInfo]`
- `cog_settings.CACHE_TTL_SECONDS = 60`
- `async cog_settings.is_enabled(guild_id: int, key: str) -> bool` – unbekannter Schlüssel → `UnknownCog`; nicht abschaltbare Cogs immer `True`
- `async cog_settings.get_states(guild_id: int) -> dict[str, bool]` – nur abschaltbare Cogs, Reihenfolge des Verzeichnisses
- `async cog_settings.set_enabled(guild_id: int, key: str, enabled: bool, *, cascade: bool = False) -> list[str]` – gibt alle geschalteten Schlüssel zurück (`key` zuerst); wirft `UnknownCog`, `CogNotToggleable`, `GuildNotRegistered`; beim Abschalten mit aktiven Abhängigen bzw. Anschalten mit abgeschalteten Voraussetzungen ohne `cascade` → `DependencyConflict` und nichts wird geändert; liest die Zeile innerhalb einer Transaktion frisch (`select_for_update`), schreibt beide Listen, verwirft den Zwischenspeicher der Guild
- `async cog_settings.enabled_guild_ids(key: str, guild_ids: Iterable[int]) -> set[int]`
- `cog_settings.invalidate(guild_id: int | None = None) -> None`

Regel: aktiv = (`default_enabled` und nicht in `disabled_cogs`) oder in `enabled_cogs`. `set_enabled` hält die Listen minimal: bei Standard-aktiven Cogs steht der Schlüssel nur beim Abschalten in `disabled_cogs`, sonst in keiner Liste. Zeitquelle des Zwischenspeichers: `time.monotonic`, im Modul patchbar.

- [ ] **Step 1: Failing tests**

```python
# test_registry.py
def test_fixed_cogs_are_not_toggleable(self):
    self.assertEqual({k for k, c in REGISTRY.items() if not c.toggleable}, {"core", "owner", "guild", "panel"})
def test_registry_matches_preload_extensions(self):
    self.assertEqual(set(REGISTRY) - {"panel"}, set(config.PRELOAD_EXTENSIONS) - {"panel"})
def test_get_unknown_raises(self): ...  # UnknownCog

# test_cog_settings.py  (setUp: cog_settings.invalidate())
async def test_unregistered_guild_is_all_enabled_and_creates_no_rows(self):
    self.assertTrue(await cog_settings.is_enabled(99, "ticket"))
    self.assertEqual(await GuildProfile.objects.acount(), 0)
async def test_null_fields_mean_enabled(self): ...
async def test_disable_and_enable_roundtrip(self):
    await guilds.ensure_guild(1, "Alpha")
    await cog_settings.set_enabled(1, "games", False)
    self.assertFalse(await cog_settings.is_enabled(1, "games"))
    self.assertEqual((await GuildSettings.objects.aget(guild_id=1)).disabled_cogs, ["games"])
    await cog_settings.set_enabled(1, "games", True)
    self.assertTrue(await cog_settings.is_enabled(1, "games"))
    self.assertEqual((await GuildSettings.objects.aget(guild_id=1)).disabled_cogs, [])
async def test_fixed_cog_cannot_be_disabled(self):       # CogNotToggleable für "core"
async def test_fixed_cog_in_db_list_stays_enabled(self): # disabled_cogs=["core"] → is_enabled True
async def test_garbage_in_json_is_ignored(self):         # disabled_cogs={"x": 1} bzw. ["removed_cog", 5] → alles aktiv, get_states läuft
async def test_set_enabled_unregistered_guild_raises(self):  # GuildNotRegistered
async def test_sequential_toggles_keep_both(self):
    # games aus; dann DB-Zeile direkt (am Cache vorbei) um "shop" ergänzen; dann killmail aus
    # → disabled_cogs enthält games, shop, killmail
async def test_external_change_visible_after_ttl(self):
    # is_enabled → True (gecacht); DB direkt ändern; noch True; monotonic +61 s → False
async def test_enabled_guild_ids(self): ...
async def test_disable_with_active_dependents_raises(self):
    with self.assertRaises(DependencyConflict) as cm:
        await cog_settings.set_enabled(1, "banksystem", False)
    self.assertEqual(cm.exception.affected, ["economy", "shop", "games"])
    self.assertTrue(await cog_settings.is_enabled(1, "banksystem"))
async def test_disable_cascade_disables_dependents(self):
    changed = await cog_settings.set_enabled(1, "banksystem", False, cascade=True)
    self.assertEqual(changed, ["banksystem", "economy", "shop", "games"])
async def test_disable_only_lists_active_dependents(self):   # games schon aus → affected == ["economy", "shop"]
async def test_enable_with_disabled_requirement_raises(self): # alles aus; games an → DependencyConflict(affected=["banksystem"])
async def test_enable_cascade_enables_requirement(self):      # → ["games", "banksystem"], shop bleibt aus

# test_registry.py
def test_bank_dependents(self):
    self.assertEqual(registry.dependents("banksystem"), ["economy", "shop", "games"])
    self.assertEqual(registry.requirements("games"), ["banksystem"])
def test_requirements_reference_toggleable_known_cogs(self): ...
```

- [ ] **Step 2:** → FAIL
- [ ] **Step 3:** `registry.py`, dann `cog_settings.py` umsetzen
- [ ] **Step 4:** `python runtests.py demolizzen` → OK; `grep -rn "import discord\|from discord" demolizzen/services demolizzen/core/registry.py` → keine Treffer
- [ ] **Step 5:** Commit `feat: add cog registry and per-guild cog settings service`

### Task 5: BaseCog, Schalter für Befehle und Events

**Files:**
- Create: `demolizzen/core/errors.py`, `demolizzen/core/cog.py`, `demolizzen/tests/core/test_cog.py`
- Modify: jede Cog-Klasse der geladenen Erweiterungen (`core`, `owner`, `admin`, `guild`, `general`, `commands`, `levelsystem`, `banksystem`, `economy`, `shop`, `games`, `eveonline`, `killmail`, `ticket`); Listener in `levelsystem.py` (`on_message`, `on_guild_channel_delete`), `banksystem_config.py` (`on_guild_join`), `killmail.py` (`on_guild_leave`)

**Interfaces – Consumes:** `cog_settings.is_enabled`, `registry.get`

**Interfaces – Produces:**
- `core.errors.CogDisabled(discord.ext.commands.CheckFailure)` – `CogDisabled(key)`, `str()` = `This module is disabled on this server.`
- `core.cog.BaseCog(commands.Cog)` – Klassenattribut `key: str` (Pflicht; fehlt es oder ist es nicht im Verzeichnis, wirft `__init_subclass__` `TypeError`); `__init__(self, bot)` setzt `self.bot`; `async is_enabled(self, guild_id: int | None) -> bool` (`None` → `True`); `async cog_check(self, ctx) -> bool` (wirft `CogDisabled`)
- `core.cog.guild_listener(name: str | None = None)` – Ersatz für `commands.Cog.listener()`; ruft den Listener nicht auf, wenn das Cog in der Guild des Events abgeschaltet ist
- `core.cog.resolve_guild_id(args: tuple) -> int | None` – erstes Argument: `discord.Guild` → `.id`; sonst `.guild.id`, falls `.guild` gesetzt; sonst `.guild_id`; sonst `None`

`on_ready`-Listener bleiben `commands.Cog.listener()`. Cogs mit eigenem `__init__` brauchen kein `super().__init__`, solange sie `self.bot` setzen.

- [ ] **Step 1: Failing tests** `test_cog.py`

```python
class Dummy(BaseCog):
    key = "games"
    def __init__(self, bot): super().__init__(bot); self.calls = []
    @guild_listener()
    async def on_message(self, message): self.calls.append(message)

async def test_check_passes_when_enabled(self): ...
async def test_check_raises_when_disabled(self):
    await guilds.ensure_guild(1, "Alpha"); await cog_settings.set_enabled(1, "games", False)
    with self.assertRaisesMessage(CogDisabled, "This module is disabled on this server."):
        await Dummy(MagicMock()).cog_check(make_ctx(guild=make_guild(1)))
async def test_check_passes_in_dm(self):            # make_ctx(guild=None) → True
def test_cog_disabled_is_shown_to_user(self):       # issubclass(CogDisabled, commands.CheckFailure)
async def test_listener_skipped_when_disabled(self): # calls bleibt leer
async def test_listener_runs_without_guild(self):    # message.guild = None → aufgerufen
def test_listener_is_registered(self):              # ("on_message", "on_message") in Dummy.__cog_listeners__
def test_missing_or_unknown_key_raises(self):       # TypeError bei class X(BaseCog): pass / key = "nope"
def test_resolve_guild_id(self):                    # Guild, Member, Message ohne Guild, Objekt mit guild_id, leere args
def test_every_loaded_cog_uses_basecog(self):
    bot = Demolizzen(); bot.load_preload_extensions()
    for cog in bot.cogs.values():
        self.assertIsInstance(cog, BaseCog, cog.qualified_name)
        self.assertEqual(cog.key, cog.__module__.split(".")[2])
```

- [ ] **Step 2:** → FAIL
- [ ] **Step 3:** `errors.py` und `cog.py` umsetzen
- [ ] **Step 4:** Alle Cog-Klassen auf `BaseCog` mit `key` umstellen; die vier genannten Listener auf `@guild_listener()`
- [ ] **Step 5:** `python runtests.py demolizzen` → OK
- [ ] **Step 6:** CHANGELOG (`Added`), Commit `feat: gate cog commands and events per guild`

### Task 6: `/panel`

**Files:**
- Create: `demolizzen/cogs/panel/__init__.py`, `panel.py`, `_view.py`, `demolizzen/tests/cogs/test_panel.py`
- Modify: `demolizzen/config.py` (`"panel"` nach `"guild"` in `PRELOAD_EXTENSIONS`), `CHANGELOG.md`

**Interfaces – Consumes:** `cog_settings.get_states/set_enabled`, `guilds.ensure_guild`, `registry`, `checks.check_is_admin(ctx, precheck=True)`, `BaseCog`

**Interfaces – Produces:**
- `_view.build_embed(guild_name: str, states: dict[str, bool], selected: str | None = None) -> discord.Embed` – Titel `⚙️ Demolizzen Panel – {guild_name}`; je Cog ein Inline-Feld `🟢 {title}` bzw. `🔴 {title}`; bei `selected` Beschreibung = Titel, Beschreibung und Zustand des Cogs
- `_view.PanelView(guild_id: int, guild_name: str, author_id: int, states: dict[str, bool])` – `discord.ui.View`, `timeout=180`, `disable_on_timeout=True`; ein `string_select` (Platzhalter `Select a module`, eine Option je abschaltbarem Cog), Buttons `Enable` (grün) und `Disable` (rot), beide deaktiviert, bis ein Modul gewählt ist; nach Wahl ist nur der sinnvolle Button aktiv
- Meldet `set_enabled` einen `DependencyConflict`, zeigt die Ansicht statt zu schalten eine Rückfrage – `Disabling {title} will also disable: {titles}.` bzw. `Enabling {title} will also enable: {titles}.` – mit den Buttons `Confirm` und `Cancel`; `Confirm` ruft `set_enabled(..., cascade=True)`, `Cancel` zeigt wieder die Übersicht
- `PanelView.interaction_check`: weist ab, wenn `interaction.user.id != author_id` oder der Nutzer weder Owner ist noch `manage_guild` hat; Antwort ephemeral `You are not allowed to use this panel.`
- `panel.Panel(BaseCog)`, `key = "panel"`; Slash-Befehl `/panel` (`contexts=[guild]`, `default_member_permissions=Permissions(manage_guild=True)`, `@checks.is_admin()`), antwortet ephemeral mit Embed und View; ruft vorher `ensure_guild(ctx.guild.id, ctx.guild.name)`

- [ ] **Step 1: Failing tests** `test_panel.py`

```python
def test_embed_lists_every_toggleable_cog(self):
    embed = build_embed("Alpha", {"games": False, "ticket": True})
    self.assertEqual(embed.title, "⚙️ Demolizzen Panel – Alpha")
    self.assertEqual([f.name for f in embed.fields], ["🔴 Games", "🟢 Ticket System"])  # Titel laut Verzeichnis
async def test_command_registers_guild_and_responds_ephemeral(self):
    await cog.panel.callback(cog, ctx)
    self.assertTrue(await GuildProfile.objects.filter(guild_id=1).aexists())
    self.assertTrue(ctx.respond.await_args.kwargs["ephemeral"])
async def test_disable_button_persists_and_redraws(self):
    # Modul "games" wählen, Disable-Callback auslösen
    self.assertFalse(await cog_settings.is_enabled(1, "games"))
    interaction.response.edit_message.assert_awaited_once()
async def test_foreign_user_is_rejected(self):
    self.assertFalse(await view.interaction_check(make_interaction(user=make_member(99, manage_guild=True))))
async def test_author_without_permission_is_rejected(self):
    self.assertFalse(await view.interaction_check(make_interaction(user=make_member(10, manage_guild=False))))
    self.assertTrue(await cog_settings.is_enabled(1, "games"))
async def test_disable_bank_asks_before_cascading(self):
    # Disable auf "banksystem": nichts geschaltet, Embed-Beschreibung enthält
    # "Disabling Banksystem will also disable: Economy, Shop, Games."
async def test_confirm_cascades(self):   # danach banksystem, economy, shop, games aus
async def test_cancel_changes_nothing(self):
def test_select_has_no_fixed_cogs(self):  # Optionswerte ∩ {"core","owner","guild","panel"} == ∅
```

- [ ] **Step 2:** → FAIL
- [ ] **Step 3:** `_view.py`, `panel.py`, `__init__.py` (`setup`) umsetzen, `config.py` ergänzen
- [ ] **Step 4:** `python runtests.py demolizzen` → OK; `coverage run runtests.py demolizzen && coverage report --include="demolizzen/services/*"` → ≥ 90 %
- [ ] **Step 5:** CHANGELOG (`Added`: Panel, Cog-Schalter), Commit `feat: add /panel to toggle cogs per guild`

---

## Bekannte Grenzen dieser Etappe

- Hintergrundschleifen (Killmail, Bank-Zinsen, Shop) beachten den Schalter noch nicht; `enabled_guild_ids` steht dafür bereit.
- Das Cog `commands` enthält einzelne Befehle, die Bank-Daten lesen; es gilt nicht als abhängig, damit `/help` nicht an der Bank hängt.
- `games.py` ruft `self.bot.sessionmaker()` auf, das es nicht gibt (Altlast); wird beim Umzug von Games behoben.
