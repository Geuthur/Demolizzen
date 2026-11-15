# Ticketsystem – Umsetzungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Das Ticketsystem läuft ohne Aufgaben-Tabelle, mit geprüften Rechten, dauerhaftem Zustand, Formular, „Open ticket"-Button, Protokoll und Einstellungen im `/panel`.

**Architecture:** `demolizzen/services/tickets.py` hält Rechte, Zustandswechsel und Nummernvergabe ohne Discord. Das Cog übersetzt Klicks in Service-Aufrufe und setzt deren Ergebnis in Discord um (Status-Nachricht, Rechte am Kanal, Kanalname). Eine dauerhafte Ansicht mit festen Kennungen ersetzt das Laden aller Tickets beim Start.

**Tech Stack:** Python ≥ 3.11, py-cord 2.8.x, Django 5.2 (async ORM), Tests: `python runtests.py demolizzen --debug-mode`.

**Spec:** `docs/superpowers/specs/2026-11-15-ticketsystem-design.md`

## Global Constraints

- `demolizzen/services/**` importiert nie `discord`.
- Kanalname: `ticket-{nummer:04d}-{name}` offen, `closed-{nummer:04d}-{name}` geschlossen; `name` kleingeschrieben, nur `a-z0-9-`, Gesamtlänge ≤ 100.
- Feste Kennungen: `ticket:claim`, `ticket:close`, `ticket:reopen`, `ticket:delete`, `ticket:open`. Alt-Kennungen: `^(claim|close|reopen|delete):\d+:\d+$`.
- Rechte genau nach der Tabelle im Design; Admin = Owner oder „Server verwalten"; Admin ist auch Staff.
- Betreff Pflicht, ≤ 100 Zeichen. Standard `max_open_tickets = 1`.
- Discord: höchstens 50 Kanäle je Kategorie; höchstens 2 Umbenennungen je Kanal in 600 s.
- Rückfrage beim Löschen exakt: `Delete this ticket? This cannot be undone.`
- Bot-Texte englisch. Jeder Commit lässt Tests grün und den Bot startbar; `pre-commit run --all-files` läuft durch.
- Abweichung vom Design: zwei Migrationen statt einer (Felder zuerst, Tabelle `guild_ticket_tasks` erst mit dem Entfernen des alten Codes), damit jeder Commit lauffähig bleibt.

### py-cord-Eigenheiten

- Dauerhafte Ansicht: `timeout=None` und jedes Element mit `custom_id`; einmal `bot.add_view(view)` – dann erreicht jeder Klick mit dieser Kennung die Ansicht, egal in welcher Nachricht.
- Formular: `discord.ui.Modal(title=…)` mit `discord.ui.InputText`; Öffnen über `interaction.response.send_modal(modal)` bzw. `ctx.send_modal(modal)`; Auswertung in `Modal.callback(interaction)`.
- Der HTTP-Client schläft bei einem 429 selbst und hält dabei die Sperre der Route. Der Bot zählt Umbenennungen deshalb selbst mit und wartet vor dem Aufruf, statt in das Limit zu laufen.
- Kanal- und Rollenauswahl: `discord.ui.Select(select_type=discord.ComponentType.channel_select, channel_types=[…])` bzw. `role_select`.

## Review Focus

1. Der Ersteller hat den Server verlassen: Übernehmen, Schließen, Wiederöffnen und Löschen funktionieren trotzdem. → Aufgabe 4
1. Zwei Staff-Mitglieder klicken gleichzeitig „Claim": genau einer übernimmt, der andere bekommt „already claimed". → Aufgabe 2
1. Der Ticket-Kanal wurde von Hand gelöscht: der Datensatz verschwindet, zählt nicht mehr gegen das Limit und blockiert keine Nummer. → Aufgabe 5
1. Die Kategorie ist voll (50) oder wurde gelöscht – beim Öffnen und beim Wiederöffnen aus dem Archiv: klare Meldung, kein halbes Ticket. → Aufgabe 4
1. Alt-Ticket ohne `control_message_id` und mit Alt-Kennungen: Klick wirkt und stellt die Nachricht um. → Aufgabe 5

## Dateien

