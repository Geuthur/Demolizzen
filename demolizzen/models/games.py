# Standard Library
import random

# Django
from django.db import models
from django.utils.translation import gettext_lazy as _

# Demolizzen
from demolizzen.models.economy import EconomyShip
from demolizzen.models.user import UserProfile


class UserWorkMission(models.Model):
    class JobTypes(models.TextChoices):
        UNEMPLOYED = "Unemployed", _("Unemployed")
        MINER = "Miner", _("Miner")
        HAULER = "Hauler", _("Hauler")
        EXPLORER = "Explorer", _("Explorer")
        TRADER = "Trader", _("Trader")
        BOUNTY_HUNTER = "Bounty Hunter", _("Bounty Hunter")
        PIRATE = "Pirate", _("Pirate")
        SMUGGLER = "Smuggler", _("Smuggler")
        MISSION_RUNNER = "Mission Runner", _("Mission Runner")
        INDUSTRIALIST = "Industrialist", _("Industrialist")
        CORPORATE_AGENT = "Corporate Agent", _("Corporate Agent")
        FLEET_COMMANDER = "Fleet Commander", _("Fleet Commander")
        WARLORD = "Warlord", _("Warlord")
        DREADNOUGHT = "Dreadnought", _("Dreadnought")

    user = models.OneToOneField(
        UserProfile, on_delete=models.CASCADE, related_name="working_mission"
    )
    cooldown = models.DateTimeField(null=True)
    job = models.CharField(
        max_length=100, choices=JobTypes.choices, default=JobTypes.UNEMPLOYED
    )  # Not Implemented yet
    job_duration = models.IntegerField(default=3600)
    salary = models.IntegerField(null=True)
    experience = models.IntegerField(default=0)  # Not Implemented yet
    level = models.IntegerField(default=1)  # Not Implemented yet
    chance = models.IntegerField(default=0)

    class Meta:
        db_table = "user_work_mission"
        default_permissions = ()

    def __str__(self):
        return f"{self.user.user_name} ({self.user.user_id}) in Guild {self.guild.guild_name} ({self.guild.guild_id}) - Job: {self.job}"

    def get_work_text_combined(
        self, escalation_chance=0.2
    ) -> tuple[str, str | None, str]:
        """
        Gibt ein passendes Triple (work_text, escalation_text, work_ending_text) zurück.
        escalation_text ist entweder None oder ein passender Text, je nach Zufall.
        """
        pairs = [
            (
                "You spend the day working diligently, earning your keep.",
                "As the day ends, you reflect on your achievements and look forward to tomorrow.",
                "You feel a surge of adrenaline as you take on more challenging tasks.",
            ),
            (
                "Your efforts at work are paying off, and you feel accomplished.",
                "You wrap up your work with a sense of fulfillment and anticipation for what's next.",
                "Your skills are being put to the test with these new responsibilities.",
            ),
            (
                "You tackle your tasks with enthusiasm, making the most of your workday.",
                "The conclusion of your workday leaves you eager for new opportunities ahead.",
                "The thrill of the challenge excites you as you step up your game.",
            ),
            (
                "The satisfaction of a job well done fills you as you complete your duties.",
                "You finish your tasks with pride, knowing you've done your best.",
                "You embrace the opportunity to prove your worth with tougher assignments.",
            ),
            (
                "You navigate the challenges of your work with skill and determination.",
                "As you close out your work, you feel ready to take on whatever comes next.",
                "The increased difficulty only fuels your determination to succeed.",
            ),
        ]
        work_text, work_ending, escalation = random.choice(pairs)
        if random.random() < escalation_chance:
            return work_text, escalation, work_ending
        return work_text, None, work_ending


