# Django
from django.db import models
from django.utils.translation import gettext_lazy as _


class EconomyShip(models.Model):
    class ShipTypes(models.TextChoices):
        FRIGATE = "frigate", _("Frigate")
        DESTROYER = "destroyer", _("Destroyer")
        CRUISER = "cruiser", _("Cruiser")
        BATTLECRUISER = "battlecruiser", _("Battlecruiser")
        BATTLESHIP = "battleship", _("Battleship")
        CARRIER = "carrier", _("Carrier")
        DREADNOUGHT = "dreadnought", _("Dreadnought")
        SUPER_CARRIER = "super_carrier", _("Super Carrier")

        # Mining
        MINING_BARGE = "mining_barge", _("Mining Barge")
        EXHUMER = "exhumer", _("Exhumer")
        INDUSTRIAL = "industrial", _("Industrial")
        RORQUAL = "rorqual", _("Rorqual")

        UNKNOWN = "unknown", _("Unknown")

    class MissionCategories(models.TextChoices):
        MINING = "mining", _("Mining")
        RAIDING = "raiding", _("Raiding")
        UNKNOWN = "unknown", _("Unknown")

    name = models.CharField(max_length=100)
    ship_type = models.CharField(
        max_length=50, choices=ShipTypes.choices, default=ShipTypes.UNKNOWN
    )
    ship_speed = models.IntegerField()
    payout_bonus = models.IntegerField(default=0)
    success_bonus = models.IntegerField(default=0)
    price = models.BigIntegerField()
    insurance = models.BigIntegerField()
    description = models.TextField()
    active = models.BooleanField(default=True)
    category = models.CharField(
        max_length=50,
        choices=MissionCategories.choices,
        default=MissionCategories.UNKNOWN,
    )

    class Meta:
        db_table = "economy_ship"
        default_permissions = ()

    def __str__(self):
        return f"{self.name} ({self.ship_type})"


class EconomySolarSystem(models.Model):
    name = models.CharField(max_length=100)
    security_status = models.FloatField()
    description = models.TextField()
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "economy_solar_system"
        default_permissions = ()

    def __str__(self):
        return f"{self.name} (Security: {self.security_status})"


class EconomyShop(models.Model):
    class ShopTypes(models.TextChoices):
        GENERAL = "general", _("General")
        TROPHIES = "trophies", _("Trophies")
        SKINS = "skins", _("Skins")
        FURNITURE = "furniture", _("Furniture")
        DRINKS = "drinks", _("Drinks")
        FOOD = "food", _("Food")
        MISC = "misc", _("Miscellaneous")
        OPENABLE = "openable", _("Openable")
        BOOSTERS = "boosters", _("Boosters")
        SPECIAL = "special", _("Special")
        UNIQUE = "unique", _("Unique")
        SUPER_RARE = "super_rare", _("Super Rare")

    name = models.CharField(max_length=100)
    price = models.BigIntegerField()
    description = models.TextField()
    shop_type = models.CharField(
        max_length=50, choices=ShopTypes.choices, default=ShopTypes.GENERAL
    )
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "economy_shop"
        default_permissions = ()
