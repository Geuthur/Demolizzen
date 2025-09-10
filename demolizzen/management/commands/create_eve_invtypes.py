# Standard Library
import bz2
import csv
import re

# Third Party
import requests

# Django
from django.core.management.base import BaseCommand

# Demolizzen
from demolizzen.models import InvTypes


class Command(BaseCommand):
    help = "Import invTypes from fuzzwork and bulk insert into InvTypes"

    def add_arguments(self, parser):
        parser.add_argument(
            "--local",
            action="store_true",
            help="Use local file instead of downloading from remote.",
        )

    def handle(self, *args, **options):
        if options.get("local"):
            local_path = "tools/invTypes.sql.bz2"
            self.stdout.write(f"Reading local file: {local_path}")
            with open(local_path, "rb") as f:
                data = bz2.decompress(f.read()).decode("utf-8")
        else:
            url = "https://www.fuzzwork.co.uk/dump/latest/invTypes.sql.bz2"
            self.stdout.write(f"Downloading from: {url}")
            response = requests.get(url)
            data = bz2.decompress(response.content).decode("utf-8")

        insert_re = re.compile(r"INSERT INTO `invTypes` VALUES (.+);")
        tuple_re = re.compile(r"\(([^)]+)\)")
        values_lines = []
        for line in data.splitlines():
            match = insert_re.match(line)
            if match:
                values_lines.extend(tuple_re.findall(match.group(1)))

        objs = []
        for line in values_lines:
            reader = csv.reader([line], delimiter=",", quotechar="'", escapechar="\\")
            values = next(reader)
            # Werte ggf. nach None umwandeln:
            values = [None if v == "NULL" else v for v in values]
            if len(values) != 15:
                # Optional: print(line) für Debug
                self.stdout.write(
                    f"Skipped line with {len(values)} fields (expected 15)."
                )
                continue
            objs.append(
                InvTypes(
                    typeID=int(values[0]),
                    groupID=int(values[1]) if values[1] is not None else None,
                    typeName=values[2],
                    description=values[3],
                    mass=float(values[4]) if values[4] is not None else None,
                    volume=float(values[5]) if values[5] is not None else None,
                    capacity=float(values[6]) if values[6] is not None else None,
                    portionSize=int(values[7]) if values[7] is not None else None,
                    raceID=int(values[8]) if values[8] is not None else None,
                    BaseModelPrice=float(values[9]) if values[9] is not None else None,
                    published=bool(int(values[10])) if values[10] is not None else None,
                    marketGroupID=int(values[11]) if values[11] is not None else None,
                    iconID=int(values[12]) if values[12] is not None else None,
                    soundID=int(values[13]) if values[13] is not None else None,
                    graphicID=int(values[14]) if values[14] is not None else None,
                )
            )

        self.stdout.write(f"Importing {len(objs)} items...")
        InvTypes.objects.bulk_create(objs, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS("Import finished!"))
