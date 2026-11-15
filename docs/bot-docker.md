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

## A database in a container

If there is no database yet, the compose file can start one: a MariaDB whose login is the one the
bot uses. In `.env` set

```shell
DATABASE_HOST=db
DATABASE_PORT=3306
DATABASE_NAME=demolizzen
DATABASE_USER=demolizzen
DATABASE_PASSWORD=a-long-random-password
DATABASE_ROOT_PASSWORD=another-long-random-password
```

and add `--profile database` to the compose commands on this page, for example

```shell
docker compose -f docker-compose.bot.yml --profile database up -d --build
```

Without `--profile database` the database service is left alone, so nothing changes for a bot that
uses a database of its own.

- Database, user and passwords are created at the very first start. Changing them in `.env`
  afterwards does not change the existing database.
- The data is kept in the volume `db-data`. `docker compose down` keeps it;
  `docker compose down -v` deletes it together with the logs.
- The database is reachable from the bot's container only; no port is published. A web panel on
  another machine needs a database it can reach, see
  [Reaching the database from the container](web-panel.md#reaching-the-database-from-the-container).
- The bot starts before the database is ready, ends, and is started again until it connects.
  A few restarts right after the first start are expected.

Back it up before every update that brings migrations:

```shell
docker compose -f docker-compose.bot.yml --profile database exec db \
  sh -c 'mariadb-dump -uroot -p"$MARIADB_ROOT_PASSWORD" --single-transaction "$MARIADB_DATABASE"' > backup.sql
```

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
