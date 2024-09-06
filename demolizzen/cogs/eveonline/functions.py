import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta

import discord
from settings import db

log = logging.getLogger("discord")
log_testing = logging.getLogger("testing")


class EveOnlineData:
    def __init__(self) -> None:
        self.total_price = 0
        self.total_buyprice = 0
        self.items_dict = defaultdict(int)
        self.item_price_dict = defaultdict(int)
        self.ship_title = "Summary"
        self.formatted_total_price = None
        self.formatted_total_buyprice = None


class PriceHandler:
    def __init__(
        self,
        bot: discord.bot,
        content,
        message: discord.ApplicationContext,
        region_id: int,
    ):
        self.bot = bot
        self.content = content
        self.context = message
        self.region_id = region_id

    async def _handle_eft_fit(self, data: EveOnlineData):
        fittingarray = self.content.splitlines()

        shipdetails = fittingarray[0].split(",", 2)

        if len(shipdetails) > 40 or not shipdetails[0].startswith("["):
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description="The format is not correct. Try it with the correct format: [EFT] or Copy to Clipboard on Fitting Screen",
            )
            await self.context.respond(embed=em)
            return False

        shipname = shipdetails[0].strip("[")

        data.items_dict[shipname] = 1

        fittingarray.pop(0)

        for line in fittingarray:
            line = line.strip()
            match = re.match(r"^(.*) x(\d+)$", line)
            if match:
                if match.group(1) in data.items_dict:
                    data.items_dict[match.group(1)] += int(match.group(2))
                else:
                    data.items_dict[match.group(1)] = int(match.group(2))
            elif "[" not in line:
                moduledetail = line.split(",", 1)
                if moduledetail[0] in data.items_dict:
                    data.items_dict[moduledetail[0]] += 1
                else:
                    data.items_dict[moduledetail[0]] = 1
                if len(moduledetail) > 1:
                    if moduledetail[1].strip() in data.items_dict:
                        data.items_dict[moduledetail[1].strip()] += 1
                    else:
                        data.items_dict[moduledetail[1].strip()] = 1
        return data

    async def get_item_names_with_typeid(self):
        if not self.bot.esi_data._eve_item_db:
            try:
                sql = "SELECT typeID, typeName FROM invTypes"
                results = await db.select(sql)
                self.bot.esi_data._eve_item_db = {
                    result[1]: result[0] for result in results
                }
            # pylint: disable=broad-except
            except Exception as e:
                log.error("Fehler in 'Database/get.py' - %s", e)
        return self.bot.esi_data._eve_item_db

    # pylint: disable=too-many-locals, too-many-statements
    async def process_item_list(self, items_dict, tradehub):
        item_names_with_typeid = await self.get_item_names_with_typeid()
        expire_time_seconds = 600  # 10 Minuten in Sekunden
        # Item Namen der Listen
        item_names_to_fetch = list(items_dict.keys())

        # Platzhalter für die SQL-Abfrage erstellen
        placeholders = ", ".join([f":item{i}" for i in range(len(item_names_to_fetch))])

        # Price Dict (Sellprice, Buyprice, Expiration)
        price_dict = {item_name: (0, 0, None) for item_name in item_names_to_fetch}

        # SQL-Abfrage, um die Preise für die relevanten Artikel abzurufen
        sql = f"SELECT item_name, price, buy, expiration FROM eve_pricecache WHERE tradehub = :tradehub AND item_name IN ({placeholders})"
        params = {
            "tradehub": tradehub
        }  # Der Parameter 'tradehub' wird separat hinzugefügt
        params.update(
            {f"item{i}": item_name for i, item_name in enumerate(item_names_to_fetch)}
        )

        # Preise aus der Datenbank abrufen
        results = await db.select_var(sql, params)

        if results is not None:
            # Preisdaten aus den results aktualisieren
            for result in results:
                item_name, price, buyprice, expiration = result
                price_dict[item_name] = (price, buyprice, expiration)

        item_ids = {}
        item_counts = {}
        item_prices = {}
        item_buyprice = {}

        # Abfrage ob Items im Cache sind
        for item_name, item_count in items_dict.items():
            expiration = datetime.now() + timedelta(seconds=expire_time_seconds)

            cached_price, cached_buyprice, cached_expiration = price_dict.get(
                item_name, (0, 0, None)
            )

            if cached_expiration is None or cached_expiration < datetime.now():
                if item_name in item_names_with_typeid:
                    item_id = item_names_with_typeid[item_name]
                    item_ids[item_name] = item_id
                else:
                    item_ids[item_name] = 0

            item_counts[item_name] = item_count

        # Wenn items existieren abfrage an Fuzzwork Market API
        if item_ids:
            log.debug("Fetch Daten von Fuzzy")
            item_id_list = ",".join(str(item_id) for item_id in item_ids.values())
            url = f"https://market.fuzzwork.co.uk/aggregates/?station={tradehub}&types={item_id_list}"
            response = await self.bot.esi_data.get_data(url)

            for item_name, item_id in item_ids.items():
                item_id_str = str(item_id)
                if item_id_str in response and response[item_id_str]["sell"]["min"]:
                    price = float(response[item_id_str]["sell"]["min"])
                    buyprice = float(response[item_id_str]["buy"]["max"])
                else:
                    price = 0
                    buyprice = 0
                item_prices[item_name] = price
                item_buyprice[item_name] = buyprice

        # Schritt 1: Gesamtpreise berechnen und aktualisierte Daten sammeln
        insert_data = []
        for item_name, price in item_prices.items():
            # Hier können Sie auf cached_expiration zugreifen, um die Ablaufdaten zu erhalten
            if (
                cached_expiration is None
                or cached_expiration < datetime.now()
                or item_prices
            ):
                log.debug(f"{item_name} wurde aktualisiert.")
                insert_data.append(
                    (
                        item_name,
                        price,
                        item_buyprice[item_name],
                        tradehub,
                        datetime.now() + timedelta(seconds=expire_time_seconds),
                    )
                )

        # Schritt 2: Speichere Alle Abfragen in die Datenbank (Caching)
        if insert_data:
            sql = "REPLACE INTO eve_pricecache (item_name, price, buy, tradehub, expiration) VALUES (:item_name, :price, :buy, :tradehub, :expiration)"
            params = [
                {
                    "item_name": item[0],
                    "price": item[1],
                    "buy": item[2],
                    "tradehub": item[3],
                    "expiration": item[4],
                }
                for item in insert_data
            ]
            await db.executemany_var_sql(sql, params)

        item_total_prices = {}
        item_totalbuy_prices = {}

        # Gesamtpreise berechnen und speichern
        for item_name, item_count in items_dict.items():
            cached_data = price_dict.get(
                item_name, (0, 0, None)
            )  # Standardwert 0, falls der Preis nicht gefunden wird
            cached_price, cached_buyprice, cached_expiration = cached_data

            # Wenn Kein Cache vorhanden ist
            if cached_expiration is None:
                cached_price = item_prices[item_name]
                cached_buyprice = item_buyprice[item_name]
            # Summiere Total Price
            item_total_prices[item_name] = cached_price * item_count
            item_totalbuy_prices[item_name] = cached_buyprice * item_count
        return item_total_prices, item_totalbuy_prices

    def extract_item_info(self, line):
        # Production Handler
        if "<localized hint=" in line:
            match = re.search(r'<localized hint="([^"]+)', line)
            if match:
                item_name = match.group(1).strip()
                values = re.findall(r"\d+[\d.,]*", line)
                if len(values) >= 3:
                    quantity = int(values[0].replace(",", ""))
                    return item_name, quantity
        else:
            # Normal Handler
            match = re.match(r"(.+?)\s+(\d+)\s+([\d.,-]+)\s+([\d.,-]+)", line)
            if not match:
                match = re.match(r"^(.*) x ?(\d+)$", line)
            if match:
                item_name = match.group(1).strip()
                quantity = int(match.group(2))
                return item_name, quantity
        return None, None

    async def process_input(self):
        # Hier die Liste verarbeiten
        textlist = ["Gesamt:", "Total:"]

        message = self.context
        data = EveOnlineData()

        try:
            if "\n" not in self.content:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description="The format is not correct. Too Short..",
                )
                await message.respond(embed=em)
                return

            if "[" in self.content:
                data = await self._handle_eft_fit(data)
                if data is False:
                    return
            else:
                for line in self.content.split("\n"):
                    if not line:
                        continue

                    item_name, quantity = self.extract_item_info(line)
                    if not item_name or item_name in textlist:
                        continue

                    if item_name in data.items_dict:
                        data.items_dict[item_name] += quantity
                    else:
                        data.items_dict[item_name] = quantity

            if data.items_dict:
                # Procced all items to Fuzzywork
                item_sell, item_buy = await self.process_item_list(
                    data.items_dict, self.region_id
                )
                # For Schleife Total Price Buy
                for item_name, item_total_price in item_sell.items():
                    data.total_price += item_total_price
                    data.item_price_dict[item_name] = int(item_total_price)
                # For Schleife Total Price Buy
                for item_name, item_totalbuy_prices in item_buy.items():
                    data.total_buyprice += item_totalbuy_prices
            else:
                # pylint: disable=broad-exception-raised
                raise AttributeError
        # pylint: disable=broad-except
        except Exception as e:
            log_testing.exception(f"Price List: {e}")
            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description="The format is not correct. Try it with the correct format: [Copy Material Information] or [Copy order to Clipboard].",
            )
            await message.respond(embed=em)
            return False

        # Gesamtpreis ausgeben (nach der Schleife)
        data.formatted_total_price = f"{data.total_price:,.0f} ISK"
        data.formatted_total_buyprice = f"{data.total_buyprice:,.0f} ISK"
        return data
