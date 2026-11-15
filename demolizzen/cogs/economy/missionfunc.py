# Standard Library
import random

# Discord
import discord

# Demolizzen
from demolizzen import models
from demolizzen.services import missions
from demolizzen.services.errors import AlreadySettled
from demolizzen.services.missions import Event, Kind


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
        kind: Kind,
        event: Event | None = None,
    ):
        super().__init__(timeout=20, disable_on_timeout=True)
        if components is None:
            components = []

        self.ctx = ctx
        self.components = self.format_components(components)
        self.mission_account = mission_account
        self.kind = kind
        # Identifies the mission this message reports. It is settled only once,
        # however many messages show it.
        self.started_at = mission_account.cooldown
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

        # The guild's event as it was when the mission was shown.
        self.event = event or Event(False, missions.DEFAULT_EVENT_FACTOR)

    async def on_timeout(self):
        # Nobody clicked: the mission is settled without a decision.
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

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.ctx.author.id

    async def mission_trigger(self, interaction: discord.ApplicationContext):
        """Settle the mission and report how it went.

        ``interaction`` is the button click, or the command context when the
        buttons timed out. Returns True once the mission is dealt with.
        """
        clicked = isinstance(interaction, discord.Interaction)
        ship = self.mission_account.ship

        # The outcome is decided once; booking and report both follow it.
        outcome = missions.resolve(
            roll=random.randint(1, 100),
            chance=self.chance,
            payout=self.payout,
            insurance=self.insurance,
            attack=self.bonus,
            bonus_amount=random.randrange(50, 100),
            event=self.event.active,
            event_factor=self.event.factor,
        )
        # The next mission starts right away
        next_salary = random.randrange(10, 30) + ship.payout_bonus
        next_chance = random.randint(1, 30) + ship.success_bonus

        try:
            applied = await missions.settle(
                self.ctx.guild.id,
                self.ctx.author.id,
                self.ctx.author.display_name,
                self.kind,
                self.started_at,
                payout=outcome.payout,
                next_salary=next_salary,
                next_chance=next_chance,
            )
        except AlreadySettled as error:
            self.finish = True
            if clicked:
                await interaction.response.send_message(error.message, ephemeral=True)
            return True
        self.finish = True

        em = discord.Embed(title="", color=discord.Color.teal(), description="")
        if self.modus == "mining":
            em.set_thumbnail(
                url="https://hell-rider.de/static/images/discord/evewin.gif"
            )
        elif self.modus == "raiding":
            em.set_thumbnail(
                url="https://hell-rider.de/static/images/discord/raidwin.gif"
            )
        for name, value in await self.generate_embed_fields(outcome, applied):
            em.add_field(name=name, value=value, inline=False)

        try:
            if clicked:
                await interaction.response.send_message(embed=em)
            else:
                await interaction.send(embed=em)
        # pylint: disable=broad-except
        except Exception as e:
            self.ctx.bot.logger.error(
                f"Error in mission trigger interaction {e}", exc_info=True
            )
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
                return

            try:
                await interaction.message.edit(
                    view=MissionEvent(
                        ctx=self.ctx,
                        components=self.components,
                        mission_account=self.mission_account,
                        kind=self.kind,
                        event=self.event,
                    )
                )
            # pylint: disable=broad-exception-caught
            except Exception:
                pass

        button.callback = button_callback
        self.add_item(button)

    async def generate_embed_fields(self, outcome: missions.Outcome, applied: int):
        """Tell the story of the mission. ``applied`` is what was actually booked."""
        fields = []
        mission_payout = outcome.payout
        if outcome.success:
            if self.bonus and self.chance <= 25:
                fields.append(
                    (
                        "",
                        f":rocket: {self.username}, 🌟**BONUS**🌟\n{self.mission_account.get_attack_story()}",
                    )
                )
            if self.event.active:
                fields.append(
                    (
                        "",
                        f"🎉**EVENT DAY**🎉\n You get an additional **`{outcome.event_extra}`**:coin:",
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
            if self.event.active:
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
                        f":rocket: {self.username}, \nYou wake up in {system} and fit a new ship, having paid {abs(applied)} :coin: for insurance!",
                    )
                )
        return fields
