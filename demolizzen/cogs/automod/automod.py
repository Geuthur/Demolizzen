from datetime import timedelta

import discord
from core import checks
from discord.commands import Option
from discord.ext import commands

invite_links = ["*discord.com/invite*", "*discord.gg*"]


class Automod(commands.Cog):
    """
    Auto Moderation System
    """

    def __init__(self, bot):
        self.bot = bot
        self.title = "Automod"  # Alias hier festlegen
        self.alias = "auto"  # Alias hier festlegen
        self.automod_entry = {}

    @commands.slash_command()
    @discord.guild_only()
    @checks.is_guild_owner()
    async def automod(
        self, ctx: discord.ApplicationContext, log_channel: Option(discord.TextChannel)
    ):
        """
        Install Automod Module to Server
        """
        server_id = ctx.guild.id

        try:
            em = discord.Embed(title="", color=discord.Color.teal(), description="")
            automod_data = await ctx.guild.fetch_auto_moderation_rules()

            if server_id not in self.automod_entry:
                self.automod_entry[server_id] = {}

            # Check if the Automod already installed
            for entry in automod_data:
                self.automod_entry[server_id][entry.name] = True

            if self.automod_entry[server_id].get("Anti Invite"):
                em.add_field(
                    name="",
                    value="❌ `Anti Invite` Bereits eingerichtet.",
                    inline=False,
                )
            else:
                actions = [
                    discord.AutoModAction(
                        action_type=discord.AutoModActionType.block_message,
                        metadata=discord.AutoModActionMetadata(),
                    ),
                    discord.AutoModAction(
                        action_type=discord.AutoModActionType.send_alert_message,
                        metadata=discord.AutoModActionMetadata(
                            channel_id=log_channel.id
                        ),
                    ),
                    discord.AutoModAction(
                        action_type=discord.AutoModActionType.timeout,
                        metadata=discord.AutoModActionMetadata(
                            timeout_duration=timedelta(minutes=5)
                        ),
                    ),
                ]
                await ctx.guild.create_auto_moderation_rule(
                    name="Anti Invite",
                    event_type=discord.AutoModEventType.message_send,
                    trigger_type=discord.AutoModTriggerType.keyword,
                    trigger_metadata=discord.AutoModTriggerMetadata(
                        keyword_filter=invite_links
                    ),
                    enabled=True,
                    actions=actions,
                )
                em.add_field(
                    name="",
                    value="✅ `Anti Invite` Erfolgereich eingerichtet.",
                    inline=False,
                )
            em.add_field(
                name="",
                value="✅ **Alle Automod Erfolgereich eingerichtet.**",
                inline=False,
            )
            await ctx.respond(embed=em)
        except discord.HTTPException:
            await ctx.respond("❌ Du hast schon zuviele Automod regeln.")
