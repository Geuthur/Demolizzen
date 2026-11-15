# Geld in Games, Shop und Economy – Umsetzungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kein Cog ändert Kontostände mehr selbst; Shop-Käufe sind ein Schritt; die gefundenen Geld-Fehler sind behoben.

**Architecture:** Zwei neue Buchungen in `services/bank.py` (`wager`, `adjust`) und eine neue Fachschicht `services/shop.py`. Die Cogs behalten ihre Spiellogik und rufen für Geld und Gegenstände nur noch die Fachschicht auf.

**Tech Stack:** Python ≥ 3.11, py-cord 2.8.x, Django 5.2 (async ORM), Tests: `python runtests.py demolizzen --debug-mode`.

**Spec:** `docs/superpowers/specs/2026-11-15-economy-money-design.md`

## Global Constraints

- `demolizzen/services/**` importiert nie `discord`.
- Beträge und Einsätze: `1 ≤ n ≤ bank.MAX_AMOUNT`; Kaufmenge `1 ≤ n ≤ 1000`.
- Kein Kontostand und keine Gegenstandsmenge wird negativ.
- Gewinn bei Slots und Dice = doppelter Einsatz; die Meldung nennt diesen Betrag.
- Bot-Texte bleiben wie sie sind, außer wo ein Fehlertext der Fachschicht sie ersetzt.
- Jeder Commit lässt Tests grün (SQLite und `USE_MYSQL=1`) und den Bot startbar; `pre-commit run --all-files` läuft durch.

## Review Focus

1. Negative oder Null-Menge bei `/shop buy` und `/use`: abgelehnt, nichts gebucht. → Aufgabe 2
1. Kauf, bei dem das Geld nicht reicht: weder Geld noch Inventar ändern sich. → Aufgabe 2
1. Gank gegen Mitglied ohne Konto, gegen sich selbst, gegen Bot: kein Absturz, kein Geld bewegt. → Aufgabe 4
1. Missions-Versicherung größer als das Wallet: Wallet endet bei 0. → Aufgaben 1 und 4
1. Mitglied ohne Profil nutzt `/daily`, `/shop buy`, `/work`: funktioniert ohne „erst Konto anlegen". → Aufgaben 3 und 4

______________________________________________________________________

### Task 1: `wager` und `adjust`

**Files:** Modify `demolizzen/services/bank.py`; Create `demolizzen/tests/services/test_bank_games.py`

**Interfaces – Produces:**

- `async bank.wager(guild_id, user_id, user_name, stake, won: bool) -> Balance` – verlangt `wallet ≥ stake` (`InsufficientFunds`), bucht bei Gewinn `+2 × stake`, bei Verlust `−stake`

- `async bank.adjust(guild_id, user_id, user_name, delta: int) -> int` – `delta > 0` Gutschrift, `delta < 0` Abzug höchstens bis null, `0` nichts; Rückgabe = tatsächlich gebuchte Änderung; `|delta| ≤ MAX_AMOUNT`, sonst `InvalidAmount`

- [ ] **Step 1: Failing tests**

```text
wager: wallet 100, stake 30, won → 160; lost → 70; stake 101 → InsufficientFunds, unverändert
       stake 0, -1, True → InvalidAmount; Bank-Stand bleibt unberührt
adjust: +50 → 50 zurück, Stand 50; -30 bei 50 → -30; -80 bei 20 → -20, Stand 0; 0 → 0
        ±(MAX_AMOUNT + 1), True, "5" → InvalidAmount; legt Konto bei Bedarf an
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `feat: wager and adjust bookings`

### Task 2: Shop-Fachschicht

**Files:** Create `demolizzen/services/shop.py`, `demolizzen/tests/services/test_shop.py`; Modify `demolizzen/services/errors.py`

**Interfaces – Produces:**

- `errors.ShopError(ServiceError)` mit `.message`; Unterklassen `ItemNotFound`, `InvalidQuantity`, `ItemNotOwned`, `NotEnoughItems`

- `shop.MAX_QUANTITY = 1000`

- `shop.Purchase` – `@dataclass(frozen=True)`: `item_name: str`, `quantity: int`, `total_price: int`, `owned: int`

- `shop.ItemUse` – `@dataclass(frozen=True)`: `item_name: str`, `item_type: str`, `remaining: int`

- `async shop.buy(guild_id, user_id, user_name, item_name, quantity) -> Purchase` – Gegenstand ohne Beachtung der Groß-/Kleinschreibung, nur `active=True`; `ItemNotFound`, `InvalidQuantity`, `InsufficientFunds`; Geld und Inventar in einer Transaktion

- `async shop.use_item(guild_id, user_id, user_name, item_name, quantity) -> ItemUse` – `InvalidQuantity`, `ItemNotOwned`, `NotEnoughItems`

- [ ] **Step 1: Failing tests**

```text
buy:  wallet 100, Preis 30, Menge 2 → Purchase(…, 2, 60, 2), wallet 40; zweiter Kauf erhöht owned
      Menge 0, -5, 1001, True → InvalidQuantity, nichts geändert
      zu wenig Geld → InsufficientFunds, kein Inventar-Eintrag
      unbekannter oder inaktiver Gegenstand → ItemNotFound; "beer" findet "Beer"
      Mitglied ohne Profil → InsufficientFunds statt Absturz
