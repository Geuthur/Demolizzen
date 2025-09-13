# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands

# Django
from django.utils import timezone

# Demolizzen
from demolizzen import models
from demolizzen.config import EVENTS_SERVER
from demolizzen.core import checks
from demolizzen.core.bot import Demolizzen


class Admin(commands.Cog):
    """
    Secure the Server with automated Moderation Tools
    """

    def __init__(self, bot: Demolizzen):
        self.bot = bot
        self.title = "Admin"
        self.alias = "admin"
        self.command_ids = {}

    admin = SlashCommandGroup(
        "admin", "Adminsystem", contexts=[discord.InteractionContextType.guild]
    )
    mod = SlashCommandGroup(
        "moderation",
        "Moderation System",
        contexts=[discord.InteractionContextType.guild],
    )
    bank = admin.create_subgroup(
        "bank", contexts=[discord.InteractionContextType.guild]
    )
    economy = admin.create_subgroup(
        "economy", contexts=[discord.InteractionContextType.guild]
    )

    # ---------------------------- Moderation ----------------------------
    # ---------------------------- Moderation ----------------------------
    # ---------------------------- Moderation ----------------------------

    @mod.command()
    @commands.guild_only()
    @checks.is_mod()
    @option("limit", description="How many")
    async def clear(self, ctx: discord.ApplicationContext, limit: int):
        """Clear Message from a Channel."""
        # await ctx.defer(ephemeral=True)

        if limit > 100:
            embed = discord.Embed(
                description="❌ No more than 100 messages can be purged at a time."
            )
            await ctx.respond(embed=embed, ephemeral=True, delete_after=20)
            return

        # Fetching the messages to delete
        # messages = await ctx.channel.history(limit=limit).flatten()
        # Fetching the messages to delete, only considering messages within the last 14 days
        try:
            messages = await ctx.channel.history(
                limit=limit,
                after=timezone.datetime.now() - timezone.timedelta(days=14),
                oldest_first=False,
            ).flatten()
        except discord.HTTPException as e:
            if e.code == 50001:  # Messages are older than 14 days
                pass
                # embed = discord.Embed(description="❌ I have no permission to see that channel...")
            else:
                self.bot.logger.error(e, exc_info=True)
                embed = discord.Embed(description="❌ Something went wrong try later.")
            return False

        if messages:
            try:
                # Try bulk deleting the messages
                await ctx.channel.delete_messages(messages)
                embed = discord.Embed(
                    description=f"✅ Deleted {len(messages)} message(s) bulk delete."
                )
            except discord.HTTPException as e:
                if e.code == 50034:  # Messages are older than 14 days
                    embed = discord.Embed(
                        description="❌ You can only bulk delete messages that are under 14 days old."
                    )
                elif e.code == 50013:  # No Permission
                    embed = discord.Embed(
                        description="❌ I have no permission to do that..."
                    )
                else:
                    self.bot.logger.error(e, exc_info=True)
                    embed = discord.Embed(
                        description="❌ Something went wrong try later."
                    )
        else:
            embed = discord.Embed(
                description="❌ No messages older than 14 days to delete."
            )
        await ctx.respond(embed=embed, ephemeral=True, delete_after=10)

    @mod.command()
    @commands.guild_only()
    @checks.is_mod()
    @option("user", description="Choose User")
    @option("role", description="Choose Role")
    async def role(
        self, ctx: discord.ApplicationContext, user: discord.Member, role: discord.Role
    ):
        """Give a Role to a User. Works Hierarchically."""

        if ctx.author.top_role.position < user.top_role.position:
            return await ctx.respond("You cannot give a role to this user.")
        try:
            await user.add_roles(role)
            await ctx.respond(f"{role} has been added to {user.mention}!")
            return
        except discord.HTTPException as e:
            if e.code == 50013:  # No Permission
                embed = discord.Embed(
                    description="❌ I have no permission to do that..."
                )
            elif e.code == 50001:  # No Permission
                embed = discord.Embed(
                    description="❌ I have no permission to do that..."
                )
            self.bot.logger.error(e, exc_info=True)
            embed = discord.Embed(description="❌ Something went wrong try later.")
        await ctx.respond(embed=embed, ephemeral=True, delete_after=10)

    @mod.command()
    @commands.guild_only()
    @checks.is_mod()
    @option("user", description="Choose User")
    @option("derole", description="Choose Role")
    async def derole(
        self, ctx: discord.ApplicationContext, user: discord.Member, role: discord.Role
    ):
        """Remove a Role from a User."""

        if ctx.author.top_role.position < user.top_role.position:
            return await ctx.respond("You cannot remove a role from this user.")
        try:
            await user.remove_roles(role)
            await ctx.respond(f"{role} has been removed from {user.mention}!")
            return
        except discord.HTTPException as e:
            if e.code == 50013:  # No Permission
                embed = discord.Embed(
                    description="❌ I have no permission to do that..."
                )
            elif e.code == 50001:  # No Access
                embed = discord.Embed(
                    description="❌ I have no permission to do that..."
                )
            self.bot.logger.error(e, exc_info=True)
            embed = discord.Embed(description="❌ Something went wrong try later.")
        await ctx.respond(embed=embed, ephemeral=True, delete_after=10)

    # ---------------------------- Mission System ----------------------------
    # ---------------------------- Mission System ----------------------------
    # ---------------------------- Mission System ----------------------------

    @economy.command(
        name="mode", description="Start or Stop the Event for the Economy System"
    )
    @commands.guild_only()
    @checks.is_admin()
    @option(
        "action",
        description="Start or Stop the Event for the Economy System",
        choices=["On", "Off", "Status"],
    )
    async def mode(self, ctx, action: str):
        """Start or Stop the Event for the Economy System."""

        server_id = ctx.guild.id

        if server_id in EVENTS_SERVER:
            events, event_factor = EVENTS_SERVER[server_id]
        else:
            EVENTS_SERVER[server_id] = (False, 0)
            events, event_factor = EVENTS_SERVER[server_id]

        if action == "Status":
            if events:
                await ctx.respond(f"🟢 Event ist aktiv.\n Faktor: {event_factor}")
            else:
                await ctx.respond(f"🔴 Event ist nicht aktiv.\n Faktor: {event_factor}")

        if action == "On":
            EVENTS_SERVER[server_id] = (True, int(event_factor))
            await ctx.respond("🟢 Event wurde aktiviert.")
            return

        if action == "Off":
            EVENTS_SERVER[server_id] = (False, int(event_factor))
            await ctx.respond("🔴 Event wurde deaktiviert.")
            return

    @economy.command(name="set", description="Set the Event Faktor as Multiplier")
    @checks.is_admin()
    @option("amount", description="Multiply the Loan")
    async def set(self, ctx, amount: int):
        """Set the Event Faktor as Multiplier."""
        server_id = ctx.guild.id

        EVENTS_SERVER[server_id] = (True, int(amount))
        await ctx.respond(f"🟢 Event has been set to x {amount}.")
        return

    # ---------------------------- Bank System ----------------------------
    # ---------------------------- Bank System ----------------------------
    # ---------------------------- Bank System ----------------------------

    @bank.command(name="give-money")
    @checks.is_admin()
    @option("member", description="Choose Member")
    @option("amount", description="Specify the amount of Coins to Give")
    async def give_money(
        self, ctx: discord.ApplicationContext, member: discord.Member, amount: int
    ):
        """Give money to a specific user."""
        amount = int(amount)
        if amount < 0:
            await ctx.respond("Amount must be positive!")
            return

        try:
            user = await models.UserProfile.objects.select_related("bank_account").aget(
                user_id=member.id, guild_id=ctx.guild.id
            )
            bank_account = user.bank_account
        except models.UserBankAccount.DoesNotExist:
            bank_account = await models.UserBankAccount.objects.acreate(
                user=user,
            )

        bank_account.wallet += amount
        # Update the bank account with the new amount
        await bank_account.asave()

        await ctx.respond(
            f"You gave {amount}:coin:! to {member.mention}", ephemeral=True
        )
        return

    @bank.command(name="remove-money")
    @checks.is_admin()
    @option("member", description="Choose Member")
    @option("amount", description="Specify the amount of Coins to Remove")
    @option("konto", description="Choose Account", choices=["wallet", "bank"])
    async def remove_money(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        amount: int,
        konto: str,
    ):
        """Remove money from a specific user."""
        # Get Server-ID for further process
        server_id = ctx.guild.id

        if amount < 0:
            await ctx.respond("Amount must be positive!")
            return

        if konto not in ["wallet", "bank"]:
            await ctx.respond("Invalid account type selected.")
            return

        # Fetch the bank account for the member
        try:
            user = await models.UserProfile.objects.select_related("bank_account").aget(
                user_id=member.id, guild_id=server_id
            )
            bank_account = user.bank_account
        except models.UserBankAccount.DoesNotExist:
            await ctx.respond(f"❌ {member.name}, has no bank account.", ephemeral=True)
            return

        # If the account exists, check the account type and adjust the balance accordingly
        if konto == "wallet":
            amount = min(amount, bank_account.wallet)
            bank_account.wallet -= amount
        elif konto == "bank":
            amount = min(amount, bank_account.bank)
            bank_account.bank -= amount

        # Update the account in the database
        await bank_account.asave()

        await ctx.respond(
            f"You removed {amount}:coin:! from {member.mention}", ephemeral=True
        )
        return

    @bank.command(name="remove-bank")
    @checks.is_admin()
    @option("member", description="Choose Member")
    async def reset_money(
        self, ctx: discord.ApplicationContext, member: discord.Member
    ):
        """
        Reset Bankaccount from Member
        """
        # Fetch the bank account for the member
        try:
            user = await models.UserProfile.objects.select_related("bank_account").aget(
                user_id=member.id, guild_id=ctx.guild.id
            )
            bank_account = user.bank_account
        except models.UserBankAccount.DoesNotExist:
            await ctx.respond(f"❌ {member.name}, has no bank account.", ephemeral=True)
            return

        # Reset the bank account from the database
        bank_account.wallet = 0
        bank_account.bank = 0

        # Update the account in the database
        await bank_account.asave()

        await ctx.respond(
            f"Bankaccount from {member.mention} has been reset.", ephemeral=True
        )
        return
