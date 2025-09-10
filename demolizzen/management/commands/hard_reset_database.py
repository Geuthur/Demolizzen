# Django
from django.apps import apps
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Hard Reset all Database tables including static data"

    def handle(self, *args, **options):
        for model in apps.get_models():
            model.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS("All Database tables have been hard reset")
        )
