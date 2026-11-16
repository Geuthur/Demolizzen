# Contributing to This Project

Thank you for considering contributing to our project! Here are some guidelines to help you get started.

## Getting Started

1. **Fork the repository**: Click the "Fork" button at the top right of the repository page.

1. **Clone your fork**: Clone your forked repository to your local machine.

   ```sh
   git clone https://github.com/geuthur/demolizzen.git
   ```

1. **Set up the upstream remote**: Add the original repository as a remote to keep your fork up to date.

   ```sh
   git remote add upstream https://github.com/geuthur/demolizzen.git
   ```

1. **Set up Py-Cord Development Environment**

   To develop and test your change, you need a development environment based on [py-cord](https://docs.pycord.dev/en/stable/) on your local machine.
   Ensure you can use pre-commit checks in this environment.

## Pre-commit Hooks

We use pre-commit hooks to ensure code quality and consistency. Please make sure you have pre-commit installed and set up.

1. **Install pre-commit**: If you don't have pre-commit installed, you can install it using pip.

   ```sh
   pip install pre-commit
   ```

1. **Install the hooks**: Run the following command to install the pre-commit hooks.

   ```sh
   pre-commit install
   ```

1. **Use Pre Commit**

   Check all files

   ```sh
   pre-commit run --all-files
   ```

   If you want only one of the hooks like `pylint`

   ```sh
   pre-commit run pylint
   ```

## Branching and Contributing via Pull Requests

Before creating a pull request, make sure that you have forked the repository and are working on your fork. This ensures that your changes are isolated and do not affect the original repository until they are reviewed and merged.

The `master` branch should always be kept up to date to avoid conflicts. This means that all changes integrated into the `master` branch should be thoroughly reviewed and tested before being merged. Regular updates and synchronizations with the `master` branch help to identify and resolve potential conflicts early.

Before creating a new feature, an issue should always be opened first. This serves to start a discussion about the planned feature and ensure that all team members are informed about the planned changes. Through discussion, potential problems and improvements can be identified and considered early. This promotes a collaborative working approach and contributes to the quality and consistency of the project.

## Tests

We use several testing tools and frameworks to ensure the quality and reliability of our codebase. For Discord/py-cord bots, the following types of tests can serve as templates:

- **Unit tests for commands and cogs:** Test individual functions and commands, e.g., whether a command is called correctly and returns the expected response. Use mocking for Discord objects (User, Message, Context).
- **Event handler tests:** Simulate events like on_message, on_member_join, etc., and check if the handlers respond correctly.
- **Integration tests (optional):** Start the bot in a test environment and simulate real Discord interactions (e.g., with discord.ext.test or pytest-discord).
- **Coverage tests:** Check how much of your code is covered by tests.

Typical tools:

- pytest
- unittest
- pytest-mock or asynctest for async/mocking

The tests in this project serve as templates and can be adapted for your own py-cord commands and events.

Example of a simple command test (using pytest and unittest.mock):

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from demolizzen.cogs.general import GeneralCog


@pytest.mark.asyncio
async def test_ping_command():
    ctx = MagicMock()
    cog = GeneralCog(None)
    await cog.ping(ctx)
    ctx.send.assert_called_with("Pong!")
```

Below is a list of the main tools we use:

- [coverage](https://coverage.readthedocs.io/en/latest/#)

## Adding a cog

Cogs live in `demolizzen/cogs/<name>/` and follow three rules:

1. **Register it.** Add a `CogInfo` entry to `demolizzen/core/registry.py`. The key is the folder
   name. Set `toggleable=False` for cogs every server needs, and `requires=(...)` if the cog only
   makes sense together with another one. The server panel (`/panel`) and the per-server switch
   pick the entry up on their own.
1. **Derive from `BaseCog`.** Set `key` to the registry key. Commands of the cog are then refused
   with a notice in servers that disabled it. Declare event listeners with `@guild_listener()`
   from `demolizzen.core.cog` instead of `@commands.Cog.listener()` so they are skipped as well.
   Background loops must ask `cog_settings.enabled_guild_ids(key, guild_ids)` which servers to serve.
1. **Keep logic out of the cog.** Database access and rules go into `demolizzen/services/`, which
   must not import `discord`. The cog only translates between Discord and the service.

Add the folder name to `PRELOAD_EXTENSIONS` in `demolizzen/config.py` to load the cog.

### Settings in the server panel

A module can offer its settings in `/panel`. Register a page in the extension's `setup()`:

```python
from demolizzen.core import settings_pages


def setup(bot):
    settings_pages.register("ticket", ticket_settings_page)
    bot.add_cog(TicketSystem(bot))
```

A page is `async def page(interaction, back)`. It replaces the panel message with its own embed
and view and calls `back(interaction)` to return to the panel. Use
`settings_pages.check_admin(interaction, author_id)` as the view's `interaction_check` so the
page follows the same access rule as the panel. `demolizzen/cogs/ticket/_settings_page.py` is
the reference implementation.

py-cord views need a running event loop. Extensions are loaded before the bot runs, so create
persistent views in an `on_ready` listener, not in the cog's `__init__`.

## Running the tests

```shell
python runtests.py demolizzen --debug-mode
```

Tests use in-memory SQLite. Set `USE_MYSQL=1` to run them against MySQL, as tox and CI do.
Service tests go to `demolizzen/tests/services/`, cog tests to `demolizzen/tests/cogs/`;
`demolizzen/tests/helpers.py` provides stand-ins for Discord objects.

## Updating a running bot

Slash commands are registered with Discord when the bot starts. The normal update is therefore:

```shell
git pull
pip install -e .
```

followed by a restart of the bot. Before it connects, the bot applies pending database migrations
(`demolizzen/core/schema.py`); a migration that fails stops the start. `AUTO_MIGRATE=0` in `.env`
switches that off for operators who run `python manage.py migrate` themselves. Most logic lives in `demolizzen/services/` and
`demolizzen/core/`, which only a restart reloads.

The owner commands are for small changes without a restart:

- `/owner reload <cog>` reloads the code of one cog package (`demolizzen/cogs/<cog>/`), nothing
  else.
- `/owner load <cog>` and `/owner unload <cog>` add or remove a cog.
- `/owner migrate` applies pending database migrations.

All three load commands register added, changed or removed slash commands with Discord
afterwards.

### Where a slash command is registered

- Commands of the always-on modules (`toggleable=False` in `demolizzen/core/registry.py`) are
  global.
- Commands of the modules a server can switch are registered per server, only where the module is
  on (`demolizzen/core/command_scope.py`). Do not give them `guild_ids`; the scope sets them.
- Modules outside the registry (`vow`, `geuthur`) are registered as they declare themselves.

The bot registers every server at start. Afterwards the panel cog looks into the database once a
minute and registers only the servers whose modules changed, so a switch in the web panel needs no
restart. `/guild sync guild` registers the current server again by hand. A server that answers
403 is named in the log with the invite link and tried again after an hour.

Discord gives such a command a different id in every server. Build command links with
`get_command_mention(..., guild_id=...)` or `bot.command_scope.command_id(command, guild_id)`,
never with `command.id`.

## Web panel

The web panel lives in `demolizzen/web/` and calls the same service layer as the cogs. How to run
and deploy it is described in [docs/web-panel.md](docs/web-panel.md). Its tests are in
`demolizzen/tests/web/` and replace Discord with `FakeDiscord` from `fakes.py`.
