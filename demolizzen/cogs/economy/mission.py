import random

# Write Success Chance
ship_chance_var = {
    "normal": 70,
    "yield": 75,
    "tanky": 85,
    "fast": 75,
    "T2yield": 80,
    "T2tanky": 90,
    "T2fast": 80,
    "precapital": 85,
    "capital": 90,
    # Raid Ships
    "mission": 75,
    "missionT2": 80,
    "missionT2dps": 90,
    "missionT2fast": 80,
}


# Write earn Coins
def generate_ship_coin_var():
    return {
        "normal": random.randrange(10, 35),
        "yield": random.randrange(40, 80),
        "tanky": random.randrange(25, 40),
        "fast": random.randrange(20, 60),
        "T2yield": random.randrange(80, 120),
        "T2tanky": random.randrange(60, 100),
        "T2fast": random.randrange(50, 90),
        "precapital": random.randrange(100, 200),
        "capital": random.randrange(150, 300),
        # Raid Ships
        "mission": random.randrange(40, 100),
        "missionT2": random.randrange(80, 120),
        "missionT2dps": random.randrange(60, 100),
        "missionT2fast": random.randrange(50, 90),
    }


# Write repeat Cooldown
ship_speed_var = {
    "normal": 7200,
    "yield": 5400,
    "tanky": 7500,
    "fast": 3600,
    "T2yield": 4800,
    "T2tanky": 6600,
    "T2fast": 3000,
    "precapital": 10000,
    "capital": 14400,
    # Raid Ships
    "mission": 5400,
    "missionT2": 4800,
    "missionT2dps": 6600,
    "missionT2fast": 3000,
}

# Text Adventure
Raidingschiffe = (
    "Ares",
    "Proteus",
    "Confessor",
    "Tengu",
    "Svipul",
    "Gila",
    "Orthrus",
    "Catalyst",
    "Cynabal",
)

System = (
    "K-QWHE",
    "0SHT-A",
    "TXME-A",
    "3T7-M8",
    "JNG7-K",
    "3-DMQT",
    "1DQ1-A",
    "GY6A-L",
)

System2 = ("Rens", "Amarr", "Jita", "Hek", "Dodixie", "Abdudban", "Perimeter", "Ofage")

MiningAsteroid = (
    "Spodumain",
    "Crokite",
    "Bistot",
    "Gneiss",
    "Plagioclase",
    "Veldspar",
    "Hemorphite",
    "Dark Ochre",
)

Miningschiffe = (
    "Venture",
    "Retriever",
    "Procurer",
    "Covetor",
    "Hulk",
    "Mackinaw",
    "Skiff",
    "Orca",
)


def get_random_ship(modus):
    if modus == "mining":
        return random.choice(Raidingschiffe)
    if modus == "raiding":
        return random.choice(Miningschiffe)
    return None


def get_random_system():
    return random.choice(System)


def get_random_system2():
    return random.choice(System2)


def get_story_information(modus):
    if modus == "mining":
        return random.choice(MiningAsteroid)
    if modus == "raiding":
        return random.choice(Miningschiffe)
    return None


# 1
def get_anomalie_text():
    return random.choice(
        [
            "You warp to a mining anomaly.",
            "You make a warp to the Ice Belt.",
            "You land at a moon.",
            "You arrive at an asteroid belt.",
        ]
    )


# 2
def get_story_text(modus, target):
    if modus == "mining":
        return random.choice(
            [
                f"You fly to the **`{target}`** and start mining.",
                f"You survey the Belt and choose the largest **`{target}`** rock to mine.",
                f"The Belt is very busy, you select a small **`{target}`** rock to mine.",
                f"Since no one is around, you start mining **`{target}`** casually.",
            ]
        )

    if modus == "raiding":
        return random.choice(
            [
                f"You fly to the **`{target}`**.",
                f"After examining the Belt closely, you decide on the nearest **`{target}`**.",
                f"The Belt is full of ships, you orbit one of them, the **`{target}`**.",
                f"You land right next to a **`{target}`**.",
            ]
        )
    return None


