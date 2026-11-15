# Design: Bank

Stand: 2026-11-15 · Branch: `development` · Status: freigegeben (Geuthur, 2026-11-15)

Baut auf dem Fundament (Fachschicht, `BaseCog`, `/panel`, Einstellungsseiten) auf.

## Warum

Jeder Bank-Befehl liest den Kontostand, rechnet im Speicher und schreibt zurück. Zwei
gleichzeitige Befehle überschreiben sich, Geld geht verloren oder verdoppelt sich. Der Zinssatz
wird als Prozentzahl gespeichert, aber als Faktor verrechnet (5 → 500 %). Die Zinsauszahlung
überschreibt Buchungen, die währenddessen passieren. `/bank create` schlägt immer fehl,
Admin-Befehle stürzen bei Mitgliedern ohne Profil ab, und `allow_deposits` /
`allow_withdrawals` werden nie geprüft.

## Ziele

1. Jede Buchung läuft in der Datenbank unter Sperre; gleichzeitige Befehle können kein Geld
   erzeugen oder vernichten.
1. Alle Bank-Regeln stehen in `demolizzen/services/bank.py` ohne Discord und sind getestet.
1. Der Zinssatz ist eindeutig: Prozent pro Woche, höchstens 10 %.
1. Einstellungen (Zinssatz, Ein- und Auszahlungen erlauben) über `/panel`.

## Nicht-Ziele

- Games, Shop und Economy umstellen. Sie nutzen die neuen Buchungen, wenn sie an der Reihe sind;
  bis dahin bleibt dort das Risiko gleichzeitiger Befehle.
- Neue Bank-Funktionen (Kredite, Kontoauszüge, Limits).

## Was auf keinen Fall passieren darf

- Bestehende Kontostände ändern sich durch das Update.
- Ein Server zahlt nach dem Update andere Zinsen als bisher, außer er hatte einen Wert ab 1
  gespeichert (der bisher als Faktor wirkte und jetzt als Prozent gilt).
- Ein Kontostand wird negativ.

## Ansätze

|       | Ansatz                                                                               | Abwägung                                                                        |
| ----- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------- |
| **A** | Buchungen als Funktionen der Fachschicht, jede in einer Transaktion mit Zeilensperre | Sicher, testbar, vom Web-Panel nutzbar                                          |
| B     | Bestehende Befehle einzeln mit Sperren flicken                                       | Regeln bleiben über acht Dateien verstreut                                      |
| C     | Buchungsjournal (jede Bewegung als Zeile, Stand als Summe)                           | Nachvollziehbar, aber neues Schema und Umbau aller Leser; für Spielgeld zu viel |

**Gewählt: A.** B löst die Verstreuung nicht, C ist für den Zweck zu schwer.

## Verhalten

- **Konto:** entsteht automatisch beim ersten Bank-Befehl eines Mitglieds, auch für den Empfänger
  einer Überweisung oder Gutschrift. `/bank create` entfällt.
- **Beträge:** ganze Zahlen ab 1 und höchstens 1 000 000 000 000 je Buchung.
- **`/bank deposit`** Wallet → Bank, **`/bank withdraw`** Bank → Wallet; beide nur, wenn der
  Server es erlaubt und genug Geld da ist.
- **`/bank send`** Wallet → Wallet eines anderen Mitglieds; nicht an sich selbst, nicht an Bots.
- **`/bank_admin give-money`**, **`remove-money`** (zieht höchstens ab, was da ist),
  **`remove-bank`** (setzt beide Stände auf 0) wie bisher, ohne Absturz bei fehlendem Profil.
- **Zinsen:** einmal pro Woche je Server auf den Bank-Stand, abgerundet auf ganze Coins, als eine
  einzige Datenbank-Anweisung. Geprüft wird alle sechs Stunden, ob ein Server fällig ist; nur
  Server mit aktivem Bank-Modul.
- **Zinssatz:** wird als Anteil gespeichert (0.001 = 0,1 %). Eine Migration rechnet gespeicherte
  Werte ab 1 als Prozent um (5 → 0.05) und begrenzt sie auf 0.10; Werte unter 1 bleiben
  unverändert. Neu einstellbar sind 0 bis 10 %.
- **Panel:** Einstellungsseite „Banksystem" mit Zinssatz, „Deposits" und „Withdrawals" an/aus.
  Die Befehle unter `/bank_config` entfallen.

## Technik

- `services/bank.py`: `ensure_account`, `get_balance`, `deposit`, `withdraw`, `transfer`,
  `credit`, `debit`, `reset`, `get_settings`, `update_settings`, `pay_interest`, `due_guild_ids`.
- Sperren: `select_for_update` in einer Transaktion; bei Überweisungen werden beide Konten in
  fester Reihenfolge gesperrt.
- Cogs `Bank` und `BankAdmin` rufen nur die Fachschicht auf; die Zins-Schleife zieht ins
  `Bank`-Cog; `banksystem_config.py` entfällt.
- Fehler der Fachschicht tragen den Text für den Nutzer.

## Tests

Fachschicht vollständig gegen SQLite und MySQL: jede Buchung mit Erfolg und jeder Ablehnung,
Reihenfolge der Sperren, Zinsen (Fälligkeit, Rundung, gesperrtes Modul), Migration der Zinssätze.
Cogs und Einstellungsseite mit nachgebautem Discord-Kontext.

## Offene Annahmen (von Claude gesetzt)

- Überweisungen und Gutschriften legen beim Empfänger automatisch ein Konto an.
- Höchstbetrag je Buchung 1 000 000 000 000.
- Die Zinsprüfung läuft alle sechs Stunden statt einmal pro Woche ab Bot-Start.
