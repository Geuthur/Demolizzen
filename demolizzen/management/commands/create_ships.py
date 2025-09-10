# Django
from django.core.management.base import BaseCommand

# Demolizzen
from demolizzen.models import EconomyShip


class Command(BaseCommand):
    help = "Insert default mission ships into the database"

    def handle(self, *args, **options):
        # Standard Library
        import random

        systems = []
        # Frigates: 4000-5000
        for name, desc in [
            ("Catalyst", "A fast and agile frigate, perfect for hit-and-run tactics."),
            (
                "Rifter",
                "A versatile and durable frigate, known for its adaptability in various combat scenarios.",
            ),
            (
                "Merlin",
                "A sleek and powerful frigate, favored by pilots who value speed and firepower.",
            ),
            (
                "Incursus",
                "A well-rounded frigate, offering a balance of offense and defense.",
            ),
            (
                "Punisher",
                "A heavily armed frigate, designed to deliver devastating blows to its enemies.",
            ),
            (
                "Slasher",
                "A nimble and stealthy frigate, ideal for surprise attacks and evasive maneuvers.",
            ),
            (
                "Tristan",
                "A versatile frigate, capable of fulfilling multiple roles in combat.",
            ),
            ("Kestrel", "A fast and agile frigate, perfect for hit-and-run tactics."),
            ("Cormorant", "A durable frigate, known for its resilience in battle."),
            (
                "Coercer",
                "A heavily armed frigate, designed to dominate in close-quarters combat.",
            ),
            (
                "Algos",
                "A sleek and powerful frigate, favored by pilots who value speed and firepower.",
            ),
            (
                "Breacher",
                "A well-rounded frigate, offering a balance of offense and defense.",
            ),
            (
                "Tormentor",
                "A heavily armed frigate, designed to deliver devastating blows to its enemies.",
            ),
            (
                "Astero",
                "A nimble and stealthy frigate, ideal for surprise attacks and evasive maneuvers.",
            ),
            (
                "Raptor",
                "A versatile frigate, capable of fulfilling multiple roles in combat.",
            ),
        ]:
            payout_bonus = random.randint(5, 15)
            insurance = random.randint(int(payout_bonus * 0.2), int(payout_bonus * 0.4))
            price = random.randint(payout_bonus * 80, payout_bonus * 120)
            systems.append(
                {
                    "name": name,
                    "description": desc,
                    "active": True,
                    "category": "raiding",
                    "ship_type": "frigate",
                    "ship_speed": random.randint(4000, 5000),
                    "payout_bonus": payout_bonus,
                    "success_bonus": random.randint(40, 50),
                    "insurance": insurance,
                    "price": price,
                }
            )
        # Cruiser: 5000-6000
        for name, desc in [
            ("Vexor", "A fast and agile cruiser, perfect for hit-and-run tactics."),
            (
                "Caracal",
                "A versatile cruiser, known for its adaptability in various combat scenarios.",
            ),
            (
                "Omen",
                "A sleek and powerful cruiser, favored by pilots who value speed and firepower.",
            ),
            (
                "Stabber",
                "A well-rounded cruiser, offering a balance of offense and defense.",
            ),
            (
                "Moa",
                "A heavily armed cruiser, designed to deliver devastating blows to its enemies.",
            ),
            (
                "Thorax",
                "A nimble and stealthy cruiser, ideal for surprise attacks and evasive maneuvers.",
            ),
            (
                "Exequror",
                "A versatile cruiser, capable of fulfilling multiple roles in combat.",
            ),
            ("Cerberus", "A fast and agile cruiser favored by hit-and-run tactics."),
            (
                "Blackbird",
                "An electronic warfare cruiser specializing in disrupting enemy systems.",
            ),
            ("Vigilant", "A durable cruiser known for its resilience in battle."),
            (
                "Phobos",
                "A heavily armed cruiser designed to dominate in close-quarters combat.",
            ),
        ]:
            payout_bonus = random.randint(10, 20)
            insurance = random.randint(int(payout_bonus * 0.2), int(payout_bonus * 0.4))
            price = random.randint(payout_bonus * 300, payout_bonus * 500)
            systems.append(
                {
                    "name": name,
                    "description": desc,
                    "active": True,
                    "category": "raiding",
                    "ship_type": "cruiser",
                    "ship_speed": random.randint(5000, 6000),
                    "payout_bonus": payout_bonus,
                    "success_bonus": random.randint(50, 60),
                    "insurance": insurance,
                    "price": price,
                }
            )
        # Battleship: 6000-7000
        for name, desc in [
            (
                "Hurricane",
                "A fast and agile battleship, perfect for hit-and-run tactics.",
            ),
            (
                "Raven",
                "A versatile battleship, known for its adaptability in various combat scenarios.",
            ),
            (
                "Apocalypse",
                "A sleek and powerful battleship, favored by pilots who value speed and firepower.",
            ),
            (
                "Armageddon",
                "A well-rounded battleship, offering a balance of offense and defense.",
            ),
            (
                "Megathron",
                "A heavily armed battleship, designed to deliver devastating blows to its enemies.",
            ),
            (
                "Tempest",
                "A nimble and stealthy battleship, ideal for surprise attacks and evasive maneuvers.",
            ),
            (
                "Dominix",
                "A versatile battleship, capable of fulfilling multiple roles in combat.",
            ),
            ("Rokh", "A powerful battleship known for its heavy armor and firepower."),
            (
                "Scorpion",
                "A long-range battleship equipped with advanced missile systems.",
            ),
            ("Paladin", "A heavily armored battleship designed for frontline combat."),
            (
                "Abaddon",
                "A versatile battleship capable of adapting to various combat roles.",
            ),
            ("Prophecy", "A battleship known for its energy projection capabilities."),
        ]:
            payout_bonus = random.randint(20, 30)
            insurance = random.randint(int(payout_bonus * 0.2), int(payout_bonus * 0.4))
            price = random.randint(payout_bonus * 500, payout_bonus * 800)
            systems.append(
                {
                    "name": name,
                    "description": desc,
                    "active": True,
                    "category": "raiding",
                    "ship_type": "battleship",
                    "ship_speed": random.randint(6000, 7000),
                    "payout_bonus": payout_bonus,
                    "success_bonus": random.randint(60, 65),
                    "insurance": insurance,
                    "price": price,
                }
            )
        # Carrier: 7000-8000
        for name, desc in [
            (
                "Chimera",
                "A well-rounded carrier, offering a balance of offense, defense, and support capabilities.",
            ),
            (
                "Archon",
                "A versatile carrier, capable of fulfilling multiple roles in fleet engagements.",
            ),
            ("Thanatos", "A fast and agile carrier, perfect for hit-and-run tactics."),
            (
                "Nidhoggur",
                "A heavily armed carrier, designed to deliver devastating blows to its enemies.",
            ),
        ]:
            payout_bonus = random.randint(40, 60)
            insurance = random.randint(int(payout_bonus * 0.2), int(payout_bonus * 0.4))
            price = random.randint(payout_bonus * 900, payout_bonus * 1200)
            systems.append(
                {
                    "name": name,
                    "description": desc,
                    "active": True,
                    "category": "raiding",
                    "ship_type": "carrier",
                    "ship_speed": random.randint(7000, 8000),
                    "payout_bonus": payout_bonus,
                    "success_bonus": random.randint(65, 75),
                    "insurance": insurance,
                    "price": price,
                }
            )
        # Supercarrier: 9000-10000
        for name, desc in [
            (
                "Nyx",
                "A massive and powerful supercarrier, dominating the battlefield with overwhelming firepower.",
            ),
            (
                "Aeon",
                "A heavily armored supercarrier, known for its resilience and ability to withstand heavy damage.",
            ),
            (
                "Hel",
                "A sleek and agile supercarrier, favored by pilots who value speed and maneuverability.",
            ),
            (
                "Wyvern",
                "A nimble and stealthy supercarrier, ideal for surprise attacks and evasive maneuvers.",
            ),
        ]:
            payout_bonus = random.randint(50, 70)
            insurance = random.randint(int(payout_bonus * 0.2), int(payout_bonus * 0.4))
            price = random.randint(payout_bonus * 2000, payout_bonus * 3000)
            systems.append(
                {
                    "name": name,
                    "description": desc,
                    "active": True,
                    "category": "raiding",
                    "ship_type": "supercarrier",
                    "ship_speed": random.randint(9000, 10000),
                    "payout_bonus": payout_bonus,
                    "success_bonus": random.randint(65, 75),
                    "insurance": insurance,
                    "price": price,
                }
            )
        # -- Mining Section

        # Mining Frigates: 3000-4000
        for name, desc in [
            (
                "Venture",
                "A basic mining frigate, widely used for its reliability and efficiency in resource extraction.",
            ),
            (
                "Prospect",
                "A specialized mining frigate, designed for efficient resource extraction in hazardous environments.",
            ),
            (
                "Endurance",
                "A durable mining frigate, known for its resilience and ability to withstand harsh conditions.",
            ),
        ]:
            payout_bonus = random.randint(5, 15)
            insurance = random.randint(int(payout_bonus * 0.2), int(payout_bonus * 0.4))
            price = random.randint(payout_bonus * 80, payout_bonus * 120)
            systems.append(
                {
                    "name": name,
                    "description": desc,
                    "active": True,
                    "category": "mining",
                    "ship_type": "frigate",
                    "ship_speed": random.randint(3000, 4000),
                    "payout_bonus": payout_bonus,
                    "success_bonus": random.randint(40, 50),
                    "insurance": insurance,
                    "price": price,
                }
            )
        # Mining Badgers: 4000-5000
        for name, desc in [
            (
                "Covetor",
                "A fast and efficient mining badger, perfect for large-scale resource extraction.",
            ),
            (
                "Retriever",
                "A versatile mining badger, known for its adaptability in various mining scenarios.",
            ),
            (
                "Procurer",
                "A heavily armed mining badger, designed to protect valuable cargo during extraction operations.",
            ),
        ]:
            payout_bonus = random.randint(10, 20)
            insurance = random.randint(int(payout_bonus * 0.2), int(payout_bonus * 0.4))
            price = random.randint(payout_bonus * 300, payout_bonus * 500)
            systems.append(
                {
                    "name": name,
                    "description": desc,
                    "active": True,
                    "category": "mining",
                    "ship_type": "mining_barge",
                    "ship_speed": random.randint(4000, 5000),
                    "payout_bonus": payout_bonus,
                    "success_bonus": random.randint(50, 60),
                    "insurance": insurance,
                    "price": price,
                }
            )
        # Exhumers: 5000-6000
        for name, desc in [
            (
                "Skiff",
                "A fast and agile advanced mining barge, perfect for hit-and-run mining tactics.",
            ),
            (
                "Mackinaw",
                "A versatile advanced mining barge, known for its adaptability in various mining scenarios.",
            ),
            (
                "Hulk",
                "A heavily armed advanced mining barge, designed to protect valuable cargo during extraction operations.",
            ),
        ]:
            payout_bonus = random.randint(20, 30)
            insurance = random.randint(int(payout_bonus * 0.2), int(payout_bonus * 0.4))
            price = random.randint(payout_bonus * 500, payout_bonus * 800)
            systems.append(
                {
                    "name": name,
                    "description": desc,
                    "active": True,
                    "category": "mining",
                    "ship_type": "exhumer",
                    "ship_speed": random.randint(5000, 6000),
                    "payout_bonus": payout_bonus,
                    "success_bonus": random.randint(60, 65),
                    "insurance": insurance,
                    "price": price,
                }
            )
        # Orca: 6000-8000
        for name, desc in [
            (
                "Orca",
                "A massive and powerful industrial command ship, providing unparalleled support to mining operations.",
            ),
        ]:
            payout_bonus = random.randint(30, 50)
            insurance = random.randint(int(payout_bonus * 0.2), int(payout_bonus * 0.4))
            price = random.randint(payout_bonus * 1000, payout_bonus * 1500)
            systems.append(
                {
                    "name": name,
                    "description": desc,
                    "active": True,
                    "category": "mining",
                    "ship_type": "industrial",
                    "ship_speed": random.randint(6000, 8000),
                    "payout_bonus": payout_bonus,
                    "success_bonus": random.randint(65, 75),
                    "insurance": insurance,
                    "price": price,
                }
            )
        # Rorqual: 8000-9000
        for name, desc in [
            (
                "Rorqual",
                "A massive and powerful industrial capital ship, dominating the mining field with overwhelming extraction capabilities.",
            ),
        ]:
            payout_bonus = random.randint(40, 60)
            insurance = random.randint(int(payout_bonus * 0.2), int(payout_bonus * 0.4))
            price = random.randint(payout_bonus * 1500, payout_bonus * 2500)
            systems.append(
                {
                    "name": name,
                    "description": desc,
                    "active": True,
                    "category": "mining",
                    "ship_type": "rorqual",
                    "ship_speed": random.randint(8000, 9000),
                    "payout_bonus": payout_bonus,
                    "success_bonus": random.randint(65, 75),
                    "insurance": insurance,
                    "price": price,
                }
            )

        for sys in systems:
            obj, created = EconomyShip.objects.get_or_create(
                name=sys["name"], defaults=sys
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Added {sys['name']}"))
            else:
                self.stdout.write(f"{sys['name']} already exists")
