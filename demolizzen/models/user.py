# Standard Library
from typing import Union

# Discord
import discord

# Django
from django.db import models
from django.utils import timezone

# Demolizzen
from demolizzen.models.guild import GuildProfile


class UserProfile(models.Model):
    user_id = models.BigIntegerField()
    user_name = models.CharField(max_length=255)
    guild = models.ForeignKey(
        GuildProfile, on_delete=models.CASCADE, related_name="user_guild"
    )
    experience = models.BigIntegerField(default=0)
    level = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_profile"
        default_permissions = ()

    def __str__(self):
        return f"{self.user_name} ({self.user_id}) in Guild {self.guild.guild_name} ({self.guild.guild_id})"

    @property
    def bank_account(
        self,
    ) -> Union[models.QuerySet["UserBankAccount"], "UserBankAccount"]:
        """Returns the user's bank account QuerySet Manager."""
        return self.bank_account

    @property
    def bags(self) -> Union[models.QuerySet["UserBag"], "UserBag"]:
        """Returns the user's bag QuerySet Manager."""
        return self.bags

    async def get_cooldown(
        self,
        ctx: discord.ApplicationContext,
        ship_cooldown: timezone.timedelta,
        last_cooldown: timezone.datetime | None,
    ):
        """Get the cooldown for a specific mission type."""

        class CooldownTimer:
            def __init__(self, timer, delta, cooldown):
                self.timer = timer
                self.delta = delta
                self.cooldown = cooldown

        excluding = [784546720935182357, 240850566002114561]

        timer = ship_cooldown
        # Can be removed cause its only for checking code
        if ctx.author.id in excluding and ctx.guild.id == 518052275076464640:
            timer = timezone.timedelta(seconds=10)
        if ctx.author.id in excluding and ctx.guild.id == 337275567487320064:
            timer = timezone.timedelta(seconds=10)

        # Wenn last_cooldown nicht gesetzt ist, setze ihn auf einen Zeitpunkt weit in der Vergangenheit
        if not last_cooldown:
            print("No last cooldown found, setting to past time.")
            last_cooldown = timezone.now() - timer

        # Berechne, wie viel Zeit noch übrig ist
        cooldown_end = last_cooldown + timer
        now = timezone.now()
        cooldown_td = max(cooldown_end - now, timezone.timedelta(seconds=0))
        cooldown = str(cooldown_td).split(".", maxsplit=1)[0]
        delta = now - last_cooldown

        ctx.bot.logger.debug(
            f"Last Cooldown: {last_cooldown} | Now: {now} | Timer: {timer} | Delta: {delta} | Cooldown: {cooldown}"
        )
        return CooldownTimer(timer, delta, cooldown)


class UserSettings(models.Model):
    user = models.OneToOneField(
        UserProfile, on_delete=models.CASCADE, related_name="settings"
    )
    language = models.CharField(max_length=10, default="en")
    background = models.TextField()
    xp_colour = models.TextField()
    blur = models.IntegerField()
    border = models.TextField()

    class Meta:
        db_table = "user_settings"
        default_permissions = ()

    def __str__(self):
        return f"Settings for {self.user.user_name} ({self.user.user_id}) in Guild {self.user.guild.guild_name} ({self.user.guild.guild_id})"


class UserBankAccount(models.Model):
    user = models.OneToOneField(
        UserProfile, on_delete=models.CASCADE, related_name="bank_account"
    )
    wallet = models.BigIntegerField(default=0)
    bank = models.BigIntegerField(default=0)

    class Meta:
        db_table = "user_bank"
        default_permissions = ()


class UserDailyReward(models.Model):
    user = models.OneToOneField(
        UserProfile, on_delete=models.CASCADE, related_name="daily_reward"
    )
    last_claim = models.DateTimeField(null=True)
    streak = models.IntegerField(default=0)

    class Meta:
        db_table = "user_reward"
        default_permissions = ()


class UserBag(models.Model):
    user = models.OneToOneField(
        UserProfile, on_delete=models.CASCADE, related_name="bags"
    )

    class Meta:
        db_table = "user_bag"
        default_permissions = ()

    def __str__(self):
        return f"Bag of {self.user.user_name} ({self.user.user_id}) in Guild {self.user.guild.guild_name} ({self.user.guild.guild_id})"

    @property
    def items(self) -> Union[models.QuerySet["UserBagItems"], "UserBagItems"]:
        """Returns the User Bags QuerySet Manager."""
        return self.items


class UserBagItems(models.Model):
    user_bag = models.ForeignKey(
        UserBag, on_delete=models.CASCADE, related_name="items"
    )
    item_name = models.CharField(max_length=255)
    item_type = models.CharField(max_length=50)
    quantity = models.IntegerField(default=0)

    class Meta:
        db_table = "user_bag_items"
        default_permissions = ()
        unique_together = (("user_bag", "item_name"),)

    def __str__(self):
        return f"{self.quantity} x {self.item_name} of {self.user_bag.user.user_name} ({self.user_bag.user.user_id}) in Guild {self.user_bag.guild.guild_name} ({self.user_bag.guild.guild_id})"
