# Discord
import discord

# Django
from django.utils import timezone

# Demolizzen
from demolizzen import models


class PriceHandler:
    def __init__(self, bot: discord.bot, ctx: discord.ApplicationContext):
        self.bot = bot
        self.ctx = ctx

    async def appraisel(self, item_names: list, tradehub: str) -> list:
        expiration = timezone.now() + timezone.timedelta(
            seconds=1800
        )  # 30 Minuten in Sekunden

        if isinstance(item_names, str):
            item_names = [item_names]

        async with self.bot.session.post(
            "https://appraise.gnf.lt/appraisal/structured.json",
            json={
                "market_name": tradehub,
                "items": [{"name": item_name} for item_name in item_names],
            },
        ) as market_data:
            if market_data.status == 200:
                response = await market_data.json()

                price_list = []
                for item in response["appraisal"]["items"]:
                    item_name = item["name"]
                    item_id = item["typeID"]
                    price = int(round(float(item["prices"]["sell"]["min"])))
                    maxprice = int(round(float(item["prices"]["buy"]["max"])))

                    price_dict = {
                        "item_name": item_name,
                        "item_id": item_id,
                        "price": price,
                        "buy": maxprice,
                        "tradehub": tradehub,
                        "expiration": expiration,
                    }

                    existing_entry = await models.EvePricecache.objects.filter(
                        item_name=item_name, tradehub=tradehub
                    ).afirst()

                    if existing_entry:
                        existing_entry.price = price
                        existing_entry.buy = maxprice
                        existing_entry.expiration = expiration
                        await existing_entry.asave()
                    else:
                        await models.EvePricecache.objects.acreate(
                            item_name=item_name,
                            price=price,
                            buy=maxprice,
                            tradehub=tradehub,
                            expiration=expiration,
                        )
                    price_list.append(price_dict)
                return price_list
            self.bot.logger.error(
                f"Failed to fetch data for {item_names} in {tradehub} with status {market_data.status}"
            )
            return None
