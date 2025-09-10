# Django
from django.core.management.base import BaseCommand

# Demolizzen
from demolizzen import models


class Command(BaseCommand):
    help = "Reset all User related Database tables"

    def handle(self, *args, **options):
        models.GuildProfile.objects.all().delete()
        models.UserProfile.objects.all().delete()
        models.EconomyShip.objects.all().delete()
        models.EconomySolarSystem.objects.all().delete()
        models.ShopItem.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("All User related tables have been reset"))
