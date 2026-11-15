# Design: Fundament, Cog-Schalter pro Guild und Panel

Stand: 2026-11-15 · Branch: `development` · Status: Entwurf, wartet auf Freigabe

## Warum

Der Bot ist heute schwer zu erweitern und praktisch nicht testbar (1 Test, 27 % Abdeckung).
Discord-Logik, Datenbankzugriffe und Fachlogik stehen gemischt in den Cogs, und der Bot
startet sich im Konstruktor selbst. Außerdem soll jede Guild selbst entscheiden können,
welche der angebotenen Cogs bei ihr aktiv sind – bedient über ein Panel im Bot, später
zusätzlich über ein Web-Panel.

Dieses Dokument deckt die **erste Etappe** ab. Das Ticketsystem bekommt danach ein eigenes
Design, das auf dieser Etappe aufbaut.

## Ziele

1. Fachlogik liegt in einer eigenen Schicht ohne Discord-Abhängigkeit und ist mit SQLite testbar.
2. Der Bot lässt sich in Tests erzeugen, ohne Netzwerk, Token oder laufende Event-Loop.
3. Guild-Admins schalten Cogs für ihre Guild über `/panel` an und ab.
4. Ein neues Cog hinzuzufügen heißt: eine Klasse von `BaseCog` ableiten, einen Eintrag
   im Verzeichnis der angebotenen Cogs machen – Schalter und Panel funktionieren dann von selbst.

## Nicht-Ziele (dieser Etappe)

- Web-Panel. Die Schicht aus Ziel 1 wird aber so gebaut, dass es sie später unverändert nutzt.
- Befehle abgeschalteter Cogs in Discord ausblenden. Sie bleiben sichtbar und antworten mit einem Hinweis.
- Umbau des Ticketsystems (eigenes Design) und der übrigen Cogs (folgen einzeln, siehe Reihenfolge).
- Die privaten, derzeit nicht geladenen Cogs `geuthur`, `vow`, `token`, `automod`.
- Änderungen am Schema bestehender Tabellen.

## Was auf keinen Fall passieren darf

- Bestehende Guilds verlieren nach dem Update Funktionen: ohne eigenes Zutun bleibt bei ihnen alles aktiv.
- Der Bot ist zwischen zwei Schritten nicht lauffähig.
- Daten bestehender Guilds gehen verloren oder werden umgedeutet.

## Ansätze

| | Ansatz | Abwägung |
|---|---|---|
| **A** | Schrittweise im bestehenden Bot: Fachlogik in eine eigene Schicht, Cogs werden dünn, Umzug Cog für Cog | Bot bleibt lauffähig; eine Zeit lang alter und neuer Stil nebeneinander |
| B | Neuaufbau daneben | Sauberstes Ergebnis, aber lange nichts lauffähig und ohne Tests kein Schutz vor verlorenem Verhalten |
| C | Nur Panel und Ticketsystem aufsetzen | Am schnellsten, löst „schwer erweiterbar, nicht testbar" nicht |

**Gewählt: A** (Entscheidung von Geuthur, 2026-11-15).

## Aufbau

```
demolizzen/
  core/
    bot.py        Demolizzen: Konstruktor setzt nur Zustand
    cog.py        BaseCog: gemeinsame Basis aller Cogs
    registry.py   Verzeichnis der angebotenen Cogs
    errors.py     CogDisabled (für Discord sichtbarer Fehler)
  services/       Fachlogik ohne discord-Import
    errors.py       Fehler der Fachschicht
    guilds.py       Guild anlegen, umbenennen, entfernen, Mitglieder abgleichen
    cog_settings.py Cogs pro Guild abfragen und schalten
  cogs/panel/     /panel und seine Ansichten
  tests/
    services/     Tests gegen SQLite
    core/         Bot-Start, BaseCog, Schalter
    cogs/         dünne Cog-Tests mit nachgebautem Discord-Kontext
    helpers.py    Nachbauten für ctx, Guild, Member
```

**Regel:** `services/` importiert nie `discord`. Cogs enthalten keine `.objects.`-Zugriffe mehr,
sobald sie umgezogen sind.

### Bibliothek

Der Bot läuft auf **py-cord** (geprüft an 2.8.1), nicht auf discord.py. Für diese Etappe heißt das:
kein `setup_hook` (Ressourcen entstehen in einem überschriebenen `start()`), der Schalter hängt an
`cog_check`, das py-cord auch für Slash-Befehle auswertet, und der Hinweis an den Nutzer muss ein
`discord.ext.commands.CheckFailure` sein – den anderen `CheckFailure` aus `discord.errors`
verschluckt der Bot heute stumm. Details stehen im Umsetzungsplan.

### Bot-Start

Heute lädt `Demolizzen.__init__` die Cogs, öffnet die HTTP-Session und ruft `start()` selbst
auf; `launch.py` ruft danach zusätzlich `bot.run()`. Neu:

- `__init__` setzt nur Intents und Zustand.
- `load_extensions()` lädt die Cogs aus der Konfiguration und meldet Fehler pro Cog.
- HTTP-Session, ESI-Client und Hintergrundaufgabe entstehen erst beim Start in der laufenden Loop.
- `launch.py` baut den Bot, lädt die Cogs und startet ihn.
- Das nicht vorhandene Cog `test` fliegt aus `PRELOAD_EXTENSIONS`.

### BaseCog und Verzeichnis

