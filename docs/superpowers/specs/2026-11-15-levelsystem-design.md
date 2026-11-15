# Design: Levelsystem

Stand: 2026-11-15 · Branch: `development` · Status: freigegeben (Geuthur, 2026-11-15)

## Warum

Bei jedem Level-Up und jedem `/rank` lädt der Bot Avatar, Hintergrund und Rahmen mit einer
blockierenden Abfrage ohne Zeitlimit und rendert das Bild in der Event-Loop. Solange steht der
ganze Bot still. XP werden gelesen, im Speicher erhöht und zurückgeschrieben; Nachrichten in
schneller Folge überschreiben sich. Vor jeder XP-Entscheidung laufen zwei Abfragen, auch wenn
der Würfel danach „keine XP" sagt. `/rank` für ein Mitglied ohne Profil endet im allgemeinen
Fehler.

## Ziele

1. Der Bot blockiert nie beim Erzeugen eines Bildes: Laden asynchron mit Zeitlimit und
   Größengrenze, Rendern außerhalb der Event-Loop.
1. XP gehen nicht verloren: eine Datenbank-Anweisung je Vergabe.
1. Nachrichten ohne XP kosten keine Datenbankabfrage.
1. Regeln (Level-Formel, XP je Nachricht) liegen in `demolizzen/services/levels.py`, getestet.
1. Die Einstellungen des Levelsystems liegen im `/panel`.

## Nicht-Ziele

- Aussehen der Karten, Level-Formel oder XP-Werte ändern.
- Eigene Hintergründe oder Rahmen für Mitglieder einstellbar machen.

## Was auf keinen Fall passieren darf

- Bestehende XP oder Level ändern sich durch das Update.
- Ein langsamer oder riesiger Bild-Download hält den Bot auf.

## Ansätze

|       | Ansatz                                                                                                  | Abwägung                                                    |
| ----- | ------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| **A** | Fachschicht für XP/Level, asynchroner Lader mit Zwischenspeicher, Rendern im Thread, Zeichencode bleibt | Behebt Blockade und XP-Verlust, Karten sehen aus wie bisher |
| B     | Karten durch Embeds ohne Bild ersetzen                                                                  | Am einfachsten, aber die Karten sind ein sichtbares Merkmal |
| C     | Nur `requests` in einen Thread schieben                                                                 | Bot blockiert nicht mehr, XP-Verlust und Abfragen bleiben   |

**Gewählt: A.**

## Verhalten

- **XP:** Für eine Nachricht in einem Server wird zuerst gewürfelt (`XP_CHANCE`), dann die Menge
  bestimmt (`XP_TYPE`), dann gebucht. Bots und Direktnachrichten bekommen nichts.
- **Level-Up:** Steigt das Level, kommt die Karte in den Hauptkanal (sonst Systemkanal), wenn der
  Server die Ankündigung nicht abgeschaltet hat und der Bot dort schreiben darf.
- **Bilder:** höchstens 10 Sekunden je Download und 8 MB je Bild. Feste Bilder (Hintergründe,
  Rahmen) werden zwischengespeichert, Avatare nicht. Schlägt ein Bild fehl, fällt die Karte aus;
  XP und Level sind trotzdem gebucht.
- **`/rank`:** Mitglied ohne Profil → `… is not registered in the leveling system.`
- **Panel:** Seite „Levelsystem" mit „Level up posts: On/Off" und Auswahl des Kanals für
  Ankündigungen. `/levelsystem_config set-mention` entfällt.

## Technik

- `services/levels.py`: `level_for`, `xp_for_level`, `progress`, `message_xp`, `add_xp`,
  `get_card_data`, `leaderboard`, Einstellungen.
- `cogs/levelsystem/_cards.py`: `AssetLoader` und die beiden Zeichenfunktionen; ersetzt
  `_functions.py`. Kein `requests` mehr in den Cogs.
- `add_xp`: `UPDATE … SET experience = experience + n`; nur wenn kein Profil existiert, wird es
  angelegt.
