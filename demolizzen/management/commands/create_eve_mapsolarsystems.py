# Standard Library
import bz2
import csv
import re

# Third Party
import requests

# Django
from django.core.management.base import BaseCommand

# Demolizzen
from demolizzen.models import MapSolarSystems


class Command(BaseCommand):
    help = "Import mapSolarSystems from fuzzwork and bulk insert into mapSolarSystems"

    def add_arguments(self, parser):
        parser.add_argument(
            "--local",
            action="store_true",
            help="Use local file instead of downloading from remote.",
        )

    def handle(self, *args, **options):
        if options.get("local"):
            local_path = "tools/mapSolarSystems.sql.bz2"
            self.stdout.write(f"Reading local file: {local_path}")
            with open(local_path, "rb") as f:
                data = bz2.decompress(f.read()).decode("utf-8")
        else:
            url = "https://www.fuzzwork.co.uk/dump/latest/mapSolarSystems.sql.bz2"
            self.stdout.write("Downloading...")
            response = requests.get(url)
            data = bz2.decompress(response.content).decode("utf-8")

        insert_re = re.compile(r"INSERT INTO `mapSolarSystems` VALUES (.+);")
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
            values = [None if v == "NULL" else v for v in values]
            if len(values) != 26:
                self.stdout.write(
                    f"Skipped line with {len(values)} fields (expected 26)."
                )
                continue
            objs.append(
                MapSolarSystems(
                    regionID=int(values[0]) if values[0] is not None else None,
                    constellationID=int(values[1]) if values[1] is not None else None,
                    solarSystemID=int(values[2]),
                    solarSystemName=values[3],
                    x=float(values[4]) if values[4] is not None else None,
                    y=float(values[5]) if values[5] is not None else None,
                    z=float(values[6]) if values[6] is not None else None,
                    xMin=float(values[7]) if values[7] is not None else None,
                    xMax=float(values[8]) if values[8] is not None else None,
                    yMin=float(values[9]) if values[9] is not None else None,
                    yMax=float(values[10]) if values[10] is not None else None,
                    zMin=float(values[11]) if values[11] is not None else None,
                    zMax=float(values[12]) if values[12] is not None else None,
                    luminosity=float(values[13]) if values[13] is not None else None,
                    border=bool(int(values[14])) if values[14] is not None else None,
                    fringe=bool(int(values[15])) if values[15] is not None else None,
                    corridor=bool(int(values[16])) if values[16] is not None else None,
                    hub=bool(int(values[17])) if values[17] is not None else None,
                    international=(
                        bool(int(values[18])) if values[18] is not None else None
                    ),
                    regional=bool(int(values[19])) if values[19] is not None else None,
                    constellation=(
                        bool(int(values[20])) if values[20] is not None else None
                    ),
                    security=float(values[21]) if values[21] is not None else None,
                    factionID=int(values[22]) if values[22] is not None else None,
                    radius=float(values[23]) if values[23] is not None else None,
                    sunTypeID=int(values[24]) if values[24] is not None else None,
                    securityClass=values[25],
                )
            )
        self.stdout.write(f"Importing {len(objs)} items...")
        MapSolarSystems.objects.bulk_create(objs, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS("Import finished!"))
