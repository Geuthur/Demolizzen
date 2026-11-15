# Web panel: module settings – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change the settings of bank, level system and economy event in the browser.

**Architecture:** `demolizzen/web/module_settings.py` describes one page per module: how to load its values and how to save a submitted form through the service layer. One view serves all pages.

**Tech Stack:** Django 5.2 async views.

**Spec:** `docs/superpowers/specs/2026-11-15-web-panel-design.md` (step 3)

## Global Constraints

- URL `/guilds/<int:guild_id>/settings/<slug:key>`; GET shows, POST saves
- Interest choices in percent: 0, 0.1, 0.25, 0.5, 1, 2, 5, 10 (stored as fraction); event factor 1 to 10
- A server the user may not manage answers 404 and nothing changes; a module without settings answers 404
- An unchecked box means off

## Review Focus

1. A value outside the offered ones (interest 7, factor 11, text): nothing saved, the page says so. → Task 1
1. Saving for one server leaves every other server untouched. → Task 1
1. A stored interest rate that is not among the choices is still shown and kept when other fields are saved. → Task 1
1. Rights withdrawn before saving: 404, nothing saved. → Task 1
1. Form sent without CSRF token: refused. → Task 1

______________________________________________________________________

### Task 1: Settings pages

**Files:** Create `demolizzen/web/module_settings.py`, `demolizzen/web/templates/web/settings_{banksystem,levelsystem,economy}.html`, `demolizzen/tests/web/test_settings.py`; Modify `demolizzen/web/{views,urls}.py`, `demolizzen/web/templates/web/guild.html`, `demolizzen/web/static/panel.css`, `demolizzen/services/bank.py`, `demolizzen/cogs/banksystem/_settings_page.py`, `docs/web-panel.md`, `CHANGELOG.md`

**Interfaces – Produces:**

- `bank.INTEREST_CHOICES` (percent per week; moved from the cog)

- `module_settings.PAGES: dict[str, SettingsPage]`, `SettingsPage(key, title, template, load, save)`; `async load(guild_id) -> dict`; `async save(guild_id, data) -> None`, raising `InvalidInput(message)`

- URL name `module_settings`

- [ ] **Step 1: Failing tests**

```text
test_modules_with_settings_link_to_their_page
test_bank_page_shows_the_stored_values
test_bank_settings_are_saved
test_unchecked_boxes_switch_off
test_unusual_stored_interest_is_offered_and_kept
test_interest_outside_the_choices_is_refused
test_level_announcements_are_saved
test_event_is_saved
test_factor_outside_one_to_ten_is_refused
test_saved_notice_is_shown_once
test_other_servers_are_untouched
test_page_says_when_the_module_is_off
test_module_without_settings_is_404
test_foreign_guild_is_404_and_unchanged
test_withdrawn_rights_block_saving
test_settings_need_a_sign_in
test_saving_needs_csrf
test_saving_is_logged
```

- [ ] **Step 2:** → FAIL · **Step 3:** Implement · **Step 4:** Suite green (SQLite and `USE_MYSQL=1`), `pre-commit run --all-files` green
- [ ] **Step 5:** Commit `feat: module settings in the web panel`
