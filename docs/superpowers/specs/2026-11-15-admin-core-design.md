# Design: Verwaltungs- und Grundmodule

Stand: 2026-11-15 · Branch: `development` · Status: freigegeben (Geuthur, 2026-11-15)

Betrifft: Admin, Owner, Core, General, Commands und das Economy-Event.

## Warum

- Das Economy-Event liegt nur im Arbeitsspeicher und startet mit Faktor 0: eingeschaltet ohne
  gesetzten Faktor zahlen erfolgreiche Missionen und `/work` 0 Coins, ein negativer Faktor zieht
  Geld ab. Nach einem Neustart ist das Event weg.
- `/help`, `/bag`, `/richest`, `/use` und `/spenden` verlangen `/auth register`, obwohl Profile
  sonst überall bei Bedarf entstehen.
- `/owner force-deposits-update` und `force-ship-update` rufen Funktionen auf, die es nicht mehr
  gibt. `/owner status` bricht in Direktnachrichten ab. `/owner migrate` blockiert den Bot bis zu
  60 Sekunden.
- `/moderation clear` antwortet nie, wenn das Lesen der Nachrichten fehlschlägt; die Meldung bei
  leerem Ergebnis sagt das Gegenteil des Gemeinten.
- Die Statusanzeige bleibt nach einem einzigen Datenbankfehler bis zum Neustart rot.
- `/bag` zeigt bei leerem Rucksack eine leere Nachricht und scheitert ab 26 Items. `/richest` lädt
  alle Konten in den Speicher und verändert die Schreibweise der Namen.
- Keines dieser Module hat Tests.

## Ziele

1. Das Event wird pro Server gespeichert und über `/panel` eingestellt; der Faktor ist immer
   sinnvoll.
1. Grundbefehle funktionieren ohne Registrierung.
1. Jeder Befehl antwortet; kein Owner-Befehl blockiert den Bot.
1. Die Statusanzeige folgt dem tatsächlichen Zustand.

## Nicht-Ziele

- Die nicht geladenen Module `geuthur`, `automod`, `token`, `vow`.
- Neue Moderationsfunktionen, anderes Aussehen der Nachrichten.

## Was auf keinen Fall passieren darf

- Ein Event verringert eine Auszahlung.
- Ein Server sieht oder ändert das Event eines anderen.

## Ansätze

|       | Ansatz                                                                              | Abwägung                                                  |
| ----- | ----------------------------------------------------------------------------------- | --------------------------------------------------------- |
| **A** | Event in die Datenbank und ins Panel, Befehle `/admin economy …` entfallen          | Einheitlich mit Bank, Tickets, Levelsystem; eine Migration |
| B     | Event in der Datenbank, Befehle bleiben                                             | Zwei Bedienwege für dieselbe Einstellung                  |
| C     | Nur den Faktor im Arbeitsspeicher absichern                                         | Event bleibt nach Neustart verloren                       |

**Gewählt: A.**

## Verhalten

- **Event:** pro Server `aktiv` (Standard aus) und `Faktor` 1 bis 10 (Standard 2). Einstellung auf
  der Economy-Seite in `/panel`: Schalter und Auswahl des Faktors. Auszahlungen werden mit dem
  Faktor multipliziert; verlorene Schiffe kosten während des Events nichts (wie bisher).
- **Grundbefehle:** Profil und Konto entstehen beim ersten Befehl. `/auth register` entfällt.
- **`/bag`:** leer → `Your Bag is empty... Buy something with </shop buy>`; höchstens 25 Items,
  darüber eine Zeile `… and N more`.
- **`/richest`:** Top 10 nach Wallet und Summe aller Wallets direkt aus der Datenbank; Namen
  unverändert.
- **`/moderation clear`:** 1 bis 100 Nachrichten der letzten 14 Tage. Antwortet immer: Anzahl
  gelöscht, nichts zu löschen, fehlendes Recht oder allgemeiner Fehler.
- **Owner:** `force-deposits-update` startet die Zinszahlung und nennt die Zahl der Server;
  `force-ship-update` entfällt; `migrate` läuft in einem Thread; `status` behält die aktuelle
  Aktivität auch in Direktnachrichten.
- **Statusanzeige:** jede Stunde neu bestimmt; grün, sobald die Datenbank antwortet.
- **Core:** Debug-Zeile und ungenutzte Changelog-Funktion entfallen.

## Technik

- `GuildEconomySettings` (`guild_economy_settings`, Migration `0014`): `event_active`,
  `event_factor`.
- `services/missions.py`: `Event`, `get_event`, `set_event`, `InvalidEventFactor`; `resolve`
  behandelt einen Faktor unter 1 als 1.
- `services/shop.py`: `get_bag`; `services/bank.py`: `richest`.
- `cogs/economy/_settings_page.py`: Seite im Panel. `config.EVENTS_SERVER` entfällt.
