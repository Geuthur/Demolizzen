# Design: Geld in Games, Shop und Economy

Stand: 2026-11-15 · Branch: `development` · Status: freigegeben (Geuthur, 2026-11-15)

Baut auf `2026-11-15-bank-design.md` auf.

## Warum

Games, Shop und Economy ändern Kontostände noch direkt auf geladenen Objekten. Gleichzeitige
Befehle können dort Geld verfälschen. Dazu kommen Fehler: `/shop buy` nimmt negative Mengen an
und schreibt dafür Geld gut, ein erfolgreicher `/gank` bucht die Beute nie um, `/games dice`
würfelt nur 1 bis 5 und meldet den einfachen statt den doppelten Gewinn, die Missions-Versicherung
kann das Wallet ins Minus ziehen, und mehrere Befehle verlangen ein Konto über den nicht mehr
vorhandenen Befehl `/bank create`.

## Ziele

1. Kein Cog ändert einen Kontostand selbst; jede Geldbewegung ist eine Buchung der Bank.
1. Kauf und Benutzen von Gegenständen liegen in einer Fachschicht; Bezahlen und Erhalten sind
   ein Schritt.
1. Die genannten Fehler sind behoben.
1. Konten entstehen automatisch.

## Nicht-Ziele

- Die Missions-Spiellogik (Cooldowns, Schiffswerte, Events) in die Fachschicht ziehen. Nur ihr
  Geld läuft über die Bank; der vollständige Umzug ist eine eigene Etappe.
- Spielregeln ändern, außer wo unten genannt.

## Was auf keinen Fall passieren darf

- Ein Befehl schreibt Geld gut, ohne dass die Regel es vorsieht (negative Mengen, doppelte
  Buchung).
- Ein Kontostand wird negativ.

## Ansätze

|       | Ansatz                                                                                     | Abwägung                                                        |
| ----- | ------------------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| **A** | Geldbewegungen auf Bank-Buchungen umstellen, Shop in eigene Fachschicht, Spiellogik bleibt | Schließt Exploits und Wettläufe mit überschaubarem Umbau        |
| B     | Alles (auch Missionen) vollständig in Fachschichten neu bauen                              | Sauberer, aber rund 900 Zeilen Spiellogik ohne Tests auf einmal |
| C     | Nur die Fehler einzeln flicken                                                             | Wettläufe bleiben                                               |

**Gewählt: A.**

## Verhalten

- **Slots, Dice:** Einsatz mindestens 1 und höchstens das Wallet. Verlust zieht den Einsatz ab,
  Gewinn schreibt den doppelten Einsatz gut; die Meldung nennt den gutgeschriebenen Betrag. Dice
  würfelt 1 bis 6.
- **Daily, Work:** Auszahlung als Gutschrift.
- **Gank:** Erfolg bucht die Beute vom Opfer zum Angreifer, Misserfolg umgekehrt. Nicht gegen
  sich selbst und nicht gegen Bots.
- **Missionen:** Auszahlung als Gutschrift; die Versicherung zieht höchstens ab, was im Wallet
  ist. Schiffskauf zieht den Preis ab und scheitert bei zu wenig Geld.
- **Shop:** Menge mindestens 1. Der Kauf prüft Geld, zieht den Preis ab und legt die Gegenstände
  ins Inventar – in einer Transaktion. `/use` verbraucht Gegenstände ebenso.
- **Konten:** Economy, Shop und Missionen legen Profil und Konto bei Bedarf an.

## Technik

- `services/bank.py` neu: `wager` (Einsatz mit Gewinn oder Verlust in einer Buchung) und
  `adjust` (Gutschrift oder Abzug höchstens bis null).
- `services/shop.py`: `buy`, `use_item`.
- Ein Test stellt sicher, dass kein Cog `wallet` oder `bank` zuweist.

## Offene Annahmen (von Claude gesetzt)

- Dice zahlt wie Slots den doppelten Einsatz und meldet ihn auch so.
- Ein Opfer ohne Konto bekommt eines mit Stand 0; der Gank findet dann nichts.
- Je Kauf höchstens 1000 Stück.
