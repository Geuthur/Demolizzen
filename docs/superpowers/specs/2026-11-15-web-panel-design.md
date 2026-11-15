# Design: Web panel

Date: 2026-11-15 · Branch: `development` · Status: approved (Geuthur, 2026-11-15)

## Why

Server admins configure the bot with `/panel` inside Discord. The same settings should be
reachable in a browser. The bot runs on one server, the website on another; the panel is deployed
as a Docker container whose port the host's nginx forwards.

## Goals

1. A server admin signs in with Discord and sees the servers they may manage and the bot is in.
1. They can do in the browser what `/panel` offers: switch modules, change the settings of bank,
   level system, economy event and tickets.
1. The panel shares nothing with the bot but the database; it runs where the database is reachable.

## Non-goals

- Killmail subscriptions and anything else that lives in the running bot's memory.
- Accounts, roles or rights of the panel's own; Discord decides who may manage a server.
- A JavaScript application; pages are rendered on the server.

## What must never happen

- Someone changes or sees the settings of a server they may not manage.
- The bot token or the Discord client secret reaches a browser.
- A request forged by another website changes a setting.

## Approaches

|       | Approach                                                        | Trade-off                                                 |
| ----- | --------------------------------------------------------------- | --------------------------------------------------------- |
| **A** | Server-rendered Django pages calling the existing service layer | Little technology, fully testable; a page load per change |
| B     | JSON API plus a browser application                             | Smoother, but a second code base with its own build       |
| C     | Django admin                                                    | Quick, but made for operators, not per-server admins      |

**Chosen: A**, delivered in five steps, each usable on its own:

1. Foundation: sign-in, server list, access check, container. *(this document, step 1)*
1. Switch modules, with the same dependency confirmation as in the bot.
1. Settings of bank, level system and economy event.
1. Ticket settings with channel and role pickers.
1. Operating guide for both deployments.

## Behaviour (step 1)

- **Sign-in:** Discord OAuth2, authorization code grant, scopes `identify guilds`, protected by a
  `state` value bound to the session. Cancelled or unverifiable sign-ins end on a page that says so.
- **Who may manage a server:** its owner, or a member with *Administrator* or *Manage Server*,
  exactly as Discord reports it for the signed-in user.
- **Which servers are shown:** those the user may manage **and** the bot has registered.
- **Staying correct:** the list is fetched from Discord again when it is older than 5 minutes (the
  endpoint is rate limited). A rejected token signs the user out.
- **Server page:** name and the state of every module, read-only in this step. A server the user
  may not manage answers 404, like one that does not exist.
- **Session:** an encrypted and signed cookie holding the user's id and name, their Discord token and the ids of
  their manageable servers. No table, no account. Valid for 7 days, `Secure`, `HttpOnly`,
  `SameSite=Lax`.
- **Sign-out:** a POST with CSRF protection.

## Behaviour (step 2: switching modules)

- Every module that can be switched has a button on the server page: *Switch off* or *Switch on*.
  Modules that are always on have none.
- A switch is a POST with CSRF protection to `/guilds/<id>/modules/<key>`; the same access check as
  for the page runs first.
- **Dependencies** work as in the bot. Switching off a module others need, or switching on a module
  whose requirement is off, changes nothing at first: a page names the modules that would be
  switched with it and asks. Confirming switches them together.
- After a switch the server page says what was switched, once. Every switch is logged with the
  user's id.
- The bot notices a switch within a minute.

## Behaviour (step 3: module settings)

- Modules with settings show a *Settings* link on the server page:
  - **Banksystem:** interest per week (the same choices as in the bot: 0, 0.1, 0.25, 0.5, 1, 2,
    5, 10 %), deposits allowed, withdrawals allowed.
  - **Levelsystem:** announce level-ups. The channel follows in step 4, which brings channel
    pickers.
  - **Economy:** event running, payout factor 1 to 10.
- A page is a form; saving is a POST with CSRF protection to
  `/guilds/<id>/settings/<key>` behind the same access check. Afterwards the page says *saved*,
  once.
- A value the form does not offer changes nothing and the page says what is wrong.
- Settings can be changed while the module is off; the page says that it is off.
- Every change is logged with the user's id.

## Behaviour (step 4: tickets, channels and roles)

- The panel asks Discord for a server's channels and roles with the bot's token
  (`GET /guilds/<id>/channels`, `/roles`) and keeps the answer for one minute. The token stays on
  the server; pages only ever contain names and ids.
- **Ticket System** gets a settings page: ticket category, archive category (optional), log
  channel (optional), staff roles (up to 25), whether members may close and reopen their tickets,
  archive after … days and open tickets per member (the same choices as in the bot).
- **Levelsystem** gains the channel for level-up posts: the system channel or a text channel.
- Only ids Discord listed for that server are accepted. A stored channel or role that no longer
  exists is shown as such and may be kept; nothing is reset behind the admin's back.
- If Discord cannot be asked, or no bot token is configured, the page says so and still saves the
  settings that need no channel or role.
- Posting the ticket button stays in Discord (`/panel`).

## Technical decisions

- `demolizzen/web/`: settings on top of the bot's, URLs, async views, templates. Runs under ASGI
  with uvicorn (`pip install .[web]`). The bot's own settings stay ORM-only.
- Configuration by environment: `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `WEB_BASE_URL`
  (redirect URL is `<WEB_BASE_URL>/callback`), `WEB_ALLOWED_HOSTS`, `WEB_DEBUG`; database and
  `SECRET_KEY` as for the bot.
- Discord is reached through one small client class (`web/discord_api.py`) with a 10 second limit;
  tests replace it.
- Behind a proxy: `X-Forwarded-Proto` decides whether a request counts as HTTPS.
- A content security policy allows only the panel's own stylesheet; pages load nothing from
  elsewhere.
- Docker: one image for the panel, non-root, health check on `/healthz`; `docker-compose.yml`
  publishes the port for the host's nginx.

## Left to the builder

Markup and styling (plain, dark), wording of pages, internal module layout.