| Datei                                                                                                    | Aufgabe | Verantwortung                                     |
| -------------------------------------------------------------------------------------------------------- | ------- | ------------------------------------------------- |
| `demolizzen/models/guild.py`, `migrations/0009_*`                                                        | 1       | neue Felder                                       |
| `demolizzen/services/errors.py`, `services/tickets.py`                                                   | 1–2     | Fehler, Einstellungen, Rechte, Zustände           |
| `demolizzen/cogs/ticket/_renamer.py`                                                                     | 3       | Umbenennen unter dem Discord-Limit                |
| `demolizzen/cogs/ticket/_views.py`, `_actions.py`                                                        | 4       | Status-Nachricht, Buttons, Formular, Aktionen     |
| `demolizzen/cogs/ticket/ticket.py`, `_transcript.py`                                                     | 5       | Cog, Alt-Kennungen, stündliche Prüfung, Protokoll |
| `demolizzen/core/settings_pages.py`, `cogs/panel/_view.py`, `cogs/ticket/_settings_page.py`              | 6       | Einstellungen im Panel                            |
| löschen: `_ticketview.py`, `_ticketprocess.py`, `_staffview.py`, `ticket_config.py`; `migrations/0010_*` | 7       | Altlasten                                         |

______________________________________________________________________

### Task 1: Felder, Fehler, Einstellungen

**Files:** Modify `demolizzen/models/guild.py`, `demolizzen/services/errors.py`; Create `demolizzen/migrations/0009_ticket_subject_log_limit.py` (per `makemigrations`), `demolizzen/services/tickets.py`, `demolizzen/tests/services/test_tickets_settings.py`

**Interfaces – Produces:**

- `GuildTicket.subject = CharField(max_length=100, blank=True, default="")`, `GuildTicket.control_message_id = BigIntegerField(null=True, blank=True)`

- `GuildTicketSettings.log_channel_id = PositiveBigIntegerField(null=True)`, `GuildTicketSettings.max_open_tickets = PositiveSmallIntegerField(default=1)`

- `errors.TicketError(ServiceError)` mit `.message: str` (für Nutzer gedacht); Unterklassen `TicketNotFound`, `TicketPermissionDenied`, `TicketStateError`, `TicketLimitReached`, `TicketNotConfigured`, `InvalidTicketSetting`

- `tickets.SETTING_FIELDS = ("category_id", "archive_category_id", "log_channel_id", "roles", "auto_archive_days", "max_open_tickets", "allow_user_close", "allow_user_reopen")`

- `async tickets.get_settings(guild_id: int) -> GuildTicketSettings` – legt die Zeile bei Bedarf an; `GuildNotRegistered` ohne Profil

- `async tickets.update_settings(guild_id: int, **fields) -> GuildTicketSettings` – nur `SETTING_FIELDS`; `auto_archive_days` 1–365, `max_open_tickets` 1–10, `roles` Liste von `int`; sonst `InvalidTicketSetting`

- `tickets.staff_role_ids(settings) -> list[int]` – bereinigt das JSON-Feld (kein Listen-Typ → `[]`)

- [ ] **Step 1: Failing tests**

```text
test_get_settings_creates_row_with_defaults        max_open_tickets == 1, log_channel_id is None
test_get_settings_unregistered_guild_raises        GuildNotRegistered
test_update_settings_persists_each_allowed_field   je Feld ein subTest
test_update_settings_rejects_unknown_field         InvalidTicketSetting für ticket_count
test_update_settings_rejects_out_of_range          auto_archive_days=0, max_open_tickets=11, roles="x"
test_staff_role_ids_ignores_garbage                None, {"a": 1}, ["1", 5, None] → [], [], [5]
test_ticket_has_subject_and_control_message_fields
```

- [ ] **Step 2:** → FAIL
- [ ] **Step 3:** Felder ergänzen, `DJANGO_SETTINGS_MODULE=testenv.settings python manage.py makemigrations demolizzen -n ticket_subject_log_limit`, Fehlerklassen und die drei Funktionen umsetzen
- [ ] **Step 4:** Suite grün; `python manage.py makemigrations --check --dry-run` meldet keine offenen Änderungen
- [ ] **Step 5:** Commit `feat: ticket settings service and new ticket fields`

### Task 2: Rechte und Zustandswechsel

**Files:** Modify `demolizzen/services/tickets.py`; Create `demolizzen/tests/services/test_tickets.py`

**Interfaces – Produces:**

