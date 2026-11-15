# Web panel foundation – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sign in with Discord, list the manageable servers, show a server's modules read-only, ship as a container.

**Architecture:** `demolizzen/web/` holds Django settings, URLs, async views and templates on top of the bot's ORM settings. Access rules are pure functions; Discord is reached through one client class that tests replace. State lives in a signed cookie.

**Tech Stack:** Django 5.2 (async views, ASGI), uvicorn, aiohttp, Docker.

**Spec:** `docs/superpowers/specs/2026-11-15-web-panel-design.md`

## Global Constraints

- Scopes `identify guilds`; authorize URL `https://discord.com/oauth2/authorize`; token URL `https://discord.com/api/oauth2/token` (form encoded); API base `https://discord.com/api/v10`
- Manage rule: `owner` or `permissions & (0x8 | 0x20)`; `permissions` arrives as a string
- Server list refreshed after 300 seconds; session 7 days; Discord requests limited to 10 seconds
- A server the user may not manage answers 404
- Tests: `python runtests.py demolizzen --debug-mode`, also with `USE_MYSQL=1`; `pre-commit run --all-files`

## Review Focus

1. Callback with a `state` that differs from the session's, or without one: no sign-in. → Task 4
1. Rights withdrawn in Discord after sign-in: the server disappears within 5 minutes and its page answers 404. → Task 4
1. Discord answers 401 for a stored token: the user is signed out, not shown an error loop. → Task 4
1. Discord is down during sign-in or refresh: a page that says so; an existing list stays usable. → Task 4
1. Sign-out by GET or without CSRF token: refused. → Task 4

______________________________________________________________________

### Task 1: Web application skeleton

**Files:** Create `demolizzen/web/{__init__,base_settings,settings,asgi,urls,views,middleware}.py`, `demolizzen/web/templates/web/{base,landing,message}.html`, `demolizzen/web/static/panel.css`, `demolizzen/tests/web/{__init__,test_pages}.py`; Modify `demolizzen/config.py`, `testenv/settings.py`, `pyproject.toml`

**Interfaces – Produces:** URL names `home`, `login`, `callback`, `logout`, `guild`, `healthz`, `stylesheet`; settings `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `WEB_BASE_URL`

- [ ] **Step 1: Failing tests**

```text
test_healthz_answers_ok
test_landing_offers_the_discord_sign_in
test_stylesheet_is_served
test_pages_send_a_content_security_policy
test_unknown_page_is_404
```

- [ ] **Step 2:** → FAIL · **Step 3:** Implement · **Step 4:** Suite green
- [ ] **Step 5:** Commit `feat: web panel skeleton`

### Task 2: Access rules

**Files:** Create `demolizzen/web/access.py`, `demolizzen/tests/web/test_access.py`; Modify `demolizzen/services/guilds.py`, `demolizzen/tests/services/test_guilds.py`

**Interfaces – Produces:**

- `can_manage(guild: dict) -> bool`
- `async manageable_guild_ids(discord_guilds: list[dict]) -> list[int]` (manageable and registered, sorted)
- `async guilds.known_guilds(guild_ids) -> list[tuple[int, str]]` (id, name; sorted by name)

- [ ] **Step 1: Failing tests**

```text
test_owner_administrator_and_manage_server_may_manage
test_other_members_may_not_manage
test_broken_permission_values_may_not_manage
test_only_registered_and_manageable_guilds_are_kept
test_known_guilds_returns_names_sorted
```

- [ ] **Step 2:** → FAIL · **Step 3:** Implement · **Step 4:** Suite green
- [ ] **Step 5:** Commit `feat: web panel access rules`

### Task 3: Discord client

**Files:** Create `demolizzen/web/discord_api.py`, `demolizzen/tests/web/test_discord_api.py`

**Interfaces – Produces:** `DiscordError`, `DiscordUnauthorized(DiscordError)`, `DiscordClient(client_id, client_secret, redirect_uri)` with `authorize_url(state) -> str`, `async exchange_code(code) -> str` (access token), `async fetch_user(token) -> dict`, `async fetch_guilds(token) -> list[dict]`; `get_client() -> DiscordClient`

- [ ] **Step 1: Failing tests**

```text
test_authorize_url_carries_client_scopes_redirect_and_state
test_exchange_code_posts_the_form_and_returns_the_token
test_user_and_guilds_are_fetched_with_the_bearer_token
test_401_is_unauthorized
test_other_errors_timeouts_and_bad_answers_are_discord_errors
```

- [ ] **Step 2:** → FAIL · **Step 3:** Implement · **Step 4:** Suite green
- [ ] **Step 5:** Commit `feat: discord oauth client for the web panel`

### Task 4: Sign-in, server list, server page

**Files:** Create `demolizzen/web/session.py`, `demolizzen/web/templates/web/{servers,guild}.html`, `demolizzen/tests/web/test_login.py`, `demolizzen/tests/web/test_servers.py`; Modify `demolizzen/web/views.py`

**Interfaces – Consumes:** Task 2 and 3 · **Produces:** `session.sign_in(request, user, token, guild_ids)`, `async session.current_guild_ids(request, client) -> list[int] | None` (None: signed out), `REFRESH_SECONDS = 300`

- [ ] **Step 1: Failing tests**

```text
test_login_redirects_to_discord_with_a_fresh_state
test_callback_signs_in_and_keeps_manageable_registered_guilds
test_callback_with_wrong_or_missing_state_is_refused
test_cancelled_login_says_so
test_discord_failure_during_login_says_so
test_home_lists_the_servers
test_home_without_servers_explains_why
test_guild_page_shows_module_states
test_foreign_or_unknown_guild_is_404
test_pages_need_a_sign_in
test_list_is_refreshed_after_five_minutes
test_withdrawn_rights_remove_the_server
test_rejected_token_signs_out
test_discord_failure_during_refresh_keeps_the_list
test_logout_needs_post_and_csrf
```

- [ ] **Step 2:** → FAIL · **Step 3:** Implement · **Step 4:** Suite green
- [ ] **Step 5:** Commit `feat: web panel sign-in, server list and server page`

### Task 5: Container and documentation

**Files:** Create `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`; Modify `CONTRIBUTING.md`, `CHANGELOG.md`

- [ ] **Step 1:** Dockerfile (non-root, health check, uvicorn with proxy headers), compose file publishing `${PANEL_BIND:-127.0.0.1}:${PANEL_PORT:-8000}:8000`
- [ ] **Step 2:** Build the image and request `/healthz` and `/` from the running container
- [ ] **Step 3:** Document variables, the Discord redirect URL and an nginx example
- [ ] **Step 4:** Suite green (SQLite and `USE_MYSQL=1`), `pre-commit run --all-files` green
- [ ] **Step 5:** Commit `feat: container and documentation for the web panel`
