# Web panel

Server admins manage Demolizzen in a browser: they sign in with Discord and see the servers they
may manage. The panel is a small web application of its own. It shares nothing with the bot but the
database, so it can run on a different machine.

At the moment the panel shows each server's modules. Switching modules and changing settings
follow.

## What it needs

- **The bot's database**, reachable from where the panel runs. If that is another machine, give
  the panel its own database user restricted to that machine and use a private network or TLS.
- **A Discord application** for the sign-in (the bot's own application works). In the
  [Developer Portal](https://discord.com/developers/applications) under *OAuth2*, add the redirect
  `<WEB_BASE_URL>/callback`, for example `https://panel.example.com/callback`.
- **HTTPS** in front of it, ended by a proxy such as nginx.

## Settings

Set in `.env` (see `.env.example`):

| Variable                                          | Meaning                                                                 |
| ------------------------------------------------- | ----------------------------------------------------------------------- |
| `SECRET_KEY`                                      | Long random text. Signs the session cookies; changing it signs everyone out. |
| `DATABASE_HOST`, `_PORT`, `_USER`, `_PASSWORD`, `_NAME` | The bot's database.                                               |
| `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`      | OAuth2 client of the Discord application.                               |
| `WEB_BASE_URL`                                    | Where browsers reach the panel, e.g. `https://panel.example.com`.       |
| `WEB_ALLOWED_HOSTS`                               | Further host names, comma separated. Optional.                          |
| `WEB_DEBUG`                                       | `1` only for local development.                                         |
| `PANEL_BIND`, `PANEL_PORT`                        | Address and port docker compose publishes. Default `127.0.0.1:8000`.    |

The panel does not need `BOT_TOKEN` yet. Leave it empty on the machine that only runs the panel.

## Run it with Docker

```shell
cp .env.example .env   # then fill it in
docker compose up -d --build
docker compose ps      # "healthy" once the panel answers
```

The container listens on port 8000 and publishes it as `PANEL_BIND:PANEL_PORT`. Point nginx at it:

```nginx
server {
    server_name panel.example.com;
    listen 443 ssl;
    # ssl_certificate ...; ssl_certificate_key ...;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

`X-Forwarded-Proto` must be set by the proxy as shown: the panel uses it to tell whether a request
arrived over HTTPS.

Database migrations are applied where the bot is updated (`python manage.py migrate`); the panel
adds no tables.

## Run it without Docker

```shell
pip install -e ".[web]"
WEB_DEBUG=1 WEB_BASE_URL=http://localhost:8000 \
    uvicorn demolizzen.web.asgi:application --reload
```

Register `http://localhost:8000/callback` as redirect for this.

## How access is decided

- A server is listed if the signed-in user is its owner or has *Administrator* or *Manage Server*
  there, and the bot has joined it.
- The list is asked from Discord again every five minutes. Rights withdrawn in Discord therefore
  end in the panel within five minutes. If Discord cannot be asked, the last list is used for at
  most 30 minutes, then the user is signed out.
- The session is a signed cookie holding the user's id and name, their Discord token (scopes
  `identify guilds`) and the ids of their servers. Nothing about visitors is stored in the
  database.
- A module switched in the panel takes effect in the bot within a minute.
