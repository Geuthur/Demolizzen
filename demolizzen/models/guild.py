# Django
from django.db import models


class GuildProfile(models.Model):
    guild_id = models.BigIntegerField(primary_key=True)
    guild_name = models.CharField(max_length=255)
    main_channel = models.TextField(null=True)
    mention = models.BooleanField(default=True)

    class Meta:
        db_table = "guild_profile"
        default_permissions = ()

    def __str__(self):
        return f"{self.guild_name} ({self.guild_id})"
