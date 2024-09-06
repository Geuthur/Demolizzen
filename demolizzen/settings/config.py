import os

# Secure Configs for Github
from dotenv import load_dotenv

load_dotenv()

CLIEND_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

SETTINGS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SETTINGS_DIR)
# DATA_DIR = os.path.join(ROOT_DIR, 'data')

LOGS_DIR = "demolizzen/logs"
CACHE_DIR = "demolizzen/cache"

# Permissions
MODERATOR_ROLE_NAME = "Moderator"

# https://discordapi.com/permissions.html
BOT_PERMISSIONS = 21444947025

EVENTS_SERVER = {}

# load extensions on start/restart
PRELOAD_EXTENSIONS = [
    "general",  # General Module
    "admin",  # Administration Module
    "banksystem",  # Economy System
    "commands",  # Standard Commands
    "economy",  # Get the time in eve and around the world
    "eveonline",  # EVE-Online Module
    "games",  # Games
    "levelsystem",  # Level System Module
    "shop",  # Shop System Module
    "killmail",  # Killmail posting Module
    # 'automod',                  # Automod Module
    #  Testing Area only works limited, can break bot
    # 'chatgpt',                 # ChatGPT Module - 1 Anwser (NO Conversation)
    "test",
    # require ESI Token to work
    # 'token',               # Must be activated if Modules are enabled in this section
    # Corporation Modules - Voices of War
    # 'vow'                       # Voices of War Module
]

# ESI API - Here you need to setup your Application
TOKENS = {"client_id": CLIEND_ID, "secret": CLIENT_SECRET}

# Level System

LOADER_TYPE = "message"
# If XP Chance is enabled or disabled (true = enabled, false = disabled)
XP_CHANCE = True
# Chance to earn XP when a user sends a message (Chance Rate, 1 to x) - If number = x, user gains xp
XP_CHANCE_RATE = 2
# XP Type  'words' = User xp increases by how many words were said,
#          'ranrange' = User xp increases by a random number between the min and max
#          'normal' = User xp increases by set value
XP_TYPE = "ranrange"
# The amount of xp a user gets when they send a message -- This is only used if the xp_type is set to 'normal'
XP_NORMAL_AMOUNT = 10
# The minimum amount of xp a user can gain -- This is only used if the xp_type is set to 'ranrange'
XP_RANRANGE_MIN = 1
# The maximum amount of xp a user can gain -- This is only used if the xp_type is set to 'ranrange'
XP_RANRANGE_MAX = 10
# How much XP is required per level (e.g - xp_per_level: 10 = Level 1 would require 10 xp to level up. Level 2 would require 20 xp to level up)
XP_PER_LEVEL = 100

# The default background for each user when they get added to the database || Please do not leave this as nothing!! If you get errors, it means the url is invalid.
# I recommend using imgur to get the link for your background.
DEFAULT_BACKGROUND = (
    "https://hell-rider.de/static/images/discord/standardbackground.png"
)
# Default XP Colour for each user when they get added to the database
DEFAULT_XP_COLOUR = "#ffffff"
# Default Border
DEFAULT_BORDER = "https://hell-rider.de/static/images/discord/standardborder.png"

# ======================================================================================
#                                   RANK
# ======================================================================================

# Sends a ping to the user that levelled up
LEVEL_UP_PING = True

# The background image for the level up card
LEVEL_UP_BACKGROUND = "https://hell-rider.de/static/images/discord/Background.png"
LEVEL_UP_BACKGROUND_SHADE = "https://hell-rider.de/static/images/discord/Leftshade.png"

# The amount of blur on the background image for the level up card
LEVEL_UP_BLUR = 0

# Rank Name color
NAME_COLOUR = True

# ======================================================================================
#                                   EMBED
# ======================================================================================

# Rank Embed Colour | Must Be Hex Notation
RANK_EMBED_COLOUR = 0x4863A0

# Leaderboard Embed Colour | Must Be Hex Notation (Replace # with 0x)
LEADERBOARD_EMBED_COLOUR = 0xFFFFFF

# Embed Colour | Must Be Hex Notation
EMBED_COLOUR = 0xFFFFFF

# Error Embed Colour | Must Be Hex Notation
ERROR_EMBED_COLOUR = 0x4863A0

# Success Embed Colour | Must Be Hex Notation
SUCCESS_EMBED_COLOUR = 0x4863A0
