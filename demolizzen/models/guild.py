# Django
from django.db import models
from django.utils import timezone


class GuildProfile(models.Model):
    guild_id = models.BigIntegerField(primary_key=True)
    guild_name = models.CharField(max_length=255)
    main_channel_id = models.BigIntegerField(null=True)
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
    custom_commands = models.JSONField(
        null=True, help_text="Custom commands for the guild"
    )  # JSON field for custom commands
    disabled_commands = models.JSONField(
        null=True, help_text="Disabled commands for the guild"
    )  # JSON field for disabled commands
    disabled_cogs = models.JSONField(
        null=True, help_text="Disabled cogs for the guild"
    )  # JSON field for disabled cogs
    enabled_cogs = models.JSONField(
        null=True, help_text="Enabled cogs for the guild"
    )  # JSON field for enabled cogs

    class Meta:
        db_table = "guild_settings"
        default_permissions = ()

    def __str__(self):
        return f"Settings for {self.guild.guild_name} ({self.guild.guild_id})"


class GuildBankSettings(models.Model):
    guild = models.OneToOneField(
        GuildProfile, on_delete=models.CASCADE, related_name="bank_settings"
    )
    allow_deposits = models.BooleanField(default=True, help_text="Allow deposits")
    allow_withdrawals = models.BooleanField(default=True, help_text="Allow withdrawals")
    interest_rate = models.FloatField(default=0.001, help_text="Daily interest rate")
    last_interest_update = models.DateTimeField(
        null=True, help_text="Timestamp of the last interest update"
    )

    class Meta:
        db_table = "guild_bank_settings"
        default_permissions = ()

    def __str__(self):
        return f"Bank Settings for {self.guild}"


class GuildTicket(models.Model):
    guild = models.ForeignKey(
        GuildProfile, on_delete=models.CASCADE, related_name="guild_tickets"
    )
    ticket_number = models.PositiveIntegerField(help_text="Ticket number")
    channel_id = models.BigIntegerField(help_text="ID of the ticket channel")
    user_id = models.BigIntegerField(help_text="ID of the user who created the ticket")
    created_at = models.DateTimeField(auto_now_add=True)
    closed_by = models.BigIntegerField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)
    claimed_by = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "guild_tickets"
        unique_together = ("guild", "ticket_number")
        default_permissions = ()

    def __str__(self):
        return f"Ticket {self.ticket_number} in {self.guild}"


class GuildTicketSettings(models.Model):
    guild = models.OneToOneField(
        GuildProfile, on_delete=models.CASCADE, related_name="ticket_settings"
    )
    category_id = models.PositiveBigIntegerField(
        null=True,
        help_text="ID of the channel category where tickets will be created",
    )
    archive_category_id = models.PositiveBigIntegerField(
        null=True,
        help_text="ID of the channel category where archived tickets will be moved",
    )
    roles = models.JSONField(
        null=True, help_text="List of role IDs that can see tickets"
    )
    ticket_count = models.PositiveBigIntegerField(
        default=1, help_text="Counter for tickets created in the guild"
    )
    auto_archive_days = models.PositiveSmallIntegerField(
        default=3,
        help_text="Number of days after which closed tickets are automatically archived",
    )
    allow_user_close = models.BooleanField(
        default=True, help_text="Whether users can close their own tickets"
    )
    allow_user_reopen = models.BooleanField(
        default=True, help_text="Whether users can reopen their closed tickets"
    )

    class Meta:
        db_table = "guild_ticket_settings"
        default_permissions = ()

    def __str__(self):
        return f"Ticket Settings for {self.guild}"


class GuildTicketTask(models.Model):
    task_id = models.AutoField(primary_key=True)
    ticket = models.OneToOneField(
        GuildTicket, on_delete=models.CASCADE, related_name="tasks"
    )
    channel_name = models.CharField(
        max_length=255, null=True, help_text="Name of the channel for the ticket"
    )
    topic = models.TextField(null=True, help_text="Topic of the ticket")
    is_queued = models.BooleanField(
        default=False, help_text="Whether the task is queued for processing"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the task was created"
    )
    completed_at = models.DateTimeField(
        null=True, blank=True, help_text="Timestamp when the task was completed"
    )
    has_error = models.BooleanField(
        default=False,
        help_text="Whether the task encountered an error during processing",
    )

    class Meta:
        db_table = "guild_ticket_tasks"
        default_permissions = ()

    @property
    def is_outdated(self):
        if self.completed_at:
            return False
        return timezone.now() > self.created_at + timezone.timedelta(minutes=10)

    def __str__(self):
        return f"Task {self.task_id} for {self.ticket}"
