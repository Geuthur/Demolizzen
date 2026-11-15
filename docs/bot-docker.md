# The bot in a container

`Dockerfile.bot` and `docker-compose.bot.yml` run the bot itself with Docker. The image holds one
state of the code, built before the bot starts, so an update is a single step. The
[web panel](web-panel.md) has its own image and compose file; the two share nothing but `.env` and
the database.

## What it needs

- Docker with the compose plugin.
- `.env` next to `docker-compose.bot.yml`, filled in as `.env.example` describes. The file is read
  when the container starts and is not copied into the image.
- The database, reachable from the container. If it runs on the Docker host itself, set
  `DATABASE_HOST=host.docker.internal`; [Reaching the database from the container](web-panel.md#reaching-the-database-from-the-container)
  describes what the database has to allow.

## First start

Stop the bot wherever it runs today before you start the container. Two bots with one token answer
every command twice and fight over the registration of the slash commands.

```shell
cp .env.example .env        # then fill it in
docker compose -f docker-compose.bot.yml build
docker compose -f docker-compose.bot.yml run --rm bot python manage.py migrate
docker compose -f docker-compose.bot.yml run --rm bot python manage.py init_database
docker compose -f docker-compose.bot.yml up -d
```

`init_database` is for a new database only: it adds the shop items, the mission ships and the
trade systems and downloads EVE's item and solar system lists. Skip that line and the one before
it when the database is already in use; the container applies pending migrations at every start.

## Day to day

```shell
docker compose -f docker-compose.bot.yml logs -f bot     # the console
docker compose -f docker-compose.bot.yml restart bot
docker compose -f docker-compose.bot.yml down            # stop
```

The log files (`demolizzen.log`, `discord.log`, `openapi.log`) are kept in the volume `bot-logs`
and survive a new container:

```shell
docker compose -f docker-compose.bot.yml exec bot tail -n 50 demolizzen/logs/demolizzen.log
```

The container restarts by itself after a crash and after the machine reboots. `docker compose down`
gives the bot 30 seconds to close its connections.

## Updating

```shell
git pull
docker compose -f docker-compose.bot.yml up -d --build
```

The new container applies pending database migrations and then starts the bot, which registers the
slash commands. Back up the database before an update that brings migrations.

## Modules of single servers

`vow`, `geuthur` and the other modules outside the standard list are switched on in `.env`,
without editing `demolizzen/config.py`:

```shell
EXTRA_EXTENSIONS=vow,geuthur
```

## Bot and panel on one machine

Both compose files read the same `.env`. Start each with its own command:

```shell
docker compose -f docker-compose.bot.yml up -d --build   # the bot
docker compose up -d --build                             # the web panel
```

`docker compose up` without `-f` only ever starts the panel.