use:  3 vorhanden, 2 benutzen → remaining 1; 4 → NotEnoughItems; unbekannt → ItemNotOwned
      Menge 0, -1 → InvalidQuantity; Menge bleibt unverändert
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `feat: shop service with atomic purchases`

### Task 3: Games und Shop umstellen

**Files:** Modify `demolizzen/cogs/games/games.py`, `demolizzen/cogs/shop/shop.py`, `demolizzen/cogs/commands/_economy.py`, `demolizzen/tests/cogs/test_games.py`; Create `demolizzen/tests/cogs/test_shop_cog.py`

**Interfaces – Consumes:** `bank.wager`, `shop.buy`, `shop.use_item`, `guilds.ensure_guild`, `bank.ensure_account`

- Slots und Dice: Grenzen des Cogs (`max_amount`) bleiben; Geld über `bank.wager`; `BankError` → dessen Text; Dice mit `random.randint(1, 6)`; Gewinnmeldung `You won {2 * amount} :coin:`

- `Shop.cog_before_invoke`: legt Guild und Konto an und lädt danach das Profil wie bisher; kein Verweis auf `/bank create`

- `/shop buy`: `shop.buy`; Fehlertexte wie bisher für „nicht gefunden" und „nicht genug Geld", `InvalidQuantity` mit dessen Text

- `/use`: `shop.use_item`; Erfolgstexte unverändert

- [ ] **Step 1: Failing tests**

```text
games: bestehende Slots-Tests bleiben grün; neu: Einsatz 0 abgelehnt; Dice gewinnt mit (6,6) gegen (1,1) → +2×,
       Meldung "You won 200 :coin:"; Dice verliert → −Einsatz; random.randint wird mit (1, 6) aufgerufen
shop:  Kauf zieht Geld ab und legt Inventar an; Menge -5 → abgelehnt, Wallet unverändert
       Mitglied ohne Profil kann kaufen (bekommt Konto, dann „not enough")
use:   verbraucht Gegenstände; mehr als vorhanden → abgelehnt
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün
- [ ] **Step 5:** Commit `fix: games and shop book money through the services`

### Task 4: Economy und Missionen umstellen

**Files:** Modify `demolizzen/cogs/economy/economy.py`, `mission.py`, `missionfunc.py`, `CHANGELOG.md`; Create `demolizzen/tests/cogs/test_economy_cog.py`, `demolizzen/tests/test_no_direct_balance_changes.py`

- `Economy.cog_before_invoke`, `TextAdventure.cog_before_invoke`: legen Guild und Konto an, laden danach das Profil wie bisher

- `/daily`: `bank.credit`; `/gank`: `bank.transfer` in die jeweilige Richtung, `InsufficientFunds` → bisherige Texte („finds it empty", „you are broke"); Ziel ist Bot oder man selbst → `You can't gank this target.` (ephemeral)

- `/work`, Missions-Auszahlung: `bank.adjust`; Schiffskauf: `bank.debit`, bei `InsufficientFunds` der bisherige Text

- Kein Cog speichert mehr ein `UserBankAccount`

- [ ] **Step 1: Failing tests**

```text
test_daily_credits_reward_and_works_without_profile
test_gank_success_moves_money_from_victim          random gesteuert; Opfer 100 → 100−n, Angreifer +n
test_gank_failure_moves_money_to_victim
test_gank_victim_without_money_finds_wreck_empty
test_gank_self_and_bot_is_refused
test_no_cog_assigns_wallet_or_bank                  Quelltext aller Dateien unter demolizzen/cogs ohne
                                                    Zuweisung an .wallet/.bank und ohne bank_account.save/asave
```

- [ ] **Step 2:** → FAIL · **Step 3:** Umsetzen · **Step 4:** Suite grün (SQLite und `USE_MYSQL=1`), `pre-commit run --all-files` grün
- [ ] **Step 5:** CHANGELOG, Commit `fix: economy and missions book money through the bank`

______________________________________________________________________

## Bekannte Grenzen

- `/daily` und Missions-Cooldowns werden weiter im Cog geprüft; zwei gleichzeitige `/daily` können beide auszahlen.
- Schiffskauf: Preis wird abgebucht, bevor das Schiff gespeichert ist; schlägt das Speichern fehl, wird der Preis zurückgebucht.
