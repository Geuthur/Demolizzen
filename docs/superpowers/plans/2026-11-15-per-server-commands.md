# Per-server slash commands — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Commands of a module that is switched off on a server are not registered there.

**Architecture:** `core/command_scope.py` assigns `guild_ids` to the commands of switchable modules from the module states in the database and registers each server's set through py-cord. The bot syncs through it; the panel cog polls it.

**Tech Stack:** py-cord 2.8.1, Django async ORM.

**Spec:** `docs/superpowers/specs/2026-11-15-per-server-commands-design.md`

## Global Constraints

- Python >= 3.11, English texts, services never import discord.
- Tests: `python runtests.py demolizzen --debug-mode`; `git add -A` before `pre-commit run --all-files`.
- An empty global command list is never sent to Discord.

## Review Focus

- A server that answers 403 or 5xx must not stop the others.
- A refresh with nothing changed makes no Discord request.
- A click on a command reaches the right command in every server (ids differ per server).
- A refresh that runs before the first full sync must not register everything twice.
- Reloading a module must not leave routes to the old command objects.

### Task 1: Fresh module states

**Files:** `demolizzen/services/cog_settings.py`, `demolizzen/tests/services/test_cog_settings.py`

**Interfaces:** Produces `async fresh_states(guild_ids: Iterable[int]) -> dict[int, dict[str, bool]]` — every requested guild is a key; read from the database now; renews the cache.

- [ ] Tests: defaults for a guild without a row; sees a change the cache hides; renews the cache.
- [ ] Implement, run, commit.

### Task 2: Command scope

**Files:** `demolizzen/core/command_scope.py`, `demolizzen/core/bot.py`, `demolizzen/tests/core/test_command_scope.py`, `demolizzen/tests/core/command_fakes.py`, `demolizzen/tests/core/test_bot.py`

**Interfaces:** Produces

- `module_key(command) -> str | None`

- `CommandScope(bot)` with `async sync_all() -> list[int]` (servers that failed), `async refresh() -> list[int]` (servers registered), `async sync_guild(guild_id: int) -> bool`, `command_id(command, guild_id: int | None) -> int | str | None`, `REFUSED_RETRY_SECONDS = 3600`

- `Demolizzen.command_scope`; `Demolizzen.sync_commands()` delegates to `sync_all()`; `auto_sync_commands=False`; invite link carries `applications.commands`.

- [ ] Tests against a fake command store with the real modules loaded: scope per server, module off, refresh only touches changed servers, no request when unchanged, 403 and 500 handling, routing by id per server, ids per server, joined server, stale routes, empty global list.

- [ ] Implement, run, commit.

### Task 3: Follow changes

**Files:** `demolizzen/cogs/panel/panel.py`, `demolizzen/cogs/panel/_view.py`, `demolizzen/cogs/guild/guild.py`, `demolizzen/core/bot.py`, their tests.

**Interfaces:** Consumes `CommandScope.refresh`, `sync_guild`.

- [ ] Tests: the watcher refreshes and survives an error; a switch in the Discord panel refreshes after answering; joining refreshes; `/guild sync guild` registers only this server.
- [ ] Implement, run, commit.

### Task 4: Command links

**Files:** `demolizzen/utils/functions.py`, `demolizzen/cogs/commands/_help.py`, callers of `get_command_mention`, tests.

**Interfaces:** Consumes `CommandScope.command_id`. Produces `get_command_mention(bot, cog, slash_command, slash_command_group=None, guild_id=None)`.

- [ ] Tests: the link carries the id of the server it is shown in.
- [ ] Implement, run, commit.

### Task 5: Docs and check

- [ ] CHANGELOG, `CONTRIBUTING.md`/`docs/web-panel.md` note, full suite on SQLite and MySQL, pre-commit, self-review, push.