- `tickets.Action` (`enum.Enum`): `CLAIM`, `CLOSE`, `REOPEN`, `DELETE`
- `tickets.Actor` – `@dataclass(frozen=True)`: `user_id: int`, `is_staff: bool = False`, `is_admin: bool = False`
- `tickets.is_allowed(action, actor, ticket, settings) -> bool` – die Rechte-Tabelle; Admin zählt als Staff; eigenes Ticket übernehmen ist nie erlaubt
- `tickets.channel_name(number: int, owner_name: str, closed: bool) -> str`
- `async tickets.check_can_open(guild_id, user_id) -> GuildTicketSettings` – `TicketNotConfigured` ohne Kategorie oder ohne Staff-Rollen, `TicketLimitReached` ab `max_open_tickets` offenen Tickets
- `async tickets.allocate_number(guild_id) -> int` – liest und erhöht `ticket_count` in einer Transaktion mit `select_for_update`
- `async tickets.create_ticket(guild_id, number, channel_id, user_id, subject, control_message_id=None) -> GuildTicket`
- `async tickets.get_by_channel(channel_id) -> GuildTicket` (`TicketNotFound`)
- `async tickets.claim(channel_id, actor) -> GuildTicket`, `close(...)`, `reopen(...)`, `delete(...)` – prüfen in einer Transaktion mit Sperre erst das Recht (`TicketPermissionDenied`), dann den Zustand (`TicketStateError`); `reopen` löscht `claimed_by`, `closed_*`, `is_archived`; `delete` gibt das gelöschte Ticket zurück
- `async tickets.check_action(channel_id, action, actor) -> GuildTicket` – dieselbe Prüfung ohne Änderung (für die Lösch-Rückfrage)
- `async tickets.set_control_message(channel_id, message_id) -> None`
- `async tickets.remove_by_channel(channel_id) -> bool`
- `async tickets.active_tickets(guild_ids) -> list[GuildTicket]` (nicht archiviert), `async tickets.due_for_archive(now=None) -> list[GuildTicket]` (geschlossen, nicht archiviert, `closed_at + auto_archive_days < now`, Archiv-Kategorie gesetzt), `async tickets.mark_archived(ticket_id) -> None`

Zustandsregeln: `CLAIM` nur offen und nicht übernommen; `CLOSE` nur offen; `REOPEN` nur geschlossen; `DELETE` immer.

- [ ] **Step 1: Failing tests**

```text
RightsTableTest: für jede Zelle der Design-Tabelle ein subTest, je mit allow_user_close/allow_user_reopen an und aus;
                 zusätzlich: Fremder ohne Rolle → alles False; Staff als Ersteller → CLOSE/REOPEN True, CLAIM False
ChannelNameTest: (42, "Max Mustermann!", False) → "ticket-0042-max-mustermann"; closed=True → "closed-0042-…";
                 leerer/nur Sonderzeichen-Name → "ticket-0042-user"; 150 Zeichen Name → Länge ≤ 100
OpenTest:        check_can_open ohne Kategorie / ohne Staff-Rollen → TicketNotConfigured;
                 mit einem offenen Ticket und Limit 1 → TicketLimitReached; geschlossenes Ticket zählt nicht
                 allocate_number liefert 1, 2, 3 und ticket_count steht danach auf 4
StateTest:       claim setzt claimed_by; zweites claim → TicketStateError("already claimed")
                 claim auf geschlossenes Ticket → TicketStateError; close setzt is_closed, closed_by, closed_at
                 close auf geschlossenes → TicketStateError; reopen setzt alles zurück
                 Ersteller ohne Erlaubnis: close → TicketPermissionDenied und Ticket unverändert
                 delete durch Staff → TicketPermissionDenied; durch Admin → Zeile weg
                 unbekannter Kanal → TicketNotFound; check_action ändert nichts
ArchiveTest:     due_for_archive beachtet Tage, fehlende Archiv-Kategorie, schon archivierte; mark_archived
                 remove_by_channel entfernt die Zeile und gibt True, danach False
```

- [ ] **Step 2:** → FAIL
- [ ] **Step 3:** Umsetzen
- [ ] **Step 4:** Suite grün; Abdeckung `services/tickets.py` ≥ 95 %
- [ ] **Step 5:** Commit `feat: ticket permissions and state transitions in service layer`

### Task 3: Umbenennen unter dem Discord-Limit

**Files:** Create `demolizzen/cogs/ticket/_renamer.py`, `demolizzen/tests/cogs/test_ticket_renamer.py`

**Interfaces – Produces:**

