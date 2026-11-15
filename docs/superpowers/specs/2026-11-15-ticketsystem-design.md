# Design: Ticketsystem

Stand: 2026-11-15 · Branch: `development` · Status: Entwurf, wartet auf Freigabe

Baut auf `2026-11-15-fundament-cog-schalter-design.md` auf (Fachschicht, `BaseCog`, `/panel`).

## Warum

Das Ticketsystem braucht heute eine Aufgaben-Tabelle und zwei Dauerschleifen, damit Kanäle
umbenannt werden, und die Rechte stimmen nicht: jeder im Kanal kann schließen und wieder
öffnen, die vorhandenen Einstellungen dazu werden nie geprüft. Dazu kommen verlorener
Button-Zustand nach Neustart, doppelte Ticketnummern, ein anfälliger Start und eine stumme
Obergrenze von 50 Kanälen.

## Ziele

1. Keine Aufgaben-Tabelle und keine Warteschlange mehr. Ein Klick wirkt sofort.
1. Rechte sind eindeutig, an einer Stelle festgelegt und getestet.
1. Der Zustand eines Tickets steht in der Datenbank; Buttons und Kanalname folgen ihm, auch
   nach einem Neustart.
1. Bestehende Tickets, Kategorien und Staff-Rollen laufen ohne Zutun weiter.
1. Neu: Anliegen beim Öffnen, feste Nachricht mit „Open ticket"-Button, Protokoll beim Löschen.
1. Alle Einstellungen über `/panel`.

## Nicht-Ziele

- Tickets als Threads (verworfen, siehe Ansätze).
- Mehrere Ticket-Arten oder Formulare je Art.
- Web-Panel. Die Fachschicht bleibt aber ohne Discord-Abhängigkeit.

## Was auf keinen Fall passieren darf

- Bestehende offene Tickets verlieren ihre Buttons.
- Ein Ersteller kann sein geschlossenes Ticket trotz Verbot wieder öffnen oder ein Ticket löschen.
- Ein Ticket-Kanal entsteht, ohne dass das Ticket gespeichert ist (oder umgekehrt bleibt ein
  Datensatz ohne Kanal zurück).

## Ansätze

|       | Ansatz                                                                           | Abwägung                                                                                                                       |
| ----- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **A** | Kanäle behalten, Status nicht mehr über die Warteschlange in den Namen schreiben | Kein Umbau für Server; 50er-Grenze je Kategorie bleibt, wird aber sauber gemeldet                                              |
| B     | Private Threads                                                                  | Keine Grenze, Archiv eingebaut; anderer Ablauf fürs Team, Rechte je Ticket kaum steuerbar, Alt-Tickets müssten parallel laufen |
| C     | Warteschlange behalten und nur aufräumen                                         | Löst den Hauptkritikpunkt nicht                                                                                                |

**Gewählt: A**, mit der Vorgabe, dass der Kanalname offen/geschlossen erkennen lässt
(Entscheidung von Geuthur, 2026-11-15).

## Ablauf

**Öffnen.** Über `/ticket open` oder den Button „Open ticket" erscheint ein Formular mit
Betreff (Pflicht, bis 100 Zeichen) und Beschreibung (optional). Der Bot prüft: Modul aktiv,
Kategorie und Staff-Rollen gesetzt, Kategorie nicht voll, Ersteller unter seinem Limit offener
Tickets. Dann entsteht der Kanal `ticket-0042-name`, sichtbar für Ersteller, Staff-Rollen und
Bot. Die erste Nachricht nennt Betreff, Beschreibung und Ersteller, erwähnt die Staff-Rollen
und trägt die Buttons.

**Status-Nachricht.** Diese erste Nachricht ist die verbindliche Anzeige:

```
🎫 Ticket #0042 – Login problem
Status: 🟢 Open · Claimed by: @Mod · Created by: @User

[ 🛠️ Claim ] [ 🔒 Close ] [ 🔓 Reopen ] [ 🗑️ Delete ]
```

Sie wird bei jedem Klick sofort angepasst. Aktiv sind nur die Buttons, die im aktuellen
Zustand Sinn ergeben.

**Kanalname.** `ticket-0042-name` solange offen, `closed-0042-name` wenn geschlossen. Mehr
steht nicht im Namen; übernommen/nicht übernommen zeigt die Status-Nachricht. Umbenannt wird
direkt beim Schließen und Wiederöffnen, im Hintergrund, damit der Klick nicht wartet. Discord
erlaubt zwei Umbenennungen je Kanal in zehn Minuten; wird öfter hin- und hergeschaltet, holt
der Bot den Namen nach, sobald Discord es zulässt. Die stündliche Prüfung (siehe Archiv)
gleicht Namen ab, die nach einem Neustart noch nicht stimmen. Es gibt dafür keine Tabelle.

**Schließen.** Der Ersteller kann nicht mehr schreiben, der Kanal bleibt für ihn lesbar.