class UserRaidMission(models.Model):
    user = models.OneToOneField(
        UserProfile, on_delete=models.CASCADE, related_name="raid_mission"
    )
    cooldown = models.DateTimeField(null=True)
    chance = models.IntegerField(null=True)
    salary = models.IntegerField(null=True)
    active = models.BooleanField(default=False)
    ship = models.ForeignKey(
        EconomyShip, on_delete=models.SET_NULL, null=True, related_name="raiding_ships"
    )
    ship_type = models.CharField(max_length=50, default="normal")

    class Meta:
        db_table = "user_raid_mission"
        default_permissions = ()

    def get_story(self) -> tuple[str, str, str]:
        stories = random.choice(
            [
                "You set out on a daring raid against a well-defended convoy, hoping to claim its valuable cargo.",
                "Your ship cuts through the darkness of space as you approach the target, adrenaline pumping.",
                "The thrill of the chase fills you as you close in on the convoy, ready for battle.",
                "As you engage the enemy, your heart races with excitement and fear.",
            ]
        )
        anomalies = random.choice(
            [
                "You spot a heavily armed convoy on your scanner, ripe for the picking.",
                "Your intel points to a lucrative target in a nearby system.",
                "You intercept communications about a valuable shipment passing through the area.",
                "Your sensors pick up a convoy laden with precious cargo.",
                "You detect a vulnerable transport ship in a nearby sector.",
                "You identify a convoy with minimal escort, making it an ideal target.",
                "You locate a transport ship carrying high-value goods.",
                "You receive a tip about an unguarded convoy in the vicinity.",
            ]
        )
        interaction = random.choice(
            [
                "The convoy's escorts are closing in! What do you want to do next?",
                "Enemy reinforcements arrive to protect the convoy. What do you want to do next?",
                "Your ship takes heavy damage from the convoy's defenses. What do you want to do next?",
                "A rival raider challenges you for the loot. What do you want to do next?",
                "Your instincts tell you to retreat before you're overwhelmed. What do you want to do next?",
                "A sudden counterattack forces you to disengage and flee. What do you want to do next?",
            ]
        )
        return stories, anomalies, interaction

    def get_bonus_story(self) -> str:
        return random.choice(
            [
                "During the raid, you discover an unguarded cache of high-value items, significantly boosting your haul.",
                "Your tactical brilliance allows you to outmaneuver the convoy's escorts, leading to a bonus payout.",
                "You successfully hack into the convoy's systems, gaining access to additional valuable cargo.",
                "A sudden surge in local market prices means your raided goods are worth more than usual.",
                "Your daring tactics during the raid earn you a reputation, leading to increased rewards.",
            ]
        )

    def get_cyno_story(self, failure: bool = False) -> str:
        if failure:
            return random.choice(
                [
                    "Your attempt to activate the cynosural field fails.",
                    "A Cyno Inhibitor disrupts your activation.",
                    "Hostile forces decloak and destroy your ship before the Home Defense can respond.",
                    "You forgot to bring Liquid Ozone, and the cynosural field fizzles out.",
                    "Your ship's systems struggle to stabilize the cynosural field.",
                ]
            )
        return random.choice(
            [
                "You light the cyno seconds later, the home defense fleet jumps into the system!",
                "The cyno flares up and your alliance friends land right on grid.",
                "With a bright flash, several capitals appear at your cyno reinforcements have arrived!",
                "You light the cyno, local spikes blue fleet has landed.",
                "With your cyno, you enable the entire fleet to jump quickly into the target system.",
                "You activate the cyno, and in the next moment, titans and supers appear in system.",
                "The cyno burns and your fleet jumps safely through mission accomplished!",
                "Your successful activation of the cyno allows for a swift extraction of valuable assets.",
                "The enemy fleet is caught off guard as your reinforcements arrive through the cyno.",
                "With the cyno lit, your fleet can now engage the enemy with overwhelming force.",
            ]
        )

    def get_flee_story(self, failure: bool = False) -> str:
        if failure:
            return random.choice(
                [
                    "In your haste to flee, you misjudge the asteroid field and collide with a large rock, severely damaging your ship.",
                    "As you attempt to warp out, a sudden system malfunction causes your ship to spin out of control, leaving you vulnerable to enemy fire.",
                    "You try to escape through a dense asteroid belt, but your ship's engines overheat and shut down, leaving you stranded.",
                    "While fleeing, you accidentally enter a restricted area of space, triggering an alarm that attracts hostile forces.",
                    "In the chaos of your escape, you drop valuable cargo that was essential for your mission.",
                ]
            )
        return random.choice(
            [
                "You execute a perfect warp out of the danger zone, leaving your pursuers behind.",
                "Your quick thinking and skilled piloting allow you to evade the attackers and escape unscathed.",
                "With a burst of speed, you break free from the enemy's scrambler and set a course for safety.",
                "Your ship's advanced maneuvering systems help you dodge incoming fire as you make your escape.",
            ]
        )

    def get_attack_story(self, failure: bool = False) -> str:
        if failure:
            return random.choice(
                [
                    "Your ship's weapons malfunction during the attack, leaving you defenseless against the enemy.",
                    "As you engage the enemy, your ship takes critical damage and you are forced to retreat.",
                    "You miscalculate the enemy's strength and are overwhelmed by their superior firepower.",
                    "During the heat of battle, a sudden system failure causes your ship to lose power, making you an easy target.",
                    "Your attack is thwarted by unexpected reinforcements that arrive just in time to save the enemy.",
                ]
            )
        return random.choice(
            [
                "You launch a successful attack on the enemy convoy, crippling their defenses and securing valuable loot.",
                "Your precise targeting and skilled piloting lead to a decisive victory over the hostile forces.",
                "With coordinated strikes, you overwhelm the enemy and claim their cargo for yourself.",
                "Your ship's advanced weaponry allows you to dominate the battlefield and emerge victorious.",
                "You outmaneuver the enemy fleet, delivering a crushing blow that leaves them in disarray.",
                "Your daring assault on the convoy is met with fierce resistance, but your determination sees you through to victory.",
            ]
        )

    def get_dock_story(self) -> str:
        return random.choice(
            [
                "You dock at a bustling space station, the hum of activity filling the air as traders and adventurers go about their business.",
                "The station's lights twinkle against the backdrop of space as you secure your ship and prepare to explore.",
                "As you step onto the station, the scent of exotic foods and the sound of lively chatter greet you.",
                "The station is a hive of activity, with merchants hawking their wares and pilots sharing tales of their latest exploits.",
                "You navigate through the crowded corridors of the station, eager to see what opportunities await.",
                "The station's marketplace is alive with color and sound, a testament to the diverse inhabitants of this corner of space.",
            ]
        )


