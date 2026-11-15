# Web panel: switching modules – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Server admins switch modules in the browser, with the bot's dependency confirmation.

**Architecture:** One POST view calls `cog_settings.set_enabled`; a `DependencyConflict` renders a confirmation page whose form repeats the request with `confirm=1`. Notices travel in the session.

**Tech Stack:** Django 5.2 async views.

**Spec:** `docs/superpowers/specs/2026-11-15-web-panel-design.md` (step 2)

## Global Constraints

- URL `POST /guilds/<int:guild_id>/modules/<slug:key>`, fields `enabled` (`0` or `1`) and `confirm` (`1`)
- A server the user may not manage answers 404 and nothing changes
- Unknown module 404; module that is always on 400; other `enabled` values 400

## Review Focus

1. Rights withdrawn between loading the page and pressing the button: 404, nothing switched. → Task 1
1. Request for a server the user manages, sent from another website: refused without CSRF token. → Task 1
1. `confirm=1` sent although nothing depends on the module: plain switch. → Task 1
1. The module was switched by someone else meanwhile: the request still ends in the asked state. → Task 1
1. A module key that is not in the registry or is always on: clear answer, no change. → Task 1

______________________________________________________________________

### Task 1: Switch modules

**Files:** Modify `demolizzen/web/{views,urls}.py`, `demolizzen/web/templates/web/guild.html`, `demolizzen/web/static/panel.css`, `docs/web-panel.md`, `CHANGELOG.md`; Create `demolizzen/web/templates/web/confirm.html`, `demolizzen/tests/web/test_modules.py`

**Interfaces – Consumes:** `cog_settings.set_enabled(guild_id, key, enabled, *, cascade) -> list[str]`, `DependencyConflict(key, enabled, affected)`, `registry.get(key)` · **Produces:** URL name `switch_module`

- [ ] **Step 1: Failing tests**

```text
test_server_page_offers_a_switch_for_every_switchable_module
test_switch_off_and_on
test_notice_is_shown_once
test_switching_off_a_needed_module_asks_first
test_confirming_switches_the_modules_together
test_switching_on_asks_for_the_requirement
test_confirm_without_dependencies_is_a_plain_switch
test_repeating_a_switch_is_harmless
test_module_that_is_always_on_cannot_be_switched
test_unknown_module_is_404
test_other_values_are_refused
test_foreign_guild_is_404_and_unchanged
test_withdrawn_rights_block_the_switch
test_switch_needs_a_sign_in
test_switch_needs_post_and_csrf
test_switch_is_logged
```

- [ ] **Step 2:** → FAIL · **Step 3:** Implement · **Step 4:** Suite green (SQLite and `USE_MYSQL=1`), `pre-commit run --all-files` green
- [ ] **Step 5:** Commit `feat: switch modules in the web panel`
