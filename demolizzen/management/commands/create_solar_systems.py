# Django
from django.core.management.base import BaseCommand

# Demolizzen
from demolizzen.models import EconomySolarSystem


class Command(BaseCommand):
    help = "Insert default solar systems"

    def handle(self, *args, **options):
        systems = [
            {
                "name": "Jita",
                "security_status": 0.9,
                "description": "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
                "active": True,
            },
            {
                "name": "Amarr",
                "security_status": 1.0,
                "description": "Amarr VIII (Oris) - Emperor Family Academy",
                "active": True,
            },
            {
                "name": "Dodixie",
                "security_status": 0.8,
                "description": "Dodixie IX - Moon 20 - Federation Navy Assembly Plant",
                "active": True,
            },
            {
                "name": "Rens",
                "security_status": 0.9,
                "description": "Rens VI - Moon 8 - Brutor Tribe Treasury",
                "active": True,
            },
            {
                "name": "Hek",
                "security_status": 0.9,
                "description": "Hek VIII - Moon 12 - Republic Fleet Logistics",
                "active": True,
            },
            {
                "name": "Sobaseki",
                "security_status": 0.7,
                "description": "Sobaseki VII - Moon 1 - Minmatar Republic Treasury",
                "active": True,
            },
            {
                "name": "Perimeter",
                "security_status": 0.9,
                "description": "Perimeter VII - Moon 1 - Caldari Navy Assembly Plant",
                "active": True,
            },
            {
                "name": "Tash-Murkon Prime",
                "security_status": 0.8,
                "description": "Tash-Murkon Prime VIII - Moon 2 - Tash-Murkon Family Academy",
                "active": True,
            },
            {
                "name": "Halaima",
                "security_status": 0.6,
                "description": "Halaima IV - Moon 1 - Gallente Federation Treasury",
                "active": True,
            },
            {
                "name": "Khanid Prime",
                "security_status": 1.0,
                "description": "Khanid Prime VIII - Moon 2 - Khanid Kingdom Academy",
                "active": True,
            },
            {
                "name": "Jakanerva",
                "security_status": 0.7,
                "description": "Jakanerva VII - Moon 1 - Minmatar Republic Treasury",
                "active": True,
            },
            {
                "name": "Ishukone Prime",
                "security_status": 0.9,
                "description": "Ishukone Prime VIII - Moon 2 - Ishukone Corporation Academy",
                "active": True,
            },
            {
                "name": "Oursulaert",
                "security_status": 0.8,
                "description": "Oursulaert IX - Moon 4 - Federation Navy Assembly Plant",
                "active": True,
            },
            {
                "name": "Motsu",
                "security_status": 0.7,
                "description": "Motsu VII - Moon 1 - Minmatar Republic Treasury",
                "active": True,
            },
            {
                "name": "New Caldari",
                "security_status": 0.9,
                "description": "New Caldari VIII - Moon 2 - Caldari State Academy",
                "active": True,
            },
            {
                "name": "Aunia",
                "security_status": 0.6,
                "description": "Aunia IV - Moon 1 - Gallente Federation Treasury",
                "active": True,
            },
            {
                "name": "Eystur",
                "security_status": 0.8,
                "description": "Eystur IX - Moon 4 - Federation Navy Assembly Plant",
                "active": True,
            },
            {
                "name": "Kador Prime",
                "security_status": 1.0,
                "description": "Kador Prime VIII - Moon 2 - Kador Family Academy",
                "active": True,
            },
            {
                "name": "Saisio",
                "security_status": 0.7,
                "description": "Saisio VII - Moon 1 - Minmatar Republic Treasury",
                "active": True,
            },
            {
                "name": "Arnon",
                "security_status": 0.6,
                "description": "Arnon IV - Moon 1 - Gallente Federation Treasury",
                "active": True,
            },
        ]
        for sys in systems:
            obj, created = EconomySolarSystem.objects.get_or_create(
                name=sys["name"], defaults=sys
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Added {sys['name']}"))
            else:
                self.stdout.write(f"{sys['name']} already exists")
