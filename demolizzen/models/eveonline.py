# Django
from django.db import models
from django.utils.translation import gettext_lazy as _

# Demolizzen
from demolizzen.models.guild import GuildProfile
from demolizzen.models.user import UserProfile


class ZKillboard(models.Model):
    channel_id = models.BigIntegerField(null=False)
    guild = models.ForeignKey(GuildProfile, on_delete=models.CASCADE)
    group_id = models.BigIntegerField(null=True)
    owner = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    losses = models.BooleanField(default=False)
    threshold = models.PositiveBigIntegerField(null=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "zKillboard"
        default_permissions = ()

    def __str__(self):
        return f"Subscription in Guild {self.guild.guild_name} ({self.guild.guild_id}) - Channel: {self.channel_id} - Owner: {self.owner.user_name} ({self.owner.user_id})"


class AccessToken(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    guild = models.ForeignKey(GuildProfile, on_delete=models.CASCADE)
    character_id = models.BigIntegerField()
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_at = models.DateTimeField()
    has_token_error = models.BooleanField(default=False)
    error_message = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "access_tokens"
        default_permissions = ()
        unique_together = (("user", "guild"),)


class EveEntityCache(models.Model):
    entity_id = models.IntegerField(primary_key=True)
    entity_name = models.CharField(max_length=64)
    category = models.CharField(max_length=64)
    created = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "eve_entity_cache"
        default_permissions = ()


class EvePricecache(models.Model):
    class TradehubChoices(models.TextChoices):
        JITA = "Jita IV - Moon 4 - Caldari Navy Assembly Plant", _("Jita")
        AMARR = "Amarr VIII (Oris) - Emperor Family Academy", _("Amarr")
        RENS = "Rens VI - Moon 8 - Brutor Tribe Treasury", _("Rens")
        DODIXIE = "Dodixie IX - Moon 20 - Federation Navy Assembly Plant", _("Dodixie")
        HEK = "Hek VIII - Moon 12 - Boundless Creation Factory", _("Hek")
        ALLIANCE = "Alliance Tournament", _("Alliance Tournament")

    item_name = models.CharField(max_length=255, primary_key=True)
    price = models.BigIntegerField()
    buy = models.BigIntegerField()
    tradehub = models.CharField(max_length=255, choices=TradehubChoices.choices)
    expiration = models.DateTimeField()

    class Meta:
        db_table = "eve_price_cache"
        default_permissions = ()


class InvTypes(models.Model):
    typeID = models.IntegerField(primary_key=True)
    groupID = models.IntegerField(null=True)
    typeName = models.CharField(max_length=100, null=True)
    description = models.TextField(null=True)
    mass = models.FloatField(null=True)
    volume = models.FloatField(null=True)
    capacity = models.FloatField(null=True)
    portionSize = models.IntegerField(null=True)
    raceID = models.IntegerField(null=True)
    BaseModelPrice = models.DecimalField(max_digits=19, decimal_places=4, null=True)
    published = models.BooleanField(null=True)
    marketGroupID = models.IntegerField(null=True)
    iconID = models.IntegerField(null=True)
    soundID = models.IntegerField(null=True)
    graphicID = models.IntegerField(null=True)

    class Meta:
        default_permissions = ()
        db_table = "invTypes"
        indexes = [
            models.Index(fields=["groupID"], name="ix_invTypes_groupID"),
        ]


class MapSolarSystems(models.Model):
    regionID = models.IntegerField(null=True)
    constellationID = models.IntegerField(null=True)
    solarSystemID = models.IntegerField(primary_key=True)
    solarSystemName = models.CharField(max_length=100, null=True)
    x = models.FloatField(null=True)
    y = models.FloatField(null=True)
    z = models.FloatField(null=True)
    xMin = models.FloatField(null=True)
    xMax = models.FloatField(null=True)
    yMin = models.FloatField(null=True)
    yMax = models.FloatField(null=True)
    zMin = models.FloatField(null=True)
    zMax = models.FloatField(null=True)
    luminosity = models.FloatField(null=True)
    border = models.BooleanField(null=True)
    fringe = models.BooleanField(null=True)
    corridor = models.BooleanField(null=True)
    hub = models.BooleanField(null=True)
    international = models.BooleanField(null=True)
    regional = models.BooleanField(null=True)
    constellation = models.BooleanField(null=True)
    security = models.FloatField(null=True)
    factionID = models.IntegerField(null=True)
    radius = models.FloatField(null=True)
    sunTypeID = models.IntegerField(null=True)
    securityClass = models.CharField(max_length=2, null=True)

    class Meta:
        default_permissions = ()
        db_table = "mapSolarSystems"
        indexes = [
            models.Index(fields=["regionID"], name="ix_mapSyst_regID"),
            models.Index(fields=["constellationID"], name="ix_mapSyst_constID"),
            models.Index(fields=["solarSystemID"], name="ix_mapSyst_solID"),
        ]
