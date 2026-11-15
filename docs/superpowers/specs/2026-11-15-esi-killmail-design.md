# Design: ESI und Killmail-Feed

Stand: 2026-11-15 · Branch: `development` · Status: freigegeben (Geuthur, 2026-11-15)

## Warum

- Jeder ESI-Aufruf läuft über den blockierenden Client in der Event-Loop; solange steht der Bot.
- Die Namensauflösung hängt an einer Aufgaben-Tabelle und einer Dauerschleife ohne Fehlerschutz.
  Stirbt sie, warten alle Killmails mit unbekanntem Namen ohne Zeitlimit.
- Schlägt die Verarbeitung einer Killmail fehl, rückt der Abruf nicht weiter und fragt dieselbe
  Killmail fünfmal pro Sekunde erneut an. Bei Verbindungsfehlern gibt es keine Pause, die Vorgabe
  `Retry-After` wird in der Schleife ignoriert, nach Fehlern fehlen die Killmails der Lücke.
- Fehlt das Schreibrecht im abonnierten Kanal, landet jede Killmail samt Fehlermeldung im
  erstbesten anderen Kanal.
- Dieselbe Killmail wird je Kanal einzeln angereichert; je Killmail und Abo läuft eine
  Datenbankabfrage nach der Region; Namen warten bis zu dreimal 30 Sekunden.

## Ziele

1. Kein ESI-Aufruf blockiert den Bot.
1. Namen werden direkt aufgelöst: Zwischenspeicher, dann eine Sammelabfrage mit Zeitlimit. Keine
   Aufgaben-Tabelle, keine Dauerschleife.
1. Der Abruf rückt immer weiter, wartet bei Fehlern zunehmend länger, hält `Retry-After` ein und
   macht nach Fehlern an derselben Stelle weiter.
1. Eine Killmail wird einmal geprüft und einmal angereichert, egal wie viele Kanäle sie bekommen.
1. Die Abo-Regeln liegen als reine Funktion in der Fachschicht und sind getestet.
1. Ohne Schreibrecht pausiert das Abo; der Server erfährt es einmal im Hauptkanal.

## Nicht-Ziele

- Aussehen der Killmail-Nachrichten oder die Abo-Befehle ändern.
- Verpasste Killmails aus der Zeit nachholen, in der der Bot aus war.

## Was auf keinen Fall passieren darf

- Bestehende Abos gehen verloren oder passen plötzlich auf andere Killmails.
- Der Bot fragt zKillboard oder ESI in einer engen Schleife ab.
- Killmails erscheinen in einem Kanal, der sie nicht abonniert hat.

## Ansätze

|       | Ansatz                                                                                                                     | Abwägung                                                                |
| ----- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| **A** | ESI-Aufrufe aus der Event-Loop nehmen, Namen direkt auflösen, Abruf als kleine Zustandsmaschine, Regeln in die Fachschicht | Behebt alle Punkte; Parser und Nachrichtenaufbau bleiben                |
| B     | Feed komplett neu samt eigenem ESI-Client auf aiohttp                                                                      | Unabhängig von `django-esi`, aber viel neuer, ungetesteter Netzwerkcode |
| C     | Nur Fehlerschutz um die bestehenden Schleifen                                                                              | Blockade und Mehrfacharbeit bleiben                                     |

**Gewählt: A.**

**ESI-Aufrufe:** Der bewährte synchrone Client von `django-esi` wird in Arbeits-Threads
ausgeführt. Der asynchrone Client derselben Bibliothek ist dort als ungetestet markiert und lässt
sich aus der Entwicklungsumgebung nicht gegen ESI prüfen; für den Bot ist das Ergebnis dasselbe.

## Verhalten

- **Namen:** Unbekannte IDs einer Killmail gehen in einer Abfrage an ESI (Zeitlimit 15 s).
  Lehnt ESI die Sammelabfrage wegen einer ungültigen ID ab, wird einzeln aufgelöst. Was nicht
  auflösbar ist, heißt `Unknown` und wird nicht gespeichert.
- **Abruf:** nach jeder Killmail 0,2 s Pause; ohne neue Killmail 10 s; bei Server- oder
  Verbindungsfehlern 1, 2, 4 … höchstens 300 s; bei `429` die vorgegebene Zeit. Eine fehlerhafte
  Killmail wird protokolliert und übersprungen. Bleibt die erwartete Nummer fünf Minuten lang aus,
  gleicht der Bot mit dem aktuellen Stand von zKillboard ab.
- **Zustellung:** Abos werden in einem Schritt geprüft; je Kanal höchstens eine Nachricht pro
  Killmail. Server mit abgeschaltetem Modul bekommen nichts.
- **Fehlendes Schreibrecht:** Das Abo pausiert. Der Bot schreibt einmal in den Hauptkanal (sonst
  Systemkanal): `Killmail feed for <#kanal> is paused: I cannot send messages there.` Sobald das
  Recht wieder da ist, läuft es weiter. Gelöschte Kanäle verlieren ihr Abo wie bisher.

## Technik

- `core/openapi.py`: `_call` führt ESI-Operationen im Thread aus; `resolve_names(ids)`;
  Regionen je System im Speicher. `EveEntityTask` entfällt (Migration).
- `services/killmails.py`: `SubscriptionRule`, `KillFacts`, `matches`, `is_loss`, Abo-Verwaltung.
- `cogs/killmail/_feed.py`: `KillmailFeed.step()` – ein Abruf-Schritt, der die Wartezeit bis zum
  nächsten zurückgibt.