**Archiv.** Eine stündliche Prüfung verschiebt Tickets, die länger als die eingestellte Zahl
von Tagen geschlossen sind, in die Archiv-Kategorie – nur wenn eine gesetzt ist und Platz hat.
Wiederöffnen holt ein archiviertes Ticket in die Ticket-Kategorie zurück.

**Löschen.** Nach Rückfrage („Delete this ticket? This cannot be undone.") schreibt der Bot,
falls ein Log-Kanal gesetzt ist, ein Protokoll als Textdatei dorthin (Nachrichten mit Zeit und
Autor, dazu Nummer, Betreff, Ersteller, wer geschlossen und gelöscht hat) und löscht dann
Kanal und Datensatz.

## Rechte

Staff ist, wer eine der eingestellten Staff-Rollen hat. Admin ist, wer den Server besitzt oder
„Server verwalten" hat; Admins gelten auch als Staff.

| Aktion       | Ersteller                    | Staff | Admin |
| ------------ | ---------------------------- | ----- | ----- |
| Übernehmen   | nein                         | ja    | ja    |
| Schließen    | nur wenn `allow_user_close`  | ja    | ja    |
| Wiederöffnen | nur wenn `allow_user_reopen` | ja    | ja    |
| Löschen      | nein                         | nein  | ja    |

Wer keine der drei Rollen hat, darf nichts. Ist ein Staff-Mitglied selbst der Ersteller, gelten
für ihn die Staff-Rechte, außer beim Übernehmen des eigenen Tickets. Die Tabelle steht als
eine Funktion in der Fachschicht; jede Aktion prüft Recht und Zustand dort, nicht in den Buttons.

## Technik

- **Fachschicht** `demolizzen/services/tickets.py` ohne Discord: Rechte, Zustandswechsel,
  Nummernvergabe, Limits, Fälligkeit fürs Archiv, erwarteter Kanalname, Einstellungen.
- **Ticketnummer:** wird in einer Transaktion mit Sperre auf den Einstellungen vergeben. Schlägt
  das Anlegen des Kanals danach fehl, bleibt eine Lücke in der Nummerierung, aber kein Datensatz.
- **Buttons ohne Laden beim Start:** eine einzige dauerhafte Ansicht mit festen Kennungen
  (`ticket:claim`, `ticket:close`, `ticket:reopen`, `ticket:delete`, `ticket:open`), einmal beim
  Laden des Cogs registriert. Das Ticket wird beim Klick über den Kanal gefunden.
- **Alt-Tickets:** Klicks auf Buttons mit den bisherigen Kennungen (`claim:<guild>:<nr>` usw.)
  werden erkannt und gleich behandelt; beim ersten Klick bekommt die Nachricht die neuen Buttons.
- **Modul-Schalter:** Buttons, Formular und die stündliche Prüfung beachten ihn.
- **Datenbank** (eine Migration):
  - `GuildTicket`: neu `subject`, `control_message_id`.
  - `GuildTicketSettings`: neu `log_channel_id`, `max_open_tickets` (Standard 1).
  - `GuildTicketTask` entfällt samt Tabelle. Sie enthält nur offene Umbenennungs-Aufträge.
- **Entfällt:** `_ticketprocess.py`, das Laden aller Tickets in `on_ready`.

## Einstellungen im Panel

Im `/panel` erscheint bei gewähltem Modul „Ticket System" ein Button „Settings". Module melden
ihre Einstellungsseite beim Panel an; das Panel kennt die Module nicht einzeln.

- **Channels:** Ticket-Kategorie, Archiv-Kategorie, Log-Kanal
- **Staff & permissions:** Staff-Rollen, Ersteller darf schließen, Ersteller darf wiederöffnen
- **Limits:** Tage bis zum Archiv, offene Tickets je Mitglied
- **Post ticket button:** setzt die Nachricht mit „Open ticket" in den aktuellen Kanal

Die Befehle unter `/ticket_config` entfallen.

## Tests

Fachschicht vollständig gegen SQLite: jede Zelle der Rechte-Tabelle, jeder Zustandswechsel
einschließlich der unzulässigen, Nummernvergabe, Limit, Archiv-Fälligkeit. Buttons, Formular,
Alt-Kennungen, Protokoll und Einstellungsseite mit nachgebautem Discord-Kontext.

## Dem Umsetzenden überlassen

Namen, Aufbau der Embeds, Zeilenformat des Protokolls, Aufteilung der Einstellungsseite auf
Unterseiten (Discord erlaubt fünf Zeilen mit Bedienelementen je Nachricht).

## Offene Annahmen (von Claude gesetzt, bitte prüfen)

- Löschen dürfen nur Admins; Staff ohne „Server verwalten" nicht.
- Standard: ein offenes Ticket je Mitglied, einstellbar.
- Ohne Log-Kanal wird ohne Protokoll gelöscht.
- Die Befehle `/ticket_config …` entfallen zugunsten des Panels.
- Der Kanalname zeigt nur offen/geschlossen, nicht wer übernommen hat.
- Geschlossene Tickets bleiben für den Ersteller lesbar.