# 3
def get_interaction_text_mining(modus):
    if modus == "mining":
        return random.choice(
            [
                "You want to mine another valuable rock, but you notice that enemy ships are appearing.",
                "Your asteroid belt is almost empty, and you start mining the last ores. Suddenly, an enemy ship appears.",
                "After mining everything, a ship decloaks next to you and tackles you.",
            ]
        )
    if modus == "raiding":
        return random.choice(
            [
                "You attack the ship, but it initiates a cyno.",
                "After tackling the ship, it starts attacking you with drones.",
                "You orbit the ship at optimal range, but the rats have switched targets and are attacking you.",
            ]
        )
    return None


def get_flee_text():
    return random.choice(
        [
            "You are already aligned and warp out.",
            "You activate the warp and escape.",
            "You see the enemies slowly appearing on the grid but you warp out already.",
        ]
    )


def get_cyno_text():
    return random.choice(
        [
            "You light the cyno and see the Home Defense destroying the enemy fleet.",
            "After everyone appears on the grid, you light the cyno and the enemies retreat.",
            "After realizing you forgot to fit a cyno, you see a Rorqual has already lit a cyno.",
        ]
    )


def get_flee_fail_text():
    return random.choice(
        [
            "You try to warp out but are blocked by the rock.",
            "You activate the warp but are immediately tackled by a rat.",
            "You realize quite late that enemies have appeared, try to warp out but are already tackled.",
        ]
    )


def get_cyno_fail_text():
    return random.choice(
        [
            "You try to activate a cyno but don't notice that a cyno inhibitor has been deployed.",
            "You activate the cyno, but there is no active Home Defense at the moment.",
            "The enemies are already on the grid; you try to light the cyno, but they have so much main power that you are alpha'd out immediately.",
        ]
    )


def get_bonus_text(modus, target):
    if modus == "mining":
        return random.choice(
            [
                "While mining, you notice pulsating ore in your cargo hold. It seems to be valuable...",
                "When destroying an ore rock, suddenly loot appears. You start collecting it...",
                "A mining ship has left the Belt and left behind some loot. You check it, and it's full of ores...",
                f"While heading towards the **`{target}`**, you notice the ore starting to gleam. It seems to be exceptionally valuable...",
            ]
        )
    if modus == "raiding":
        return random.choice(
            [
                f"The **`{target}`** offers you a deal and pays you extra :coin: if you leave it alone.",
                "One of the ships is empty; you fly there with your alternative character and take over.",
                "You use the ship scanner and find out that the ship you tackled is excellently fitted.",
            ]
        )

    return None


def get_docken_text(modus, target):
    if modus == "mining":
        return random.choice(
            [
                "After the rock has been mined, you return to the station. \n\nYour earnings are ",
                "You have mined all the rocks, return to the station, and sell everything. \n\nYour earnings are ",
                "You watch as the last rock explodes - a wonderful sight. You return to the station and sell everything. \n\nYour earnings are ",
                "All rocks are mined, you return to the station and sell everything. \n\nYour earnings are ",
            ]
        )

    if modus == "raiding":
        return random.choice(
            [
                f"The **`{target}`** is destroyed; you fly to the wreckage and loot it. After the raid, you sell everything. \n\nYour earnings are ",
                "You destroyed multiple ships, fly to the wrecks, and conclude the raid! \n\nYour earnings are ",
                "One ship escaped, but you got two. You fly to the wrecks and loot them. \n\nYour earnings are ",
                f"All ships escaped except the **`{target}`** that you already tackled and destroyed. You start looting. \n\nYour earnings are ",
            ]
        )

    return None


def get_tackle_text(modus, ship):
    if modus == "mining":
        return random.choice(
            [
                f"You try to warp, but the **`{ship}`** has already scrammed you.",
                f"You try to target the ship, but **`{ship}`** has already pointed you and uses ECM against you, preventing you from locking on.",
                f"You try to align for an immediate warp, but the **`{ship}`** starts bumping you.",
                f"You try to negotiate a deal in local chat, but the **`{ship}`** ignores it and continues shooting at you.",
            ]
        )

    if modus == "raiding":
        return random.choice(
            [
                "You try to warp, but it's already too late - you get destroyed.",
                "Your armor is depleting rapidly, and the fleet tears apart your ship.",
                "You destroyed the ship, but others in the Belt have already targeted and are shooting at you.",
                "A cyno is lit, and you see the Home Defense annihilating you.",
            ]
        )

    return None