- `ChannelRenamer(clock=time.monotonic, sleep=asyncio.sleep)` mit `LIMIT = 2`, `WINDOW = 600`

- `ChannelRenamer.request(channel, name: str) -> None` – synchron, kehrt sofort zurück; stimmt der Name schon und steht nichts aus, passiert nichts; sonst läuft im Hintergrund genau ein Auftrag je Kanal, ein neuer Wunsch ersetzt den wartenden

- `async ChannelRenamer.wait(channel_id: int) -> None` – wartet auf den laufenden Auftrag (für Tests und `cog_unload`); `ChannelRenamer.cancel_all() -> None`

- Fehler beim Umbenennen (`discord.HTTPException`) werden protokolliert, nicht geworfen

- [ ] **Step 1: Failing tests** (Uhr und Schlaf als Nachbauten)

```text
test_rename_happens_immediately            channel.edit(name="closed-…") einmal awaited
test_same_name_is_not_sent
test_third_rename_within_window_waits      zwei sofort, der dritte erst nach sleep(≈600 − vergangene Zeit)
test_latest_request_wins_while_waiting     während des Wartens a → b: am Ende nur b gesendet
test_window_expires                        nach 601 s wieder sofort
test_http_error_is_logged_not_raised
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `feat: rate-limit aware ticket channel renamer`

### Task 4: Status-Nachricht, Buttons, Formular, Aktionen

**Files:** Create `demolizzen/cogs/ticket/_views.py`, `demolizzen/cogs/ticket/_actions.py`, `demolizzen/tests/cogs/test_ticket_actions.py`

**Interfaces – Consumes:** alles aus Aufgabe 2, `ChannelRenamer`, `cog_settings.is_enabled`

**Interfaces – Produces:**

- `_views.build_status_embed(ticket, owner_name: str | None = None) -> discord.Embed` – Titel `🎫 Ticket #0042 – {subject}` (ohne Betreff nur Nummer); Beschreibung `Status: 🟢 Open` bzw. `🔒 Closed` bzw. `📦 Archived`, dazu `Claimed by: <@id>`, `Closed by: <@id>`, `Created by: <@id>`

- `_views.TicketControlView(ticket=None, handler=None)` – dauerhaft; vier Buttons mit den festen Kennungen; mit `ticket` sind Claim (offen und nicht übernommen), Close (offen), Reopen (geschlossen) aktiv, Delete immer; jeder Klick ruft `handler(interaction, Action)`

- `_views.OpenTicketView(handler=None)` – dauerhaft, ein Button `Open ticket` (`ticket:open`) → `handler(interaction)`

- `_views.OpenTicketModal(on_submit)` – Felder `Subject` (Pflicht, max 100) und `Description` (optional, Absatz, max 1000); `callback` ruft `on_submit(interaction, subject, description)`

- `_views.ConfirmDeleteView(on_confirm)` – `timeout=60`, Buttons `Delete` und `Cancel`

- `_actions.TicketActions(bot, renamer, is_enabled)` mit

  - `actor_for(member, settings) -> tickets.Actor`
  - `async start_open(interaction) -> None` – prüft Modul, `check_can_open`, Kategorie vorhanden und `< 50` Kanäle; zeigt dann das Formular
  - `async open(interaction, subject, description) -> None` – Nummer, Kanal mit Rechten wie bisher (Ersteller ohne `mention_everyone`), Status-Nachricht mit Staff-Erwähnung, `create_ticket`; schlägt etwas nach dem Anlegen des Kanals fehl, wird der Kanal wieder gelöscht
  - `async handle(interaction, action) -> None` – Modul prüfen, Service aufrufen, bei `TicketError` dessen `message` ephemeral zeigen; sonst Status-Nachricht neu setzen, Schreibrecht des Erstellers ändern (übersprungen, wenn er nicht mehr im Server ist), Umbenennen anstoßen, bei Reopen eines archivierten Tickets zurück in die Ticket-Kategorie; öffentliche Meldung `{user} claimed|closed|reopened the ticket.`
  - `DELETE` zeigt zuerst `ConfirmDeleteView` mit `Delete this ticket? This cannot be undone.`; Bestätigen ruft `async delete(interaction) -> None` (Protokoll-Schritt kommt in Aufgabe 5)

- [ ] **Step 1: Failing tests**

