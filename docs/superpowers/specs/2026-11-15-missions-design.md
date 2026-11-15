# Design: Daily, Work und Missionen

Stand: 2026-11-15 · Branch: `development` · Status: freigegeben (Geuthur, 2026-11-15: „offene Punkte beheben")

Baut auf `2026-11-15-economy-money-design.md` auf und schließt dessen offene Punkte.

## Warum

`/daily`, `/work` und die Missionen prüfen ihren Cooldown im Cog auf einem geladenen Objekt und
buchen danach. Zwei gleichzeitige Befehle kommen beide durch. Bei Missionen reicht es,
`/mission start` mehrfach abzuschicken: jede der Nachrichten mit Buttons zahlt die Mission
einzeln aus. Außerdem würfelt die Mission für Buchung und Bericht getrennt, sodass der Bericht
einen Verlust erzählen kann, während ein Gewinn gebucht wird. `/use` zeigt die Trink-Texte nie,
weil es auf den Typ `drink` prüft, der Shop aber `drinks` speichert.

## Ziele

1. Cooldown prüfen, Zustand ändern und Geld buchen sind je Befehl eine Transaktion unter Sperre.
1. Eine Mission wird genau einmal abgerechnet, egal wie viele Nachrichten offen sind.
1. Ausgang und Bericht einer Mission stimmen überein.
1. Die Regeln liegen in `demolizzen/services/missions.py` ohne Discord und sind getestet;
   `models/user.py` braucht kein `discord` mehr.

## Nicht-Ziele

- Spielwerte ändern (Auszahlungen, Chancen, Cooldowns, Texte).
- Die Texte und Buttons aus den Cogs nehmen; sie bleiben dort.

## Was auf keinen Fall passieren darf

- Eine Mission, ein Arbeitstag oder ein Daily wird doppelt ausgezahlt.
- Laufende Missionen oder Cooldowns bestehender Spieler gehen durch das Update verloren.

## Ansätze

|       | Ansatz                                                                          | Abwägung                                                            |
| ----- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| **A** | Regeln und Zustandswechsel in die Fachschicht, Texte und Buttons bleiben im Cog | Schließt die Wettläufe, Regeln werden testbar, überschaubarer Umbau |
| B     | Auch Texte und Ablauf der Buttons neu bauen                                     | Kein zusätzlicher Nutzen für die Fehler, viel Risiko ohne Tests     |

**Gewählt: A.**

## Verhalten

- **Daily:** einmal pro Tag; Auszahlung und Streak wie bisher.
- **Work:** erster Aufruf beginnt die Schicht, spätere Aufrufe nach Ablauf zahlen aus und beginnen
  die nächste.
- **Mission:** `/mission start` beginnt die erste Mission oder zeigt nach Ablauf den Bericht mit
  Buttons. Der erste Klick (oder der Ablauf der Buttons) rechnet ab und beginnt die nächste
  Mission. Jede weitere offene Nachricht derselben Mission antwortet
  `This mission has already been reported.` und bucht nichts.
- **Ausgang:** wird einmal bestimmt; der Bericht folgt ihm.
- **Schiffskauf:** Preis abziehen und Schiff zuweisen sind eine Transaktion.
- **Test-Konten:** die beiden bisher fest im Code stehenden Konten mit 10-Sekunden-Cooldown in
  zwei Servern bleiben erhalten und stehen jetzt in `config.py`.
- **`/use`:** Trink-Texte erscheinen für Getränke.

## Technik

- `services/missions.py`: `claim_daily`, `work`, `begin`, `settle`, `cancel`, `buy_ship`,
  `resolve` (reine Funktion für den Ausgang), Cooldown-Helfer.
- Abrechnung: `settle` bekommt den Startzeitpunkt der Mission, die die Nachricht zeigt. Stimmt er
  nicht mehr mit dem gespeicherten überein, wurde bereits abgerechnet.
- `UserProfile.get_cooldown` entfällt.
