# Design: EVE-Online-Cog und Preisabfrage

Stand: 2026-11-15 · Branch: `development` · Status: freigegeben (Geuthur, 2026-11-15)

## Warum

- Der Preis-Zwischenspeicher wird nie getroffen: gespeichert wird unter `jita`, gesucht unter dem
  langen Stationsnamen. Jeder Aufruf fragt den Preisdienst neu ab.
- Der Zwischenspeicher hat den Itemnamen als einzigen Schlüssel. Dasselbe Item für einen zweiten
  Handelsplatz endet in einem Datenbankfehler.
- Der Ablaufvergleich mischt Zeiten mit und ohne Zeitzone und bräche bei einem Treffer ab.
- Antwortet der Preisdienst nicht oder kennt er das Item nicht, zeigt der Bot `0 ISK` oder einen
  allgemeinen Fehler. Kein Zeitlimit, kein `defer`.
- Das Preislisten-Fenster wird von keinem Befehl geöffnet und ruft Funktionen auf, die es nicht
  gibt.
- `/eve status` schreibt bei Ausfall `Server Online 🔴`. Die Item-Vorschläge verlieren Treffer,
  wenn mehr als 50 Items den Suchtext enthalten.
- Der Cog hat keine Tests.

## Ziele

1. `/eve price` nutzt den Zwischenspeicher (30 Minuten) und funktioniert für jeden Handelsplatz.
1. Störungen und unbekannte Items ergeben eine klare Meldung, nie `0 ISK`.
1. Die Preislogik liegt getestet in der Fachschicht; die Anbindung an den Preisdienst ist ein
   kleiner, getesteter Baustein mit Zeitlimit.

## Nicht-Ziele

- Preislisten (mehrere Items auf einmal). Das tote Fenster wird entfernt; ein neuer Befehl wäre
  ein eigener Schritt.
- Anderer Preisdienst, anderes Aussehen der Nachrichten.

## Was auf keinen Fall passieren darf

- Ein Preis eines Handelsplatzes wird für einen anderen angezeigt.
- Ein Ausfall des Preisdienstes sieht aus wie ein Preis von 0 ISK.

## Ansätze

|       | Ansatz                                                                                             | Abwägung                                                   |
| ----- | -------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| **A** | Preislogik in die Fachschicht, Zwischenspeicher je Item und Handelsplatz, Anbindung als Baustein  | Behebt alle Punkte; Migration verwirft alte Cache-Einträge |
| B     | Nur die Vergleiche im Cog reparieren                                                               | Schlüssel-Fehler und fehlende Tests bleiben                |
| C     | Zwischenspeicher im Arbeitsspeicher statt in der Datenbank                                         | Keine Migration, aber nach jedem Neustart leer             |

**Gewählt: A.**

## Verhalten

- **Handelsplätze:** eine Zuordnung in der Fachschicht: Kurzname für den Preisdienst (`jita`),
  Anzeigename (`Jita`), Stationsname für die Überschrift wie bisher. Unbekannt oder leer: Jita.
- **Preis:** gültiger Eintrag im Zwischenspeicher → dieser. Sonst Abfrage beim Preisdienst
  (Zeitlimit 10 s), Ergebnis 30 Minuten gespeichert. Groß-/Kleinschreibung des Itemnamens ist
  egal; angezeigt wird der Name, den der Preisdienst liefert.
- **Kein Preis:** liefert der Dienst kein Item oder Verkauf und Ankauf sind beide 0:
  `No market price found for **<item>** in <hub>.` Nichts wird gespeichert.
- **Störung:** Zeitlimit, Verbindungsfehler, anderer Status als 200 oder unlesbare Antwort:
  `The price service did not answer for <hub>. Please try again later.`
- **Status:** bei Ausfall `Server Offline 🔴`; antwortet ESI nicht binnen 10 s, gilt das als
  Ausfall.
- **Vorschläge:** zuerst Items, die mit dem Suchtext beginnen, dann die übrigen, höchstens 10.

## Technik

- `services/prices.py`: `Tradehub`, `TRADEHUBS`, `tradehub(name)`, `Quote`, `Price`,
  `get_price(item_name, hub, fetch, now=None)`, `search_item_names(term, limit=10)`.
- `services/errors.py`: `PriceError`, `PriceNotFound`, `PriceUnavailable`.
- `cogs/eveonline/_appraisal.py`: `AppraisalClient(get_session).quotes(market, names)`.
  `utils/pricehandler.py` entfällt.
- `EvePricecache`: eigener Schlüssel, eindeutig je `item_name` und `tradehub` (Migration `0013`,
  legt die Tabelle neu an).

## Offen für den Betreiber

Die Seite des Preisdienstes führt Jita, Amarr, Dodixie und einige Nullsec-Märkte, aber weder Rens
noch Hek. Beide bleiben wählbar und ergeben im Zweifel die Störungsmeldung; ob sie entfernt
werden, entscheidet Geuthur nach einem Test.
