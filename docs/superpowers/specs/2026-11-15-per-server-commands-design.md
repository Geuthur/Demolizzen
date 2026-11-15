# Per-server slash commands — design

## Intent

A server admin switches a module off in the panel (Discord or web). Today the
module's slash commands stay visible on that server and only answer "this
module is switched off". They must disappear from that server for everyone,
admins included, and come back when the module is switched on again.

## Goals

- Commands of a switched-off module are not shown on that server.
- A change made in the web panel (another process, another machine) reaches
  Discord within about a minute; a change made in the Discord panel at once.
- One server refusing or failing never costs another server its commands.

## Non-goals

- Hiding single commands. The unit stays the module.
- Showing in the web panel whether Discord accepted the registration.

## Anti-goals

- A sync that can wipe commands: an empty global list is never sent.
- Depending on Discord's command permissions, which never hide anything from
  administrators.

## Approaches

1. **Register per server (chosen).** Commands of the always-on modules stay
   global. Commands of switchable modules become guild commands, registered in
   exactly the servers where their module is on. py-cord supports this through
   `ApplicationCommand.guild_ids` and `register_commands(guild_id=...)`.
   Costs: one registration per server instead of one in total, new command ids
   once (per-command overrides under *Integrations* are lost once more), and
   switchable commands are no longer offered in direct messages (all of them
   are guild-only today).
2. **Discord command permissions set by the panel.** Needs an extra OAuth scope
   on the panel login and still shows every command to administrators.
3. **Leave it.** Admins can hide commands by hand under *Integrations*.

The owner picked 1.

## How it works

- `demolizzen/core/command_scope.py` owns the rule and the bookkeeping. A
  command is *managed* when its cog is a `BaseCog` whose registry entry is
  toggleable. Everything else (always-on modules, single-server modules such
  as `vow` with fixed `guild_ids`) is left exactly as declared.
- `cog_settings.fresh_states(guild_ids)` reads the module states of many
  servers in one query, past the 60-second cache, and renews that cache.
- On start and after `/owner load|unload|reload`: every server gets its set,
  then the global list is registered. Servers first, so that the first start
  after this change shows a command twice for a moment instead of not at all.
- Every 60 seconds the panel cog asks the scope to refresh: one query, and a
  registration only for servers whose set of active modules changed.
- The Discord panel refreshes right after a switch; a joined server is
  registered right away.
- A server answering 403 is logged with the invite link and retried after an
  hour; any other failure is retried at the next refresh.
- Discord gives a guild command a different id in every server. The scope
  remembers them per server so command links (`</name:id>`) keep working.
- The module check that answers "switched off" stays as the second line for
  the minute in between.
- `auto_sync_commands` is turned off: the bot syncs only where this design
  says so.

## Left to the builder

Names of helpers, log wording, test layout.

## Not verified

Nothing here was run against Discord. The behaviour of the HTTP API is taken
from py-cord 2.8.1's source and Discord's documentation.
