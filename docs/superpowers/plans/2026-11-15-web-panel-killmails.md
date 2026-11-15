# Web panel: zKillboard subscriptions — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Manage killmail subscriptions of a server in the web panel.

**Architecture:** A settings page in `demolizzen/web/module_settings.py` on top of `services/killmails.py`; the killmail cog re-reads subscriptions every minute.

**Tech Stack:** Django async views, py-cord tasks.

**Spec:** `docs/superpowers/specs/2026-11-15-web-panel-killmails-design.md`

## Global Constraints

- English texts, no JavaScript (CSP), CSRF on every POST, services never import discord.
- Only ids Discord listed for this server, or already stored, are accepted.

## Review Focus

- A subscription of another server must not be changed or removed through this server's page.
- A channel of another server must not be accepted.
- Threshold input: empty, negative, not a number, absurdly large.
- Moving a subscription onto a channel that already follows the same id.
- The page without the channel list.

### Task 1: Service

**Files:** `demolizzen/services/killmails.py`, `demolizzen/services/errors.py`, `demolizzen/tests/services/test_killmails.py`

**Interfaces:** Produces `MAX_THRESHOLD`, `KillmailError(message)`, `DuplicateSubscription`, `SubscriptionNotFound`, `InvalidThreshold`, `async update_subscription(subscription_id, guild_id, *, channel_id=None, threshold, losses) -> SubscriptionRule` (`channel_id=None` keeps the channel).

### Task 2: Bot follows the database

**Files:** `demolizzen/cogs/killmail/killmail.py`, `demolizzen/tests/cogs/test_killmail.py`

**Interfaces:** `Killmail.watch_subscriptions` loop, 60 s, calls `load_rules()`.

### Task 3: Page

**Files:** `demolizzen/web/module_settings.py`, `demolizzen/web/views.py`, `demolizzen/web/templates/web/settings_base.html`, `settings_killmail.html`, `static/panel.css`, `demolizzen/tests/web/test_killmail_settings.py`

**Interfaces:** `SettingsPage.needs_user`; `save` may return the notice to show; POST field `action` = `add` | `update` | `remove`, `subscription` = id.

### Task 4: Docs, check, push