Jedes Cog bekommt einen Schlüssel (`ticket`, `bank`, …). Mehrere Klassen eines Moduls teilen
sich einen Schlüssel (z. B. `Bank`, `BankConfig`, `BankAdmin` → `bank`). Das Verzeichnis führt
je Schlüssel: Titel, Kurzbeschreibung, ob abschaltbar, ob standardmäßig aktiv.

Nicht abschaltbar: `core`, `owner`, `guild`, `panel`. Alle anderen geladenen Cogs sind abschaltbar
und standardmäßig aktiv.

### Cog-Schalter

- **Speicher:** die vorhandenen, bisher ungenutzten Felder `GuildSettings.disabled_cogs` und
  `enabled_cogs` (Listen von Schlüsseln). Keine Migration nötig.
  Aktiv ist ein Cog, wenn es standardmäßig aktiv und nicht in `disabled_cogs` steht, oder wenn es in
  `enabled_cogs` steht. Leere Felder bedeuten also: alles wie bisher.
- **Befehle:** `BaseCog` prüft vor jedem Befehl, ob das Cog in der Guild aktiv ist. Wenn nicht,
  Antwort nur für den Aufrufer: „This module is disabled on this server."
- **Events:** Listener abgeschalteter Cogs tun nichts. `BaseCog` stellt dafür einen Listener-Dekorator
  bereit, der die Guild aus dem Event liest.
- **Hintergrundschleifen** (Killmails, Zinsen, Shop): fragen die Fachschicht nach den Guilds, in
  denen das Cog aktiv ist. Wird beim Umzug des jeweiligen Cogs eingebaut; bis dahin wirkt der
  Schalter bei diesen Cogs nur auf Befehle und Events.
- **Zwischenspeicher:** Einstellungen pro Guild werden kurz im Speicher gehalten (Richtwert 60 s)
  und beim Schalten über den Bot sofort verworfen. Die Frist sorgt dafür, dass später auch
  Änderungen aus dem Web-Panel ohne Neustart ankommen.
- **Abhängigkeiten:** Das Verzeichnis führt je Cog, welche anderen es braucht. Derzeit brauchen
  `economy`, `shop` und `games` die Bank (`banksystem`). Die Fachschicht verweigert das Abschalten
  eines Cogs, solange abhängige Cogs aktiv sind, und das Anschalten, solange ein benötigtes Cog aus
  ist. Das Panel fragt in diesem Fall nach („Disabling Bank will also disable: Economy, Shop, Games")
  und schaltet nach Bestätigung alle Betroffenen gemeinsam (Entscheidung von Geuthur, 2026-11-15).
- **Wer darf schalten:** Guild-Owner und Mitglieder mit „Server verwalten" – die bestehende
  Admin-Prüfung.

### Panel

`/panel` zeigt eine nur für den Aufrufer sichtbare Nachricht:

```
⚙️ Demolizzen Panel – <Guild>

🟢 Level System      🟢 Bank
🟢 Economy           🔴 Games
🟢 EVE Online        🟢 Killmail
🟢 Ticket System     …

[ Modul wählen ▾ ]
[ Aktivieren ]  [ Deaktivieren ]
```

Auswahl eines Moduls zeigt dessen Beschreibung und Zustand; die Buttons schalten und zeichnen
die Übersicht neu. Texte bleiben wie im restlichen Bot englisch. Einstellungsseiten pro Modul
(Ticket-Kategorie, Bank-Zinsen usw.) kommen jeweils mit dem Umzug des Moduls dazu; das Panel
sieht dafür eine Erweiterungsstelle vor.

## Tests

- `services/` vollständig gegen SQLite getestet; Richtwert ≥ 90 % Abdeckung dieser Module.
- Bot-Start, `BaseCog`, Schalter und Panel-Logik mit nachgebautem Discord-Kontext getestet.
- `testenv/settings.py`: `USE_MYSQL` wertet künftig den Wert aus (`1/true` = MySQL, sonst SQLite).
  Die CI-Einstellung wird entsprechend gesetzt, damit CI weiter gegen MySQL läuft.
- Jeder Schritt endet mit grünen Tests.

## Reihenfolge

1. Testgerüst und Reparatur des `USE_MYSQL`-Schalters
2. Bot-Start entflechten
3. `services/guilds.py`, Cog `guild` als erstes dünnes Cog (Pilot)
4. `registry`, `BaseCog`, `services/cog_settings.py`, Schalter für Befehle und Events
5. `/panel`
6. Danach, je eigener Schritt: Ticketsystem (eigenes Design), Bank, Levelsystem, Economy/Shop/Games,
   EVE Online/Killmail

## Dem Umsetzenden überlassen

Genaue Namen von Klassen und Funktionen, Aufbau der Test-Nachbauten, genaue Zwischenspeicher-Frist,
Gestaltung der Embeds im Panel.

## Offene Annahmen (von Claude gesetzt, bitte prüfen)

- Nicht abschaltbar sind genau `core`, `owner`, `guild`, `panel`.
- Neue und bestehende Guilds starten mit allen Cogs aktiv.
- Schalten darf, wer „Server verwalten" hat oder Owner ist.
- Abgeschaltete Befehle bleiben sichtbar und antworten mit einem Hinweis.
- Bei Cogs mit Hintergrundschleifen wirkt der Schalter auf die Schleife erst nach deren Umzug.
