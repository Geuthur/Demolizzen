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


class GuildSettings(models.Model):
    guild = models.OneToOneField(
        GuildProfile, on_delete=models.CASCADE, related_name="settings"
    )
    language = models.CharField(max_length=10, default="en")
    bank_interest = models.FloatField(default=0.001)  # Interest rate for bank system
    custom_commands = models.JSONField(null=True)  # JSON field for custom commands
    disabled_commands = models.JSONField(null=True)  # JSON field for disabled commands
    disabled_cogs = models.JSONField(null=True)  # JSON field for disabled cogs
    enabled_cogs = models.JSONField(null=True)  # JSON field for enabled cogs

    class Meta:
        db_table = "guild_settings"
        default_permissions = ()

    def __str__(self):
        return f"Settings for {self.guild.guild_name} ({self.guild.guild_id})"
