# Web panel: tickets, channels and roles – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ticket settings and the level-up channel in the browser, with channels and roles read from Discord.

**Architecture:** `DiscordBotClient` fetches channels and roles with the bot token; `web/directory.py` turns them into sorted choices and caches them per server for a minute. Settings pages that need them receive the directory, or `None` when Discord cannot be asked.

**Tech Stack:** Django 5.2 async views, aiohttp.

**Spec:** `docs/superpowers/specs/2026-11-15-web-panel-design.md` (step 4)

## Global Constraints

- `GET https://discord.com/api/v10/guilds/<id>/channels` and `/roles`, header `Authorization: Bot <token>`, 10 second limit
- Channel types: 0 text, 4 category; everything else is not offered. The role whose id equals the server id (@everyone) is not offered
- Directory cached 60 seconds per server; failures are not cached
- At most 25 staff roles; archive days and open tickets from `tickets.ARCHIVE_DAY_CHOICES` / `OPEN_TICKET_CHOICES`

## Review Focus

1. An id from another server, or any made-up id, submitted as category, channel or role: refused, nothing saved. → Task 2
1. Discord down or no bot token: page usable, pickers left untouched by saving. → Task 2
1. A stored channel or role deleted in Discord: shown, kept on save unless the admin changes it. → Task 2
1. The bot token never appears in a page, a redirect or a log line. → Task 1
1. Two servers opened one after the other never see each other's channels. → Task 1

______________________________________________________________________

### Task 1: Channels and roles from Discord

**Files:** Create `demolizzen/web/directory.py`, `demolizzen/tests/web/test_directory.py`; Modify `demolizzen/web/discord_api.py`, `demolizzen/web/base_settings.py`, `demolizzen/tests/web/{fakes,test_discord_api}.py`, `testenv/settings.py`

**Interfaces – Produces:**

- `BotTokenMissing(DiscordError)`; `DiscordBotClient(token)` with `async fetch_channels(guild_id) -> list[dict]`, `async fetch_roles(guild_id) -> list[dict]`; `get_bot_client() -> DiscordBotClient` (raises `BotTokenMissing`)

- `Choice(id: int, name: str)`; `Directory(categories, text_channels, roles)` (lists of `Choice`); `async directory.load(guild_id) -> Directory`; `directory.clear()`

- [ ] **Step 1: Failing tests**

```text
test_bot_requests_carry_the_bot_token
test_bot_request_failures_are_discord_errors
test_missing_token_is_reported
test_channels_are_split_and_sorted
test_everyone_role_is_not_offered
test_unreadable_entries_are_skipped
test_directory_is_cached_per_server_for_a_minute
test_failures_are_not_cached
```

- [ ] **Step 2:** → FAIL · **Step 3:** Implement · **Step 4:** Suite green
- [ ] **Step 5:** Commit `feat: channels and roles of a server for the web panel`

### Task 2: Ticket settings and level-up channel

**Files:** Modify `demolizzen/web/{module_settings,views}.py`, `demolizzen/web/templates/web/{settings_base,settings_levelsystem}.html`, `demolizzen/web/static/panel.css`, `demolizzen/services/tickets.py`, `demolizzen/cogs/ticket/_settings_page.py`, `demolizzen/tests/web/test_settings.py`, `docs/web-panel.md`, `.env.example`, `CHANGELOG.md`; Create `demolizzen/web/templates/web/settings_ticket.html`, `demolizzen/tests/web/test_ticket_settings.py`

**Interfaces – Consumes:** Task 1 · **Produces:** `SettingsPage(..., needs_directory: bool)`; `load(guild_id, directory)`, `save(guild_id, data, directory)` with `directory: Directory | None`; `tickets.ARCHIVE_DAY_CHOICES`, `tickets.OPEN_TICKET_CHOICES`

- [ ] **Step 1: Failing tests**

```text
test_ticket_page_offers_channels_and_roles
test_ticket_settings_are_saved
test_optional_channels_can_be_cleared
test_ids_discord_did_not_list_are_refused
test_more_than_25_roles_are_refused
test_limits_outside_the_choices_are_refused
test_deleted_channel_and_role_are_shown_and_kept
test_page_says_what_is_missing_to_open_tickets
test_without_discord_the_other_settings_still_save
test_missing_bot_token_is_explained
test_level_channel_is_saved
test_level_channel_not_listed_is_refused
test_level_page_without_discord_still_saves_announcements
test_bank_page_does_not_ask_discord
```

- [ ] **Step 2:** → FAIL · **Step 3:** Implement · **Step 4:** Suite green (SQLite and `USE_MYSQL=1`), `pre-commit run --all-files` green
- [ ] **Step 5:** Commit `feat: ticket settings and level-up channel in the web panel`