```text
test_status_embed_for_open_claimed_closed_ticket
test_control_view_buttons_follow_ticket_state         je Zustand die aktiven Labels
test_views_are_persistent                             TicketControlView().is_persistent(), OpenTicketView().is_persistent()
test_start_open_shows_modal                           interaction.response.send_modal awaited mit OpenTicketModal
test_start_open_without_category_tells_user           Meldung nennt /panel, kein Modal
test_start_open_with_full_category_tells_user         50 Kanäle → "The ticket category is full."
test_start_open_at_limit_tells_user
test_start_open_when_module_disabled                  "This module is disabled on this server."
test_open_creates_channel_ticket_and_status_message   Name ticket-0001-…, GuildTicket mit subject und control_message_id
test_open_failure_after_channel_creation_cleans_up    send schlägt fehl → channel.delete awaited, kein GuildTicket
test_claim_by_staff_updates_message_and_announces
test_claim_by_owner_is_refused_ephemeral
test_close_revokes_send_and_requests_rename           set_permissions(send_messages=False), renamer.request(…, "closed-0001-…")
test_close_by_owner_respects_setting                  allow_user_close False → abgelehnt, True → geschlossen
test_reopen_of_archived_ticket_moves_channel_back
test_reopen_into_full_category_is_refused             Ticket bleibt geschlossen
test_actions_work_when_owner_left_the_guild           guild.get_member → None; close und reopen laufen durch
test_delete_asks_first_then_deletes_channel_and_row
test_delete_by_staff_without_admin_is_refused
test_legacy_ticket_without_control_message_adopts_clicked_message
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `feat: ticket status message, persistent buttons and actions`

### Task 5: Cog, Alt-Kennungen, stündliche Prüfung, Protokoll

**Files:** Rewrite `demolizzen/cogs/ticket/ticket.py`, `demolizzen/cogs/ticket/__init__.py`; Create `demolizzen/cogs/ticket/_transcript.py`, `demolizzen/tests/cogs/test_ticket_cog.py`

**Interfaces – Produces:**

- `TicketSystem(BaseCog)`, `key = "ticket"`: erzeugt `ChannelRenamer` und `TicketActions`, registriert in `__init__` `TicketControlView(handler=…)` und `OpenTicketView(handler=…)` per `bot.add_view`; `/ticket open` → `actions.start_open(ctx.interaction)`

- Listener `on_interaction`: Komponenten-Klicks mit Alt-Kennung → `actions.handle`; danach trägt die Nachricht die neuen Buttons

- Listener `on_guild_channel_delete(channel)` → `tickets.remove_by_channel(channel.id)`

- `@tasks.loop(hours=1) maintenance` → `async run_maintenance()`: nur Guilds mit aktivem Modul; fällige Tickets in die Archiv-Kategorie (übersprungen, wenn sie fehlt oder 50 Kanäle hat) und `mark_archived`; Datensätze ohne Kanal entfernen; für aktive Tickets `renamer.request(channel, erwarteter Name)`

- `_transcript.render_transcript(ticket, messages) -> str` – Kopf (Nummer, Betreff, Ersteller, geschlossen von, gelöscht von), dann je Nachricht `[YYYY-MM-DD HH:MM] autor: inhalt`, Anhänge als URL

- `_transcript.MAX_MESSAGES = 5000`

- `TicketActions.delete`: mit Log-Kanal Protokoll als `ticket-0042.txt` samt Embed dorthin, dann Kanal löschen; schlägt das Senden fehl, wird trotzdem gelöscht und der Fehler protokolliert

- [ ] **Step 1: Failing tests**

```text
test_cog_registers_persistent_views_once                bot.add_view zweimal, beide persistent
test_ticket_open_command_starts_open_flow
test_legacy_button_click_is_handled_and_migrated        custom_id "close:1:7" → Ticket geschlossen, message.edit mit TicketControlView
test_foreign_component_click_is_ignored                 custom_id "something:else" → kein Service-Aufruf
test_manual_channel_delete_removes_ticket               danach zählt count gegen das Limit 0
test_maintenance_archives_due_tickets                   channel.edit(category=archive), is_archived True
test_maintenance_skips_full_or_missing_archive_category
test_maintenance_skips_guilds_with_module_disabled
test_maintenance_removes_tickets_without_channel
test_maintenance_requests_expected_names
test_render_transcript_contains_header_and_messages
test_delete_posts_transcript_to_log_channel             log_channel.send mit Datei ticket-0001.txt
test_delete_without_log_channel_just_deletes
test_delete_continues_when_transcript_upload_fails
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen; `ticket_config`-Cog bleibt in dieser Aufgabe noch geladen, damit Einstellungen erreichbar sind · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `feat: rebuild ticket cog on service layer with transcript and maintenance`

