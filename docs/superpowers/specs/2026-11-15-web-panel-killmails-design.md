# Web panel: zKillboard subscriptions — design

## Intent

The zKillboard module has no settings page in the web panel. A server admin
wants to see which channels receive killmails and change that in the browser
instead of with `/killmail add|remove|subscription`.

## Goals

- List the server's subscriptions: channel, followed id, ISK threshold, losses.
- Change channel, threshold and losses of a subscription; remove one; add one.
- A change takes effect in the bot within a minute, without a restart.

## Non-goals

- Names for the followed ids (alliance, corporation, …). The page shows the id,
  as `/killmail subscription` does. Resolving names needs ESI and is a later step.
- Checking in the panel whether the bot may write in the chosen channel. The
  bot pauses a subscription it cannot deliver and says so, as before.
- Changing the followed id of a subscription: remove it and add another.

## Approaches

1. **A settings page like the others (chosen).** `PAGES["killmail"]`, one
   template, the existing view. The page has several forms (one per
   subscription plus "add"), told apart by an `action` field.
1. Own views and URLs per action. More code for the same result.

## How it works

- `services/killmails.py` gets `update_subscription`; a channel still follows
  an id at most once (`DuplicateSubscription`).
- The page accepts only text channels Discord lists for this server, or the
  channel a subscription already has. A subscription id that is not this
  server's is refused.
- A subscription added in the panel is owned by the signed-in user.
- Without the channel list (no bot token, Discord down) threshold, losses and
  removal still work; channel changes and adding do not.
- Removing sits behind a `<details>` element: one click opens it, a second
  removes. The panel has no JavaScript.
- The killmail cog re-reads all subscriptions every 60 seconds (one query).
