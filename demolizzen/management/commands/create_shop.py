# Django
from django.core.management.base import BaseCommand

# Demolizzen
from demolizzen.models import EconomyShop


class Command(BaseCommand):
    help = "Insert default mission ships into the database"

    def handle(self, *args, **options):

        # Standard Library
        import random

        systems = []
        # Eve Items
        items = [
            # name, desc, category
            ("Cola", "A refreshing drink.", "drinks"),
            ("Pizza", "Delicious cheesy pizza.", "food"),
            ("Golden Trophy", "A rare and prestigious trophy.", "trophies"),
            ("Sofa", "Comfortable furniture for your quarters.", "furniture"),
            ("Mystery Box", "Contains random items.", "openable"),
            ("Quafe", "The most popular soft drink in New Eden.", "drinks"),
            (
                "Synth Crash Booster",
                "A combat booster for daring capsuleers.",
                "boosters",
            ),
            (
                "Federation Navy Comet Model",
                "A scale model of the iconic Gallente police frigate.",
                "trophies",
            ),
            (
                "Rifter Blueprint",
                "A blueprint copy for the classic Minmatar frigate.",
                "misc",
            ),
            ("PLEX", "Pilot's License Extension, used for various services.", "misc"),
            (
                "Skill Injector",
                "Instantly grants skill points to your character.",
                "boosters",
            ),
            (
                "Oxygen Isotopes",
                "Essential fuel for Gallente and Minmatar ships.",
                "misc",
            ),
            ("Antimatter Charge S", "Standard ammunition for hybrid turrets.", "misc"),
            (
                "Capsuleer Mug",
                "A mug emblazoned with the capsuleer insignia.",
                "furniture",
            ),
            (
                "Astero Skin",
                "A unique skin for the Astero exploration frigate.",
                "skins",
            ),
            ("Fedo", "A classic Minmatar dish.", "food"),
            (
                "Exotic Dancers",
                "A skilled performer from the exotic dancer profession.",
                "trophies",
            ),
            (
                "Caldari Navy Hookbill Model",
                "A scale model of the Caldari police frigate.",
                "trophies",
            ),
            (
                "Amarr Navy Slicer Model",
                "A scale model of the Amarr police frigate.",
                "trophies",
            ),
            (
                "Minmatar Navy Rifter Model",
                "A scale model of the Minmatar police frigate.",
                "trophies",
            ),
            ("Tronad", "A popular drink among capsuleers.", "drinks"),
            ("Noble Wine", "A fine wine from the Amarr Empire.", "drinks"),
            ("Caviar", "A delicacy enjoyed by the wealthy.", "food"),
            ("Hobgoblin I", "A basic combat drone.", "misc"),
            (
                "Infiltrator Cloaking Device",
                "A cloaking device for stealth operations.",
                "misc",
            ),
            ("Data Analyzer", "Used for hacking and data retrieval.", "misc"),
            ("Salvage Drone I", "A basic salvage drone.", "misc"),
            ("Warp Scrambler I", "Prevents ships from warping away.", "misc"),
            ("Nanite Repair Paste", "Used for repairing ship modules.", "misc"),
            ("Cap Booster 50", "Instantly restores capacitor energy.", "boosters"),
            (
                "Eifyr and Co. 'Rogue' Evasive Maneuvering EM-705",
                "An implant that enhances evasive maneuvers.",
                "special",
            ),
            (
                "Zainou 'Deadeye' Small Hybrid Turret SH-605",
                "An implant that improves small hybrid turret performance.",
                "special",
            ),
            ("High-grade Slave Alpha", "A high-grade slave implant.", "special"),
            ("Guristas Camo", "A unique skin for ships.", "skins"),
            ("Shadow Serpentis Camo", "A unique skin for ships.", "skins"),
            ("Blood Raider Camo", "A unique skin for ships.", "skins"),
            ("Sansha's Nation Camo", "A unique skin for ships.", "skins"),
            (
                "Federation Navy Comet Skin",
                "A unique skin for the Federation Navy Comet.",
                "skins",
            ),
            (
                "Caldari Navy Hookbill Skin",
                "A unique skin for the Caldari Navy Hookbill.",
                "skins",
            ),
            (
                "Amarr Navy Slicer Skin",
                "A unique skin for the Amarr Navy Slicer.",
                "skins",
            ),
            (
                "Minmatar Navy Rifter Skin",
                "A unique skin for the Minmatar Navy Rifter.",
                "skins",
            ),
            (
                "Luxury Bed",
                "A comfortable and stylish bed for your quarters.",
                "furniture",
            ),
            (
                "Holographic Display",
                "A futuristic display for your quarters.",
                "furniture",
            ),
            ("Recliner Chair", "A relaxing chair for your quarters.", "furniture"),
            ("Wall Art", "Decorative art for your quarters.", "furniture"),
            ("Energy Drink", "Boosts your energy levels.", "drinks"),
            ("Protein Bar", "A nutritious snack.", "food"),
            ("Alien Artifact", "A mysterious artifact of unknown origin.", "trophies"),
            ("Ancient Relic", "A relic from a bygone era.", "trophies"),
            ("Collector's Item", "A rare item sought after by collectors.", "trophies"),
            ("Exotic Pet", "A rare and unusual pet.", "trophies"),
            ("Space Plant", "A unique plant that thrives in space.", "furniture"),
            (
                "Holographic Pet",
                "A virtual pet that lives in your quarters.",
                "furniture",
            ),
            ("Virtual Aquarium", "A digital aquarium for your quarters.", "furniture"),
            ("Gourmet Meal", "A high-quality meal for discerning tastes.", "food"),
            ("Exotic Fruit Basket", "A selection of rare and exotic fruits.", "food"),
            ("Luxury Chocolate Box", "A box of fine chocolates.", "food"),
            ("Rare Spice Set", "A collection of rare and exotic spices.", "food"),
            (
                "Quantum Computer",
                "A cutting-edge computer for your quarters.",
                "furniture",
            ),
            ("Antique Globe", "A decorative globe for your quarters.", "furniture"),
            ("Star Map", "A detailed map of the stars.", "furniture"),
            (
                "Unique Starship Skin",
                "A one-of-a-kind skin for your starship.",
                "unique",
            ),
            ("Legendary Weapon Skin", "A legendary skin for your weapon.", "unique"),
            ("Mythical Armor Skin", "A mythical skin for your armor.", "unique"),
            ("Epic Vehicle Skin", "An epic skin for your vehicle.", "unique"),
            (
                "Celestial Mount",
                "A mount that allows you to traverse the stars.",
                "unique",
            ),
            ("Dragon Pet", "A rare and powerful pet dragon.", "unique"),
            ("Phoenix Pet", "A rare and powerful pet phoenix.", "unique"),
            ("Unicorn Pet", "A rare and magical pet unicorn.", "unique"),
            ("Griffin Pet", "A rare and majestic pet griffin.", "unique"),
            ("Pegasus Pet", "A rare and mythical pet pegasus.", "unique"),
            ("Space-Time Distorter", "A device that manipulates space-time.", "unique"),
            (
                "Wormhole Generator",
                "A device that creates wormholes for instant travel.",
                "unique",
            ),
            (
                "Dimensional Rift",
                "A rift that allows access to other dimensions.",
                "unique",
            ),
            ("Temporal Anomaly", "An anomaly that affects the flow of time.", "unique"),
        ]

        for name, desc, category in items:
            if category in ["drinks", "food"]:
                price = random.randint(5, 20)
            elif category == "trophies":
                price = random.randint(500, 2000)
            elif category == "furniture":
                price = random.randint(100, 500)
            elif category == "skins":
                price = random.randint(200, 1000)
            elif category == "openable":
                price = random.randint(50, 300)
            elif category == "boosters":
                price = random.randint(150, 800)
            elif category == "special":
                price = random.randint(1000, 2000)
            elif category == "unique":
                price = random.randint(7000, 20000)
            else:  # misc, general, etc.
                price = random.randint(20, 100)
            systems.append(
                {
                    "name": name,
                    "price": price,
                    "description": desc,
                    "shop_type": category,
                }
            )

        for sys in systems:
            obj, created = EconomyShop.objects.get_or_create(
                name=sys["name"], defaults=sys
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Added {sys['name']}"))
            else:
                self.stdout.write(f"{sys['name']} already exists")
