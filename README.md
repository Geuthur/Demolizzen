# Demolizzen

A Discord bot for EVE Online communities: killmails from zKillboard, market prices, an economy with
missions, a level system and help tickets. Each server decides which of these it uses.

- [Changelog](CHANGELOG.md)
- [Web panel](docs/web-panel.md)
- [Contributing](CONTRIBUTING.md)
- [Privacy policy](PRIVACY_POLICY.md)
- Support: <https://discord.gg/WrHzA4rnxA>

## What it does

Server admins switch modules on and off per server, in Discord with `/panel` or in the
[web panel](docs/web-panel.md). The slash commands of a module that is off are not shown on that
server.

| Module        | What members get                                                   |
| ------------- | ------------------------------------------------------------------ |
| zKillboard    | Killmails of an alliance, corporation, character, region or system |
| EVEOnline     | Market prices in Jita, Amarr and Dodixie, and the server status    |
| Ticket System | Private help tickets with staff roles, archive and transcript      |
| Levelsystem   | Experience for chatting, levels, rank cards and a leaderboard      |
| Banksystem    | Wallets, bank accounts, transfers and weekly interest              |
| Economy       | Daily reward, work and missions with ships (needs Banksystem)      |
| Shop          | Items and ships to buy (needs Banksystem)                          |
| Games         | Small games to win or lose money (needs Banksystem)                |
| Commands      | `/help` and everyday commands                                      |
| Admin         | Moderation commands                                                |
| General       | The bot's status display                                           |

Core, Owner, Guild and Panel are always on: the bot cannot work without them.

## Requirements

- Python 3.11 or newer
- MySQL or MariaDB
- A Discord application with a bot user ([Developer Portal](https://discord.com/developers/applications))
- An EVE Online application for ESI ([EVE Developers](https://developers.eveonline.com/))

## Installation

```shell
git clone https://github.com/Geuthur/Demolizzen.git
cd Demolizzen
pip install -e .
cp .env.example .env
```

Fill in `.env`: the bot token, the database and the EVE application. `.env.example` explains every
setting. Then create the tables and the default data:

```shell
python manage.py migrate
python manage.py init_database
```

`init_database` adds the shop items, the mission ships and the trade systems, and downloads EVE's
item and solar system lists.

Start the bot:

```shell
python -m demolizzen.launch
```

On its first connect the bot prints an invite link. It asks for the `bot` and
`applications.commands` scopes; a server needs both to get its slash commands.

## First steps on a server

1. `/panel` shows the modules of the server. Switch off what you do not need and open the settings
   of the ones you keep. It is for members with the Manage Server permission.
1. `/guild set_channel` sets the channel the bot uses for its own messages.
1. `/help` lists the commands of the active modules.

## Web panel

The same switches and settings in a browser, plus a page for the killmail subscriptions. Admins
sign in with Discord. The panel is a separate small web application that shares only the database
with the bot and ships as a Docker image. See [docs/web-panel.md](docs/web-panel.md).

## Updating

```shell
git pull
pip install -e .
python manage.py migrate
```

Then restart the bot. It registers the slash commands with Discord at every start.
[CONTRIBUTING.md](CONTRIBUTING.md#updating-a-running-bot) has the details.

## Upgrading from 2.x

Version 3 changes how the bot is run and what a server sees. Back up the database first.

- **Python 3.11** or newer is required.
- **Migrations** `0008` to `0014` are applied by `python manage.py migrate`. `0011` turns bank
  interest rates into fractions (a stored `5` becomes `0.05`), `0013` recreates the price cache.
- **`panel` must be loaded.** If you keep your own `PRELOAD_EXTENSIONS`, add `"panel"` to it.
- **Slash commands move from global to per server.** They get new ids at the first start, so
  restrictions set per command under *Server Settings → Integrations* have to be set again. If a
  server refuses the registration, the log names it together with the invite link to use again.
- **Settings moved into `/panel`.** `/bank_config`, `/ticket_config`, `/levelsystem_config`,
  `/admin economy` and `/bank create` are gone; bank accounts and profiles are created on demand.
- **English everywhere.** `/spenden` is now `/donate`.
- **`/eve price`** offers Jita, Amarr and Dodixie.

The [changelog](CHANGELOG.md) lists everything.

## Development

```shell
pip install -e ".[tests-demolizzen-latest]"
pre-commit install
python runtests.py demolizzen --debug-mode
```

Tests run on in-memory SQLite; `USE_MYSQL=1` runs them against MySQL.
[CONTRIBUTING.md](CONTRIBUTING.md) describes the layout of the code and how to add a module.

## License

[GPL-3.0](LICENSE)
