# Verwaltungs- und Grundmodule – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Event pro Server im Panel, Grundbefehle ohne Registrierung, Admin-, Owner- und Statusfehler behoben.

**Architecture:** Zustand und Regeln in der Fachschicht (`services/missions.py`, `shop.py`, `bank.py`), dünne Cogs, Einstellungsseite über `core/settings_pages`.

**Tech Stack:** py-cord 2.8, Django 5.2 (async ORM).

**Spec:** `docs/superpowers/specs/2026-11-15-admin-core-design.md`

## Global Constraints

- Event-Faktor 1 bis 10, Standard 2; Event standardmäßig aus
- `/moderation clear`: 1 bis 100 Nachrichten, höchstens 14 Tage alt
- `/bag`: höchstens 25 Felder; `/richest`: Top 10
- Tests: `python runtests.py demolizzen --debug-mode`, auch mit `USE_MYSQL=1`; `pre-commit run --all-files`

## Review Focus

1. Event eingeschaltet, Faktor nie gesetzt: Auszahlung verdoppelt, nie 0. → Aufgabe 1
1. Alter Faktor 0 oder negativ erreicht `resolve`: Auszahlung bleibt mindestens unverändert. → Aufgabe 1
1. Mitglied ohne Profil ruft `/help`, `/bag`, `/richest` auf: kein Hinweis auf Registrierung. → Aufgabe 3
1. `/moderation clear` ohne Leserecht im Kanal: Antwort statt Dauer-„denkt nach“. → Aufgabe 4
1. Datenbank fällt aus und kommt zurück: Anzeige erst rot, dann wieder grün. → Aufgabe 5

______________________________________________________________________

### Task 1: Event in der Fachschicht

**Files:** Modify `demolizzen/models/guild.py`, `demolizzen/services/missions.py`, `demolizzen/services/errors.py`, `demolizzen/cogs/economy/{economy,mission,missionfunc}.py`, `demolizzen/config.py`, `demolizzen/tests/services/test_missions.py`, `demolizzen/tests/cogs/test_economy_cog.py`; Create `demolizzen/migrations/0014_guildeconomysettings.py`

**Interfaces – Produces:**

- `Event(active: bool, factor: int)`; `MIN_EVENT_FACTOR = 1`, `MAX_EVENT_FACTOR = 10`, `DEFAULT_EVENT_FACTOR = 2`
- `async get_event(guild_id: int) -> Event` (ohne Eintrag: `Event(False, 2)`)
- `async set_event(guild_id: int, *, active: bool | None = None, factor: int | None = None) -> Event`; wirft `InvalidEventFactor`, `GuildNotRegistered`
- `MissionEvent(ctx, components, mission_account, kind, event: Event)`

- [ ] **Step 1: Failing tests**

```text
test_event_defaults_to_off_with_factor_two
test_set_event_stores_per_guild
test_factor_outside_one_to_ten_is_refused
test_set_event_needs_a_registered_guild
test_resolve_never_lowers_the_payout_for_a_bad_factor
test_work_uses_the_stored_event
test_mission_uses_the_stored_event
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen, Migration · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `feat: economy event stored per guild with a safe factor`

### Task 2: Event im Panel

**Files:** Create `demolizzen/cogs/economy/_settings_page.py`, `demolizzen/tests/cogs/test_economy_settings_page.py`; Modify `demolizzen/cogs/economy/__init__.py`, `demolizzen/cogs/admin/admin.py`

**Interfaces – Consumes:** `missions.get_event`, `missions.set_event` · **Produces:** `economy_settings_page(interaction, back)`, `EconomySettingsView`

- [ ] **Step 1: Failing tests**

```text
test_embed_shows_state_and_factor
test_toggle_switches_the_event
test_factor_select_stores_the_factor
test_page_respects_panel_permission
test_back_returns_to_panel
test_economy_settings_page_is_registered
test_admin_has_no_economy_commands
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `feat: economy event settings in the server panel`

### Task 3: Grundbefehle ohne Registrierung

**Files:** Modify `demolizzen/cogs/commands/{commands,_base,_economy}.py`, `demolizzen/cogs/core/core.py`, `demolizzen/services/{shop,bank}.py`; Create `demolizzen/tests/cogs/test_commands_cog.py`, `demolizzen/tests/cogs/test_core.py`; erweitern `demolizzen/tests/services/{test_shop,test_bank}.py`

**Interfaces – Produces:**

- `async shop.get_bag(guild_id: int, user_id: int) -> list[BagItem]` (`BagItem(name: str, quantity: int)`, nur Menge > 0, nach Name sortiert)
- `async bank.richest(guild_id: int, limit: int = 10) -> Richest` (`Richest(total: int, top: list[tuple[str, int]])`)

- [ ] **Step 1: Failing tests**

```text
test_get_bag_lists_owned_items
test_richest_returns_top_wallets_and_total
test_commands_need_no_registration
test_bag_empty_message
test_bag_shows_at_most_25_items
test_richest_keeps_names_as_they_are
test_richest_without_accounts
test_auth_register_is_gone
test_uptime_does_not_log_guilds
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `fix: basic commands work without registration`

### Task 4: `/moderation clear`

**Files:** Modify `demolizzen/cogs/admin/admin.py`; Create `demolizzen/tests/cogs/test_admin.py`

- [ ] **Step 1: Failing tests**

```text
test_clear_deletes_recent_messages_and_reports_the_count
test_clear_without_messages_says_so
test_clear_answers_when_reading_is_forbidden
test_clear_answers_when_deleting_fails
test_clear_only_looks_at_the_last_14_days
test_clear_limit_is_between_1_and_100
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `fix: moderation clear always answers`

### Task 5: Owner und Statusanzeige

**Files:** Modify `demolizzen/cogs/owner/owner.py`, `demolizzen/cogs/general/general.py`, `CHANGELOG.md`; Create `demolizzen/tests/cogs/test_owner.py`, `demolizzen/tests/cogs/test_general.py`

- [ ] **Step 1: Failing tests**

```text
test_force_deposits_update_runs_the_interest
test_force_deposits_update_without_bank_module
test_force_ship_update_is_gone
test_migrate_does_not_block_the_event_loop
test_status_keeps_the_activity_in_direct_messages
test_status_turns_red_on_database_failure
test_status_recovers_when_the_database_is_back
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün (SQLite und `USE_MYSQL=1`), `pre-commit run --all-files` grün
- [ ] **Step 5:** CHANGELOG, Commit `fix: owner commands and status display`