### Task 6: Einstellungen im Panel

**Files:** Create `demolizzen/core/settings_pages.py`, `demolizzen/cogs/ticket/_settings_page.py`, `demolizzen/tests/cogs/test_ticket_settings_page.py`; Modify `demolizzen/cogs/panel/_view.py`, `demolizzen/tests/cogs/test_panel.py`, `demolizzen/cogs/ticket/__init__.py`

**Interfaces – Produces:**

- `settings_pages.register(key: str, page) -> None`, `settings_pages.get(key: str)`, `settings_pages.unregister(key: str) -> None`; `page` ist `async (interaction, back) -> None` und ersetzt die Panel-Nachricht; `back` ist `async (interaction) -> None` und zeigt das Panel wieder

- `PanelView`: Button `Settings`, nur vorhanden, wenn für das gewählte, aktive Modul eine Seite angemeldet ist

- `_settings_page.TicketSettingsView(guild_id, back, section="overview")` mit den Bereichen `Channels` (Ticket-Kategorie, Archiv-Kategorie, Log-Kanal), `Staff & permissions` (Rollen, zwei Umschalter), `Limits` (Tage `1/3/7/14/30`, offene Tickets `1/2/3/5`), dazu `Post ticket button` und `Back`; jede Änderung geht über `tickets.update_settings` und zeichnet die Seite neu

- `_settings_page.build_settings_embed(settings) -> discord.Embed` – zeigt alle aktuellen Werte, fehlende Pflichtwerte als `⚠️ not set`

- `Post ticket button` sendet in den aktuellen Kanal ein Embed (`Need help? Open a ticket.`) mit `OpenTicketView`

- `setup()` des Ticket-Cogs meldet die Seite an

- [ ] **Step 1: Failing tests**

```text
test_settings_button_only_for_modules_with_page         ticket → vorhanden, games → nicht
test_settings_button_absent_when_module_disabled
test_settings_button_opens_page_and_back_returns
test_embed_marks_missing_category_and_roles
test_each_control_updates_its_setting                   je Bedienelement ein subTest gegen die Datenbank
test_toggle_flips_allow_user_close
test_post_ticket_button_sends_open_view_to_channel
test_page_respects_panel_permission                     Fremder → abgewiesen
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `feat: ticket settings page in /panel`

### Task 7: Altlasten entfernen

**Files:** Delete `demolizzen/cogs/ticket/_ticketview.py`, `_ticketprocess.py`, `_staffview.py`, `ticket_config.py`; Modify `demolizzen/models/guild.py` (ohne `GuildTicketTask`), `demolizzen/cogs/ticket/__init__.py`, `CHANGELOG.md`, `CONTRIBUTING.md` (Abschnitt Einstellungsseiten); Create `demolizzen/migrations/0010_delete_guildtickettask.py`, `demolizzen/tests/test_migrations.py`

- [ ] **Step 1: Failing tests**

```text
test_no_pending_model_changes          call_command("makemigrations", check=True, dry_run=True) wirft nicht
test_ticket_task_model_is_gone         apps.get_model("demolizzen", "GuildTicketTask") → LookupError
test_only_one_ticket_cog_is_loaded     bot.cogs enthält TicketSystem, nicht TicketSystemConfig
test_no_ticket_config_command          kein Befehl "ticket_config" in bot.walk_application_commands()
```

- [ ] **Step 2:** → FAIL · **Step 3:** Löschen, Migration erzeugen · **Step 4:** Suite grün auf SQLite und mit `USE_MYSQL=1`; `pre-commit run --all-files` grün
- [ ] **Step 5:** CHANGELOG (`Added`, `Changed`, `Removed`), Commit `refactor: remove ticket task queue and legacy ticket views`

______________________________________________________________________

## Bekannte Grenzen

- Nach einem Neustart kennt der Bot frühere Umbenennungen nicht mehr; läuft er dabei in Discords Limit, wartet der HTTP-Client selbst.
- Das Protokoll enthält höchstens 5000 Nachrichten und keine Dateien, nur deren Links.
