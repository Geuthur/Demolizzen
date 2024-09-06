import logging

from discord.commands import SlashCommandGroup
from discord.ext import commands

log = logging.getLogger("main")


class Geuthur(commands.Cog):
    """
    Get all relevant commands for "Geuthur"
    """

    def __init__(self, bot):
        self.bot = bot
        self.title = "Geuthur"  # Title hier festlegen
        self.alias = "geuthur"  # Alias hier festlegen
        self.access = 337275567487320064  # Guild hier festlegen

    geuthur = SlashCommandGroup(
        name="geuthur", description="Geuthur", guild_ids=[337275567487320064]
    )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, member):
        if not member.guild_id == 337275567487320064:
            return
        emojis_to_roles = {
            "warframe": 780199646395498537,  # Rolle für Warframe
            "eveonline": 881537446897123338,  # Rolle für EvE Online
            "demolizzen": 1180120903317725286,  # Rolle für Discord Bot
            # Füge weitere benutzerdefinierte Emoji-Rolle-Paare hinzu
        }
        emoji_name = member.emoji.name
        if emoji_name in emojis_to_roles:
            guild = self.bot.get_guild(member.guild_id)
            if guild is not None:
                role_id = emojis_to_roles[emoji_name]
                role = guild.get_role(role_id)
                if role is not None:
                    user_id = guild.get_member(member.user_id)
                    if user_id is not None:
                        channel_id = member.channel_id
                        if (
                            channel_id == 783472747443519498
                        ):  # EINGANGSHALLE_CHANNEL_ID muss definiert sein
                            try:
                                await user_id.add_roles(role)
                                log.info(
                                    f"{user_id.name} hat die Rolle {role.name} erhalten."
                                )
                            # pylint: disable=broad-except
                            except Exception:
                                return

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, member):
        if not member.guild_id == 337275567487320064:
            return
        emojis_to_roles = {
            "warframe": 780199646395498537,  # Rolle für Warframe
            "eveonline": 881537446897123338,  # Rolle für EvE Online
            "demolizzen": 1180120903317725286,  # Rolle für Discord Bot
            # Füge weitere benutzerdefinierte Emoji-Rolle-Paare hinzu
        }

        emoji_name = member.emoji.name
        if emoji_name in emojis_to_roles:
            guild = self.bot.get_guild(member.guild_id)
            if guild is not None:
                role_id = emojis_to_roles[emoji_name]
                role = guild.get_role(role_id)
                if role is not None:
                    user_id = guild.get_member(member.user_id)
                    if user_id is not None:
                        channel_id = member.channel_id
                        if (
                            channel_id == 783472747443519498
                        ):  # EINGANGSHALLE_CHANNEL_ID muss definiert sein
                            try:
                                await user_id.remove_roles(role)
                                log.info(
                                    f"{user_id.name} hat die Rolle {role.name} verloren."
                                )
                            # pylint: disable=broad-except
                            except Exception:
                                return

    # ---------------------------- Listener ----------------------------
    # ---------------------------- Listener ----------------------------
    # ---------------------------- Listener ----------------------------

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id in [337275567487320064, 518052275076464640]:
            # Finde den gewünschten Textkanal nach Name oder ID
            channel = member.guild.get_channel(1145682399892611134)
            if channel is not None:
                # Sende eine Willkommensnachricht im Textkanal
                await channel.send(
                    f"Willkommen {member.display_name.capitalize()} ({member.name}) auf unserem Server!"
                )

    # on guild leave
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.guild.id in [337275567487320064, 518052275076464640]:
            # Finde den gewünschten Textkanal nach Name oder ID
            channel = member.guild.get_channel(1145682399892611134)
            if channel is not None:
                # Sende eine Abschiedsnachricht im Textkanal
                await channel.send(
                    f"{member.display_name.capitalize()} ({member.name}) hat den Server verlassen."
                )
