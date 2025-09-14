# Standard Library
import math
import random

# Third Party
from asgiref.sync import sync_to_async

# Discord
import discord

# Django
from django.db import transaction
from django.utils import timezone

# Demolizzen
from demolizzen import models
from demolizzen.config import EVENTS_SERVER


class MissionComponent:
    def __init__(self, label, style=discord.ButtonStyle.gray):
        self.label = label
        self.id = id
        self.style = style


# pylint: disable=too-many-instance-attributes
class MissionEvent(discord.ui.View):
    def __init__(
        self,
        ctx: discord.ApplicationContext,
        components,
        mission_account: models.UserMiningMission | models.UserRaidMission,
    ):
        super().__init__(timeout=20, disable_on_timeout=True)
        if components is None:
            components = []

        self.ctx = ctx
        self.components = self.format_components(components)
        self.mission_account = mission_account
        self.create_views()

        # Userdata
        self.payout = self.mission_account.salary
        self.insurance = self.mission_account.ship.insurance
        self.chance = self.mission_account.chance

        # Mode (Mining, Raiding)
        self.modus = (
            "mining"
            if isinstance(self.mission_account, models.UserMiningMission)
            else "raiding"
        )
        self.bonus = False
        self.flee = False
        self.cyno = False
        self.finish = False
        self.chance = random.randint(1, 100)

        # Discord Data
        self.username = self.ctx.author.name.capitalize()

        # Event Data
        if self.ctx.guild.id in EVENTS_SERVER:
            self.events, self.event_factor = EVENTS_SERVER[self.ctx.guild.id]
        else:
            EVENTS_SERVER[self.ctx.guild.id] = (False, 0)
            self.events, self.event_factor = EVENTS_SERVER[self.ctx.guild.id]
        self.difference_payout = None

    @property
    def is_on_mission(self):
        return self.mission_account.active

    async def on_timeout(self):
        if not self.finish:
            await self.mission_trigger(self.ctx)

        return await super().on_timeout()

    def format_components(self, components):
        for i, component in enumerate(components):
            component.id = i
        return components

    def create_views(self):
        for component in self.components:
            self.add_button(
                f"{component.label}", f"label-{component.id}", component.style, False, 1
            )

    # Calculate Event Amount
    async def calc_event(self, last_coin):
        self.difference_payout = last_coin
        self.payout = math.ceil(last_coin * self.event_factor)
        self.difference_payout = self.payout - self.difference_payout

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.ctx.author.id

    async def mission_trigger(self, interaction: discord.ApplicationContext):
        # Check if user has an active mission
        if self.is_on_mission:
            # Create Embed
            em = discord.Embed(title="", color=discord.Color.teal(), description="")
            if self.modus == "mining":
                em.set_thumbnail(
                    url="https://hell-rider.de/static/images/discord/evewin.gif"
                )
            elif self.modus == "raiding":
                em.set_thumbnail(
                    url="https://hell-rider.de/static/images/discord/raidwin.gif"
                )

            # Bonus und Eventberechnung
            if random.randint(1, 100) <= self.chance:
                if self.bonus and self.chance <= 25:
                    reportbonus = random.randrange(50, 100)
                    self.payout += reportbonus
                if self.events:
                    await self.calc_event(self.payout)
                multiply = (
                    1.0 if not self.bonus else (1.0 if self.chance <= 25 else 0.8)
                )
                mission_payout = round(self.payout * multiply)
            else:
                # Lost Ship, pay Insurance if no Event
                mission_payout = 0 if self.events else -self.insurance

            # Felder generieren und zum Embed hinzufügen
            for name, value in await self.generate_embed_fields(mission_payout):
                em.add_field(name=name, value=value, inline=False)

            # Prepare Payout for previous Mission
            if self.payout is not None:
                self.mission_account.user.bank_account.wallet += mission_payout

            # Calculate Payout
            earning = random.randrange(10, 30)
            payout_bonus = self.mission_account.ship.payout_bonus
            payout = earning + payout_bonus
            # Calculate Success Chance
            random_chance = random.randint(1, 30)
            ship_success_bonus = self.mission_account.ship.success_bonus
            success_chance = random_chance + ship_success_bonus
            # Update Mission Account
            self.mission_account.salary = payout
            self.mission_account.chance = success_chance
            self.mission_account.cooldown = timezone.now()
            self.mission_account.active = True

            def save_transaction():
                with transaction.atomic():
                    self.mission_account.save()
                    self.mission_account.user.bank_account.save()

            await sync_to_async(save_transaction)()
        else:
            em = discord.Embed(
                title=":x: Mission Canceled",
                color=discord.Color.red(),
                description=f"{self.ctx.author.mention}, You don't have an active mission.",
            )

        try:
            if isinstance(interaction, discord.Interaction):
                await interaction.response.send_message(embed=em)
            else:
                await interaction.send(embed=em)
        # pylint: disable=broad-except
        except Exception as e:
            self.bot.logger.error(
                f"Fehler bei Mission Trigger Interaction {e}", exc_info=True
            )
            return False
        return True

    def add_button(self, label, custom_id, style, disabled, row):

        button = discord.ui.Button(
            label=label, custom_id=custom_id, style=style, disabled=disabled, row=row
        )

        async def button_callback(interaction: discord.Interaction, button=button):
            # Check if the interaction is from the user who triggered the button
            if interaction.user.id != self.ctx.user.id:
                await interaction.response.send_message(
                    "This interaction is not yours.", ephemeral=True
                )
                return

            # Trigger Action Event
            if button.label in ["Attack", "Warp Out", "Cyno"]:
                self.bonus = button.label == "Attack"
                self.flee = button.label == "Warp Out"
                self.cyno = button.label == "Cyno"

                # Trigger Mission Event
                if await self.mission_trigger(interaction):
                    self.disable_all_items()
                    await interaction.message.edit(view=self)
                    self.finish = True
                return

            try:
                await interaction.message.edit(
                    view=MissionEvent(
                        ctx=self.ctx,
                        components=self.components,
                        mission_account=self.mission_account,
                    )
                )
            # pylint: disable=broad-exception-caught
            except Exception:
                pass

        button.callback = button_callback
        self.add_item(button)

    async def generate_embed_fields(self, mission_payout):
        fields = []
        if random.randint(1, 100) <= self.chance:
            if self.bonus and self.chance <= 25:
                fields.append(
                    (
                        "",
                        f":rocket: {self.username}, 🌟**BONUS**🌟\n{self.mission_account.get_attack_story()}",
                    )
                )
            if self.events:
                fields.append(
                    (
                        "",
                        f"🎉**EVENT DAY**🎉\n You get an additional **`{self.difference_payout}`**:coin:",
                    )
                )
            if self.cyno:
                fields.append(
                    (
                        "",
                        f":rocket: {self.username},\n {self.mission_account.get_cyno_story()}",
                    )
                )
            if self.flee:
                fields.append(
                    (
                        "",
                        f":rocket: {self.username},\n {self.mission_account.get_flee_story()}\nAfter docking, you sell everything.\n\nYour earnings are**`{mission_payout}`** :coin:",
                    )
                )
            else:
                fields.append(
                    (
                        "",
                        f":rocket: {self.username},\n {self.mission_account.get_dock_story()} **`{mission_payout}`** :coin:",
                    )
                )
        else:
            system = await models.EconomySolarSystem.objects.order_by("?").afirst()
            if self.flee:
                fields.append(
                    (
                        "",
                        f":rocket: {self.username},\n {self.mission_account.get_flee_story()}",
                    )
                )
            elif self.cyno:
                fields.append(
                    (
                        "",
                        f":rocket: {self.username},\n {self.mission_account.get_cyno_story()}",
                    )
                )
            else:
                fields.append(
                    (
                        "",
                        f":rocket: {self.username}, \n{self.mission_account.get_attack_story(failure=True)}",
                    )
                )
            if self.events:
                fields.append(
                    (
                        "",
                        f":rocket: {self.username}, \n🎉**Event Day**🎉 \nYou wake up in {system} and realize that the ship you lost is already in the hangar.",
                    )
                )
            else:
                fields.append(
                    (
                        "",
                        f":rocket: {self.username}, \nYou wake up in {system} and fit a new ship, having paid {abs(mission_payout)} :coin: for insurance!",
                    )
                )
        return fields
