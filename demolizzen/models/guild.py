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
        GuildProfile, on_delete=models.CASCADE, related_name="guild_settings"
    )
    language = models.CharField(max_length=10, default="en")
    bank_interest = models.FloatField(default=0.001)  # Interest rate for bank system
    custom_commands = models.JSONField(null=True)  # JSON field for custom commands
    disabled_commands = models.JSONField(null=True)  # JSON field for disabled commands
    disabled_cogs = models.JSONField(null=True)  # JSON field for disabled cogs
    enabled_cogs = models.JSONField(null=True)  # JSON field for enabled cogs
    help_channel = models.CharField(
        max_length=255, null=True
    )  # Channel for help tickets
    ticket_count = models.IntegerField(default=1)  # Counter for tickets

    class Meta:
        db_table = "guild_settings"
        default_permissions = ()

    def __str__(self):
        return f"Settings for {self.guild.guild_name} ({self.guild.guild_id})"


class GuildTicket(models.Model):
    guild = models.ForeignKey(
        GuildProfile, on_delete=models.CASCADE, related_name="guild_tickets"
    )
    ticket_number = models.IntegerField()
    thread_id = models.BigIntegerField()
    user_id = models.BigIntegerField()
    group_id = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)

    class Meta:
        db_table = "guild_tickets"
        unique_together = ("guild", "ticket_number")
        default_permissions = ()

    def __str__(self):
        return f"Ticket {self.ticket_number} in {self.guild.guild_name} ({self.guild.guild_id})"
