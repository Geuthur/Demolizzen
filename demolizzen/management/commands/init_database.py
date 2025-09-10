# Django
from django.core.management.base import BaseCommand

# Demolizzen
from demolizzen.models import EconomyShip


class Command(BaseCommand):
    help = "Create all default Database entries"

    def handle(self, *args, **options):
        from .create_mission_ships import Command as CreateMissionShipsCommand
        from .create_shop_items import Command as CreateShopItemsCommand
        from .create_solar_systems import Command as CreateSolarSystemsCommand

        CreateMissionShipsCommand().handle(*args, **options)
        CreateShopItemsCommand().handle(*args, **options)
        CreateSolarSystemsCommand().handle(*args, **options)
        self.stdout.write(
            self.style.SUCCESS("Database has been initialized with default entries")
        )
