# Discord
import discord
from discord import option
from discord.commands import SlashCommandGroup
from discord.ext import commands

# Django
from django.utils import timezone

# Demolizzen
from demolizzen import models
from demolizzen.cogs.banksystem import Bank
from demolizzen.cogs.economy import Economy
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

    owner = SlashCommandGroup(
        "owner", "Owner Commands", contexts=[discord.InteractionContextType.guild]
    )

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
    killmail = admin.create_subgroup(
        "killmail", contexts=[discord.InteractionContextType.guild]
    )

    # ---------------------------- Moderation ----------------------------
    # ---------------------------- Moderation ----------------------------
    # ---------------------------- Moderation ----------------------------

    @mod.command()
    @checks.is_mod()
    @option("limit", description="How many")
    async def clear(self, ctx: discord.ApplicationContext, limit: int):
        """
        Clear Message from a Channel
        """
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
    @checks.is_mod()
    @option("user", description="Wähle User")
    @option("role", description="Wähle Rolle")
    async def role(
        self, ctx: discord.ApplicationContext, user: discord.Member, role: discord.Role
    ):
        """
        Give a Role to a User
        """

        if ctx.author.top_role.position < user.top_role.position:
            return await ctx.respond("Du kannst seine Rolle nicht ändern.")
        try:
            await user.add_roles(role)
            await ctx.respond(f"{role} an {user.mention} hinzugefügt!")
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
            else:
                self.bot.logger.error(e, exc_info=True)
                embed = discord.Embed(description="❌ Something went wrong try later.")
        await ctx.respond(embed=embed, ephemeral=True, delete_after=10)

    @mod.command()
    @checks.is_mod()
    @option("user", description="Wähle User")
    @option("derole", description="Wähle Rolle")
    async def derole(self, ctx, user: discord.Member, role: discord.Role):
        """
        Remove a Role to a User
        """

        if ctx.author.top_role.position < user.top_role.position:
            return await ctx.respond("Du kannst seine Rolle nicht ändern.")
        try:
            await user.remove_roles(role)
            await ctx.respond(f"{role} an {user.mention} entfernt!")
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
            else:
                self.bot.logger.error(e, exc_info=True)
                embed = discord.Embed(description="❌ Something went wrong try later.")
        await ctx.respond(embed=embed, ephemeral=True, delete_after=10)

    # ---------------------------- Mission System ----------------------------
    # ---------------------------- Mission System ----------------------------
    # ---------------------------- Mission System ----------------------------

    @economy.command()
    @checks.is_botmanager()
    @option(
        "action",
        description="Start or Stop the Event for the Mining/Raid System",
        choices=["On", "Off", "Status"],
    )
    async def mode(self, ctx, action: str):
        """
        Start or Stop the Event for the Mining/Raid System
        """

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

    @economy.command()
    @checks.is_botmanager()
    @option("amount", description="Multiply the Loan")
    async def set(self, ctx, amount: int):
        """
        Set the Event Faktor as Multiplier
        """
        server_id = ctx.guild.id

        EVENTS_SERVER[server_id] = (True, int(amount))
        await ctx.respond(
            f"🟢 Event wurde aktiviert und der Faktor auf x {amount} gesetzt."
        )
        return

    # ---------------------------- Bank System ----------------------------
    # ---------------------------- Bank System ----------------------------
    # ---------------------------- Bank System ----------------------------

    @bank.command(name="give-money")
    @checks.is_botmanager()
    @option("member", description="Choose Member")
    @option("amount", description="Specify the amount of Coins to Give")
    async def give_money(
        self, ctx: discord.ApplicationContext, member: discord.Member, amount: int
    ):
        """
        Give money to a specific user
        """
        amount = int(amount)
        if amount < 0:
            await ctx.respond("Amount must be positive!")
            return

        try:
            user = await models.UserProfile.objects.select_related("bank_account").aget(
                user_id=member.id, guild_id=ctx.guild.id
            )
            bank_account = user.bank_account
        except models.BankAccount.DoesNotExist:
            bank_account = await models.BankAccount.objects.acreate(
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
    @checks.is_botmanager()
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
        """
        Remove money from a specific user
        """
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
        except models.BankAccount.DoesNotExist:
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
    @checks.is_botmanager()
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
        except models.BankAccount.DoesNotExist:
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

    # ---------------------------- Bank System ----------------------------
    # ---------------------------- Bank System ----------------------------
    # ---------------------------- Bank System ----------------------------

    @killmail.command(name="analyze")
    @checks.is_owner()
    async def killmail_counter(self, ctx):
        """
        Owner Only - Bug Fixing
        """
        self.bot.logger.info("Char Names: %s", self.bot.esi_data._entity_name_cache)
        self.bot.logger.info(
            "System Names: %s", self.bot.esi_data._system_id_name_cache
        )
        self.bot.logger.info("Region Names: %s", self.bot.esi_data._region_id_cache)
        await ctx.respond("Daten gespeichert")

    @owner.command(name="force-deposits-update")
    @checks.is_owner()
    async def trigger_deposit_update(self, ctx: discord.ApplicationContext):
        banksystem_cog: Bank = self.bot.get_cog("Bank")
        await banksystem_cog.process_daily_interest()
        await ctx.respond("Deposit Update Triggered.", ephemeral=True)

    @owner.command(name="force-ship-update")
    @checks.is_owner()
    async def trigger_ship_update(self, ctx: discord.ApplicationContext):
        shopsystem_cog: Economy = self.bot.get_cog("Eco")
        await shopsystem_cog.fetch_ship_data()
        await ctx.respond("Ship Data Update Triggered.", ephemeral=True)

    @owner.command(
        name="sync",
        description="Synchonizes the slash commands.",
    )
    @commands.is_owner()
    @option(
        "scope",
        description="The scope of the sync. Can be `global` or `guild`.",
        choices=["global", "guild"],
    )
    async def sync(self, context: discord.ApplicationContext, scope: str) -> None:
        """
        Synchonizes the slash commands.

        :param context: The command context.
        :param scope: The scope of the sync. Can be `global` or `guild`.
        """

        if scope == "global":
            await context.bot.sync_commands()
            embed = discord.Embed(
                description="Slash commands have been globally synchronized.",
                color=0xBEBEFE,
            )
            await context.respond(embed=embed)
            return
        await context.bot.sync_commands(guild_ids=[context.guild.id])
        embed = discord.Embed(
            description="Slash commands have been synchronized in this guild.",
            color=0xBEBEFE,
        )
        await context.respond(embed=embed, ephemeral=True)
        return

    @owner.command(
        name="load",
        description="Load a cog",
    )
    @commands.is_owner()
    async def load(self, ctx: discord.ApplicationContext, cog: str) -> None:
        """
        The bot will load the given cog.

        :param context: The hybrid command context.
        :param cog: The name of the cog to load.
        """
        try:
            self.bot.load_extension(f"demolizzen.cogs.{cog}")
        except Exception:
            embed = discord.Embed(
                description=f"Could not load the `{cog}` cog.", color=0xE02B2B
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(
            description=f"Successfully loaded the `{cog}` cog.", color=0xBEBEFE
        )
        await ctx.respond(embed=embed, ephemeral=True)

    @owner.command(
        name="unload",
        description="Unloads a cog.",
    )
    @commands.is_owner()
    async def unload(self, ctx: discord.ApplicationContext, cog: str) -> None:
        """
        The bot will unload the given cog.

        :param context: The hybrid command context.
        :param cog: The name of the cog to unload.
        """
        try:
            self.bot.unload_extension(f"demolizzen.cogs.{cog}")
        except Exception:
            embed = discord.Embed(
                description=f"Could not unload the `{cog}` cog.", color=0xE02B2B
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(
            description=f"Successfully unloaded the `{cog}` cog.", color=0xBEBEFE
        )
        await ctx.respond(embed=embed, ephemeral=True)

    @owner.command(
        name="reload",
        description="Reloads a cog.",
    )
    @commands.is_owner()
    async def reload(self, ctx: discord.ApplicationContext, cog: str) -> None:
        """
        The bot will reload the given cog.

        :param context: The hybrid command context.
        :param cog: The name of the cog to reload.
        """
        try:
            self.bot.reload_extension(f"demolizzen.cogs.{cog}")
        except Exception as e:
            self.bot.logger.error(e, exc_info=True)
            embed = discord.Embed(
                description=f"Could not reload the `{cog}` cog.", color=0xE02B2B
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(
            description=f"Successfully reloaded the `{cog}` cog.", color=0xBEBEFE
        )
        await ctx.respond(embed=embed, ephemeral=True)