class UserMiningMission(models.Model):
    user = models.OneToOneField(
        UserProfile, on_delete=models.CASCADE, related_name="mining_mission"
    )
    cooldown = models.DateTimeField(null=True)
    chance = models.IntegerField(null=True)
    salary = models.IntegerField(null=True)
    active = models.BooleanField(default=False)
    ship = models.ForeignKey(
        EconomyShip, on_delete=models.SET_NULL, null=True, related_name="mining_ships"
    )
    ship_type = models.CharField(max_length=50, default="normal")

    class Meta:
        db_table = "user_mining_mission"
        default_permissions = ()

    def random_belt(self) -> str:
        belts = ["Asteroid Belt", "Ice Belt", "Gas Cloud", "Mining Escalation", "Moon"]
        return random.choice(belts)

    def get_story(self) -> tuple[str, str, dict]:
        anomalies = random.choice(
            [
                f"You warp to a {self.random_belt()}.",
                f"You make a warp to the {self.random_belt()}.",
                f"You land at a {self.random_belt()}.",
                f"You arrive at a {self.random_belt()}.",
                "You discover a hidden asteroid cluster rich in rare minerals.",
                "You find an abandoned mining outpost surrounded by valuable rocks.",
                "A cosmic anomaly appears on your scanner, promising untold riches.",
                "You warp into a dense field of asteroids, untouched by other miners.",
            ]
        )
        stories = random.choice(
            [
                "You embark on a mining expedition to a nearby asteroid field, hoping to strike it rich.",
                "Your ship hums as you navigate through the dense asteroid belt, scanning for valuable minerals.",
                "The thrill of the hunt fills you as you deploy your mining drones to extract precious ores.",
                "As you mine, you can't help but feel a sense of adventure in the vastness of space.",
                "The sound of your mining lasers echoes through the void as you work tirelessly to gather resources.",
                "You carefully position your ship next to a promising asteroid.",
                "Your mining lasers cut into the rock, extracting valuable ore.",
                "You notice a glint in the asteroid and focus your efforts there.",
                "Your drones swarm over the asteroid, maximizing your yield.",
            ]
        )
        interaction = random.choice(
            [
                "A pirate ship appears and attacks you! What do you want to do next?",
                "Hostile drones approach your mining vessel. What do you want to do next?",
                "A rival miner tries to steal your ore. What do you want to do next?",
                "You notice danger on your scanner. What do you want to do next?",
                "Your instincts tell you to leave before trouble arrives. What do you want to do next?",
                "A sudden threat forces you to abandon your mining and warp to safety. What do you want to do next?",
            ]
        )
        return anomalies, stories, interaction

    def get_bonus_story(self) -> str:
        return random.choice(
            [
                "While mining, you discover a rare mineral vein that significantly boosts your yield.",
                "Your mining drones uncover a hidden cache of valuable ores, increasing your profits.",
                "You strike a particularly rich asteroid, yielding an unexpected bonus haul.",
                "A sudden surge in local market prices means your mined resources are worth more than usual.",
                "Your expert piloting allows you to mine more efficiently, resulting in a bonus payout.",
            ]
        )

    def get_cyno_story(self, failure: bool = False) -> str:
        if failure:
            return random.choice(
                [
                    "Your attempt to activate the cynosural field fails.",
                    "A Cyno Inhibitor disrupts your activation.",
                    "Hostile forces decloak and destroy your ship before the Home Defense can respond.",
                    "You forgot to bring Liquid Ozone, and the cynosural field fizzles out.",
                    "Your ship's systems struggle to stabilize the cynosural field.",
                ]
            )
        return random.choice(
            [
                "You light the cyno seconds later, the home defense fleet jumps into the system!",
                "The cyno flares up and your alliance friends land right on grid.",
                "With a bright flash, several capitals appear at your cyno reinforcements have arrived!",
                "You light the cyno, local spikes blue fleet has landed.",
                "Home defense jumps precisely to your cyno and secures the system.",
                "You activate the cyno, and in the next moment, titans and supers appear in system.",
                "The cyno burns and your fleet jumps safely through mission accomplished!",
                "With your cyno, you enable the entire fleet to jump quickly into the target system.",
                "Reinforcements arrive just in time thanks to your cyno and drive off the attackers.",
                "You're the hero of the night without your cyno, home defense wouldn't have made it!",
            ]
        )

    def get_flee_story(self, failure: bool = False) -> str:
        if failure:
            return random.choice(
                [
                    "In your haste to flee, you misjudge the asteroid field and collide with a large rock, severely damaging your ship.",
                    "As you attempt to warp out, a sudden system malfunction causes your ship to spin out of control, leaving you vulnerable to enemy fire.",
                    "You try to escape through a dense asteroid belt, but your ship's engines overheat and shut down, leaving you stranded.",
                    "While fleeing, you accidentally enter a restricted area of space, triggering an alarm that attracts hostile forces.",
                    "In the chaos of your escape, you drop valuable cargo that was essential for your mission.",
                ]
            )
        return random.choice(
            [
                "You execute a perfect warp out of the danger zone, leaving your pursuers behind.",
                "Your quick thinking and skilled piloting allow you to evade the attackers and escape unscathed.",
                "With a burst of speed, you break free from the enemy's scrambler and set a course for safety.",
                "Your ship's advanced maneuvering systems help you dodge incoming fire as you make your escape.",
            ]
        )

    def get_attack_story(self, failure: bool = False) -> str:
        if failure:
            return random.choice(
                [
                    "Your ship's weapons malfunction during the attack, leaving you defenseless against the enemy.",
                    "As you engage the enemy, your ship takes critical damage and you are forced to retreat.",
                    "You miscalculate the enemy's strength and are overwhelmed by their superior firepower.",
                    "During the heat of battle, a sudden system failure causes your ship to lose power, making you an easy target.",
                    "Your attack is thwarted by unexpected reinforcements that arrive just in time to save the enemy.",
                ]
            )
        return random.choice(
            [
                "You launch a successful attack on the enemy convoy, crippling their defenses and securing valuable loot.",
                "Your precise targeting and skilled piloting lead to a decisive victory over the hostile forces.",
                "With coordinated strikes, you overwhelm the enemy and claim their cargo for yourself.",
                "Your ship's advanced weaponry allows you to dominate the battlefield and emerge victorious.",
                "You outmaneuver the enemy fleet, delivering a crushing blow that leaves them in disarray.",
                "Your daring assault on the convoy is met with fierce resistance, but your determination sees you through to victory.",
            ]
        )

    def get_dock_story(self) -> str:
        return random.choice(
            [
                "You dock at a bustling space station, the hum of activity filling the air as traders and adventurers go about their business.",
                "The docking bay doors slide open, revealing a vibrant hub of commerce and camaraderie among spacefarers.",
                "As you dock, you can't help but feel a sense of relief and accomplishment after a successful mission.",
                "The station's lights twinkle in the distance as you approach, promising rest and resupply after your arduous journey.",
                "You expertly maneuver your ship into the docking bay, greeted by the familiar sights and sounds of the station.",
            ]
        )
