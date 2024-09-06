import logging
import os

import discord
import openai
from Core import checks
from discord.commands import Option
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("OPENAI")
openai.api_key = TOKEN

log = logging.getLogger("testing")


class ChatGPT(commands.Cog):
    """
    Chat GPT Module
    """

    def __init__(self, bot):
        self.bot = bot
        self.alias = "gpt"
        self.title = "ChatGPT"

    @commands.slash_command()
    @commands.guild_only()
    @checks.is_in_channel()
    @commands.cooldown(
        5, 43200, commands.BucketType.user
    )  # 5 Mal alle 6 Stunden pro Benutzer
    async def gpt(self, ctx, text: Option(str)):
        """
        Only 5 Requests per User - Can Only Anwser 1 Question no Conversation
        """
        await ctx.defer()
        try:
            result = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Du bist eine sehr komische Person die viele fehler macht und spielst EVE Online und weißt einiges darüber.",
                    },
                    {"role": "user", "content": text},
                ],
                max_tokens=250,
            )
            embed = discord.Embed(
                color=discord.Color.teal(),
                description=result["choices"][0]["message"]["content"],
            )
            log.info(result["usage"]["total_tokens"])
            await ctx.respond(embed=embed)
        # pylint: disable=broad-exception-caught
        except Exception as e:
            log.info(f"Fehler ist aufgetreten in ChatGPT: {e}")
            embed = discord.Embed(
                color=discord.Color.teal(),
                description="Es ist ein Fehler aufgetreten. Versuche es später erneut.",
            )
            await ctx.respond(embed=embed, delete_after=10)
