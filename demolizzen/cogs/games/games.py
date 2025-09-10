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
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen
from demolizzen.models import UserBankAccount
from demolizzen.utils.functions import application_cooldown


class Games(commands.Cog):
    """
    Play games, but be careful not to gamble away everything.
    """

    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.title = "Games"
        self.alias = "games"
        self.max_amount = 240

    games = SlashCommandGroup(
        "games", "Gamesystem", contexts=[discord.InteractionContextType.guild]
    )

    @games.command()
    @commands.guild_only()
    @checks.is_in_channel()
    @commands.cooldown(
        5, 600, commands.BucketType.user
    )  # 5 Mal alle 10 Minuten pro Benutzer
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

    @rps.error
    async def command_cooldown(self, ctx: discord.ApplicationContext, error):
        await application_cooldown(ctx, error)

    @games.command()
    @commands.guild_only()
    @checks.is_in_channel()
    @commands.cooldown(
        5, 600, commands.BucketType.user
    )  # 5 Mal alle 10 Minuten pro Benutzer
    @option(
        "amount", description="Specify the amount of Coins to bet in the slot machine."
    )
    async def slots(self, ctx: discord.ApplicationContext, amount: int):
        """
        Play a game of Slots with your bet of coins
        """
        # Get Server-ID for further process
        server_id = ctx.guild.id

        try:
            bank_account = await UserBankAccount.get(
                session=self.bot.sessionmaker(),
                user_id=ctx.author.id,
                guild_id=server_id,
            )

            if bank_account is None:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, You don't have a bank account. Create one with /bank create",
                )
                await ctx.respond(embed=em)
                return

            if amount > bank_account.wallet:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, You not have enough :coin:",
                )
                await ctx.respond(embed=em)
                return
            if amount < 0:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, The number must be positive",
                )
                await ctx.respond(embed=em)
                return
            if amount > self.max_amount:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, The limit is {self.max_amount} :coin:",
                )
                await ctx.respond(embed=em)
                return

            final = []
            for _ in range(3):
                a = random.choice([":red_circle:", ":yellow_circle:", ":blue_circle:"])

                final.append(a)

            await ctx.respond(str(final))

            if final[0] == final[0] and final[0] == final[1] and final[0] == final[2]:
                bank_account.wallet += 2 * amount
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, You won! {3 * amount} :coin:",
                )
            else:
                bank_account.wallet -= amount
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, You lose!",
                )

            # Update the bank account
            await bank_account.save(self.bot.sessionmaker())

            # Send Message
            await ctx.respond(embed=em)
        # pylint: disable=broad-except
        except Exception as e:
            self.bot.logger.error(f"[Slots Command] • {e}", exc_info=True)
            await ctx.respond(
                "Something went wrong, please try again later", ephemeral=True
            )
            return

    @slots.error
    async def slots_cooldown(self, ctx: discord.ApplicationContext, error):
        await application_cooldown(ctx, error)

    @games.command()
    @commands.guild_only()
    @checks.is_in_channel()
    @commands.cooldown(
        5, 600, commands.BucketType.user
    )  # 5 Mal alle 10 Minuten pro Benutzer
    @option("amount", description="Specify the amount of Coins to dice.")
    async def dice(self, ctx: discord.ApplicationContext, amount: int):
        """
        Play a game of Dice with your bet of coins
        """
        # Get Server-ID for further process
        server_id = ctx.guild.id

        try:
            bank_account = await UserBankAccount.get(
                session=self.bot.sessionmaker(),
                user_id=ctx.author.id,
                guild_id=server_id,
            )

            if bank_account is None:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, You don't have a bank account. Create one with /bank create",
                )
                await ctx.respond(embed=em)
                return

            if amount > bank_account.wallet:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, You not have enough :coin:",
                )
                await ctx.respond(embed=em)
                return
            if amount < 0:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, The number must be positive",
                )
                await ctx.respond(embed=em)
                return
            if amount > self.max_amount:
                em = discord.Embed(
                    title="",
                    color=discord.Color.red(),
                    description=f"{ctx.author.mention}, The limit is {self.max_amount} :coin:",
                )
                await ctx.respond(embed=em)
                return

            em = discord.Embed(
                title="",
                color=discord.Color.red(),
                description=f"{ctx.author.mention}, gamble {amount} :coin: and throw the dice",
            )
            dice1 = random.randrange(1, 6)
            dice2 = random.randrange(1, 6)
            em.add_field(
                name="",
                value=f":game_die: {ctx.author.name}, You get {dice1} and {dice2}...",
                inline=False,
            )
            dice3 = random.randrange(1, 6)
            dice4 = random.randrange(1, 6)
            em.add_field(
                name="",
                value=f":game_die: {ctx.author.name}, He gets {dice3} and {dice4}...",
                inline=False,
            )
            if dice1 > dice3 and dice2 > dice4:
                bank_account.wallet += 2 * amount
                em.add_field(
                    name="",
                    value=f":game_die: {ctx.author.name}, You won {amount} :coin:",
                    inline=False,
                )
            else:
                bank_account.wallet -= amount
                em.add_field(
                    name="",
                    value=f":game_die: {ctx.author.name}, You lose {amount} :coin:",
                    inline=False,
                )

            # Update the bank account
            await bank_account.save(self.bot.sessionmaker())

            # Send Message
            await ctx.respond(embed=em)
        # pylint: disable=broad-except
        except Exception as e:
            self.bot.logger.error(f"[Dice Command] • {e}", exc_info=True)
            await ctx.respond(
                "Something went wrong, please try again later.", ephemeral=True
            )
            return

    @dice.error
    async def dice_cooldown(self, ctx: discord.ApplicationContext, error):
        await application_cooldown(ctx, error)

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
        description="Dauer der Animation in Sekunden (z.B. 5)",
        type=float,
        required=False,
        default=5.0,
    )
    @option(
        "end_hold",
        description="Dauer wie lange das Endbild steht in Sekunden (z.B. 2)",
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
                # Sonst nach Namen suchen
                member = discord.utils.find(
                    lambda m, n=name: n in (m.display_name, m.name), guild_members
                )
                if member:
                    resolved_members.append(member)
            if not resolved_members:
                await ctx.respond("No valid members found.")
                return

            # Sortiere Namen für konstante Farbreihenfolge
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
