# Standard Library
import io
import math
import random

# Third Party
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands

# Demolizzen
from demolizzen.core.bot import Demolizzen
from demolizzen.core.cog import BaseCog
from demolizzen.services import bank, guilds
from demolizzen.services.errors import BankError, InsufficientFunds


class Games(BaseCog):
    """
    Play games, but be careful not to gamble away everything.
    """

    key = "games"

    def __init__(self, bot: Demolizzen):
        super().__init__(bot)
        self.title = "Games"
        self.alias = "games"
        self.max_amount = 240

    games = SlashCommandGroup(
        "games", "Gamesystem", contexts=[discord.InteractionContextType.guild]
    )

    @staticmethod
    async def _refuse(ctx: discord.ApplicationContext, reason: str) -> None:
        await ctx.respond(
            embed=discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, {reason}",
            )
        )

    async def _settle(
        self, ctx: discord.ApplicationContext, amount: int, won: bool
    ) -> bool:
        """Book the bet. Tells the player and returns False if it cannot be placed."""
        await guilds.ensure_guild(ctx.guild.id, ctx.guild.name)
        try:
            await bank.wager(
                ctx.guild.id, ctx.author.id, ctx.author.display_name, amount, won
            )
        except InsufficientFunds:
            await self._refuse(ctx, "You not have enough :coin:")
            return False
        except BankError as error:
            await self._refuse(ctx, error.message)
            return False
        return True

    @games.command()
    @commands.guild_only()
    @commands.cooldown(5, 600, commands.BucketType.user)  # 5 per 10 minutes per member
    @option(
        "choose", description="Choose between", choices=["Rock", "Paper", "Scissors"]
    )
    async def rps(self, ctx: discord.ApplicationContext, choose: str):
        """
        Play a game of Rock Paper Scissors
        """
        bot_choices = ["Rock", "Paper", "Scissors"]
        bot_choice = random.choice(bot_choices)

        # Determine the winner
        # pylint: disable=too-many-boolean-expressions
        if choose == bot_choice:
            message = f"It's a draw! Both chose: {choose}"
        elif (
            (choose == "Rock" and bot_choice == "Scissors")
            or (choose == "Paper" and bot_choice == "Rock")
            or (choose == "Scissors" and bot_choice == "Paper")
        ):
            message = f"You win: {choose} vs {bot_choice}"
        else:
            message = f"You lose: {choose} vs {bot_choice}"

        await ctx.respond(message)

    @games.command()
    @commands.guild_only()
    @commands.cooldown(5, 600, commands.BucketType.user)  # 5 per 10 minutes per member
    @option(
        "amount", description="Specify the amount of Coins to bet in the slot machine."
    )
    async def slots(self, ctx: discord.ApplicationContext, amount: int):
        """
        Play a game of Slots with your bet of coins
        """
        if amount > self.max_amount:
            await self._refuse(ctx, f"The limit is {self.max_amount} :coin:")
            return

        final = [
            random.choice([":red_circle:", ":yellow_circle:", ":blue_circle:"])
            for _ in range(3)
        ]
        won = final[0] == final[1] == final[2]
        if not await self._settle(ctx, amount, won):
            return

        await ctx.respond(str(final))
        if won:
            description = f"{ctx.author.mention}, You won! {2 * amount} :coin:"
        else:
            description = f"{ctx.author.mention}, You lose!"
        await ctx.respond(
            embed=discord.Embed(
                title="", color=discord.Color.red(), description=description
            )
        )

    @games.command()
    @commands.guild_only()
    @commands.cooldown(5, 600, commands.BucketType.user)  # 5 per 10 minutes per member
    @option("amount", description="Specify the amount of Coins to dice.")
    async def dice(self, ctx: discord.ApplicationContext, amount: int):
        """
        Play a game of Dice with your bet of coins
        """
        if amount > self.max_amount:
            await self._refuse(ctx, f"The limit is {self.max_amount} :coin:")
            return

        dice1, dice2 = random.randint(1, 6), random.randint(1, 6)
        dice3, dice4 = random.randint(1, 6), random.randint(1, 6)
        won = dice1 > dice3 and dice2 > dice4
        if not await self._settle(ctx, amount, won):
            return

        em = discord.Embed(
            title="",
            color=discord.Color.red(),
            description=f"{ctx.author.mention}, gamble {amount} :coin: and throw the dice",
        )
        em.add_field(
            name="",
            value=f":game_die: {ctx.author.name}, You get {dice1} and {dice2}...",
            inline=False,
        )
        em.add_field(
            name="",
            value=f":game_die: {ctx.author.name}, He gets {dice3} and {dice4}...",
            inline=False,
        )
        if won:
            result = f"You won {2 * amount} :coin:"
        else:
            result = f"You lose {amount} :coin:"
        em.add_field(
            name="", value=f":game_die: {ctx.author.name}, {result}", inline=False
        )
        await ctx.respond(embed=em)

    @games.command()
    @commands.guild_only()
    async def roll(self, ctx: discord.ApplicationContext):
        """

        Play a game of Roll a number
        """
        n = random.randrange(1, 101)
        await ctx.respond(n)

    @games.command()
    @commands.guild_only()
    async def flipcoin(self, ctx: discord.ApplicationContext):
        """
        Just flip a Coin
        """
        n = random.randint(0, 1)
        await ctx.respond("Heads" if n == 1 else "Tails")

    # pylint: disable=too-many-locals, too-many-statements
    @games.command()
    @commands.guild_only()
    @option(
        "members",
        description="Example (e.g. @User1 @User2 @User3)",
        type=str,
        required=True,
    )
    @option(
        "spin_duration",
        description="Length of the animation in seconds (e.g. 5)",
        type=float,
        required=False,
        default=5.0,
    )
    @option(
        "end_hold",
        description="How long the final picture stays, in seconds (e.g. 2)",
        type=float,
        required=False,
        default=3.0,
    )
    async def wheelofnames(
        self,
        ctx: discord.ApplicationContext,
        members: str,
        spin_duration: float = 5.0,
        end_hold: float = 3.0,
    ):
        """Spin the wheel with multiple members, animated GIF"""
        try:
            await ctx.defer()
            member_names = members.split()
            if not member_names:
                await ctx.respond("No members specified.")
                return
            if len(member_names) != len(set(member_names)):
                await ctx.respond("Each name must be unique.")
                return
            if len(member_names) < 2:
                await ctx.respond("Please specify at least two members.")
                return

            # Try to resolve each input into a Member object
            resolved_members = []
            guild_members = ctx.guild.members
            for name in member_names:
                # If mention (<@!1234567890>), extract ID
                if name.startswith("<@") and name.endswith(">"):
                    member_id = (
                        name.replace("<@!", "").replace("<@", "").replace(">", "")
                    )
                    member = ctx.guild.get_member(int(member_id))
                    if member:
                        resolved_members.append(member)
                        continue
                # Otherwise search by name
                member = discord.utils.find(
                    lambda m, n=name: n in (m.display_name, m.name), guild_members
                )
                if member:
                    resolved_members.append(member)
            if not resolved_members:
                await ctx.respond("No valid members found.")
                return

            # Sort the names so the colours stay in the same order
            names = [m.display_name for m in resolved_members]
            names_sorted = sorted(names)
            base_colors = [
                "#FF6384",
                "#36A2EB",
                "#FFCE56",
                "#4BC0C0",
                "#9966FF",
                "#FF9F40",
                "#E7E9ED",
                "#B2FF66",
                "#FF66B2",
                "#66B2FF",
                "#B266FF",
                "#FFB266",
            ]
            color_map = {
                name: base_colors[i % len(base_colors)]
                for i, name in enumerate(names_sorted)
            }

            # Animationseinstellungen
            size, center, radius = 500, 250, 240
            num_sectors = len(names)
            font_size = 28
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()
            fps = 15
            frame_duration = int(1000 / fps)
            steps = int(spin_duration * fps)
            end_hold_ms = int(end_hold * 1000)

            def draw_wheel_frame(angle_offset):
                img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
                draw = ImageDraw.Draw(img)
                border_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                border_draw = ImageDraw.Draw(border_layer)
                border_draw.ellipse(
                    [5, 5, size - 5, size - 5], outline="black", width=12
                )
                border_layer = border_layer.filter(ImageFilter.GaussianBlur(radius=3))
                img = Image.alpha_composite(img, border_layer)
                draw = ImageDraw.Draw(img)
                start_angle = angle_offset
                for _, name in enumerate(names):
                    end_angle = start_angle + 360 / num_sectors
                    draw.pieslice(
                        [10, 10, size - 10, size - 10],
                        start=start_angle,
                        end=end_angle,
                        fill=color_map[name],
                        outline="black",
                    )
                    mid_angle = math.radians((start_angle + end_angle) / 2)
                    text_radius = radius * 0.7
                    x = center + text_radius * math.cos(mid_angle)
                    y = center + text_radius * math.sin(mid_angle)
                    text = name
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    for ox in [-1, 0, 1]:
                        for oy in [-1, 0, 1]:
                            if ox != 0 or oy != 0:
                                draw.text(
                                    (x - text_width / 2 + ox, y - text_height / 2 + oy),
                                    text,
                                    fill="black",
                                    font=font,
                                )
                    draw.text(
                        (x - text_width / 2, y - text_height / 2),
                        text,
                        fill="white",
                        font=font,
                    )
                    start_angle = end_angle
                pointer_length = 40
                pointer_width = 22
                pointer = [
                    (center, center - radius + 10),
                    (
                        center - pointer_width // 2,
                        center - radius - pointer_length + 10,
                    ),
                    (
                        center + pointer_width // 2,
                        center - radius - pointer_length + 10,
                    ),
                ]
                draw.polygon(pointer, fill="white", outline="black")
                draw.line([pointer[0], pointer[1]], fill="black", width=2)
                draw.line([pointer[0], pointer[2]], fill="black", width=2)
                draw.line([pointer[1], pointer[2]], fill="black", width=2)
                frame_rgb = Image.new("RGB", (size, size), (255, 255, 255))
                frame_rgb.paste(img.convert("RGB"), mask=img.split()[3])
                return frame_rgb

            frames = [draw_wheel_frame((360 / steps) * step) for step in range(steps)]
            frames.extend([frames[-1]] * max(1, end_hold_ms // frame_duration))

            buf = io.BytesIO()
            frames[0].save(
                buf,
                format="GIF",
                save_all=True,
                append_images=frames[1:],
                duration=[frame_duration] * (len(frames) - 1) + [end_hold_ms],
                loop=0,
                disposal=2,
            )
            buf.seek(0)

            winner_idx = random.randint(0, num_sectors - 1)
            winner = names[winner_idx]
            file = discord.File(buf, filename="wheelspin.gif")
            await ctx.respond(f"🎉 Gewinner: **{winner}**", file=file)
        except Exception as e:
            self.bot.logger.error(f"[Wheelspin Command] {e}", exc_info=True)
            await ctx.respond(
                "Something went wrong. Please try again later.", ephemeral=True
            )
            return
