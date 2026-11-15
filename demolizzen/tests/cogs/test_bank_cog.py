# Standard Library
import inspect
from unittest.mock import MagicMock

# Django
from django.test import SimpleTestCase, TestCase

# Demolizzen
from demolizzen.cogs.banksystem import banksystem, banksystem_admin
from demolizzen.cogs.banksystem.banksystem import Bank
from demolizzen.cogs.banksystem.banksystem_admin import BankAdmin
from demolizzen.models import UserBankAccount
from demolizzen.services import bank, guilds
from demolizzen.services.bank import Balance
from demolizzen.tests.helpers import make_ctx, make_guild, make_member


class BankCogTestCase(TestCase):
    def setUp(self):
        self.guild = make_guild(1, "Alpha")
        self.alice = make_member(10, "alice", guild=self.guild)
        self.bob = make_member(11, "bob", guild=self.guild)
        self.alice.mention, self.bob.mention = "<@10>", "<@11>"
        self.cog = Bank(MagicMock())
        self.admin = BankAdmin(MagicMock())

    def ctx(self, author=None):
        return make_ctx(guild=self.guild, author=author or self.alice)

    async def fund(self, member, wallet=0, balance=0):
        await guilds.ensure_guild(1, "Alpha")
        account = await bank.ensure_account(1, member.id, member.name)
        await UserBankAccount.objects.filter(pk=account.pk).aupdate(
            wallet=wallet, bank=balance
        )

    async def balance(self, member) -> Balance:
        account = await UserBankAccount.objects.aget(user__user_id=member.id)
        return Balance(account.wallet, account.bank)

    @staticmethod
    def text(ctx) -> str:
        call = ctx.respond.await_args
        return call.args[0] if call.args else call.kwargs.get("content", "")

    @staticmethod
    def is_private(ctx) -> bool:
        return bool(ctx.respond.await_args.kwargs.get("ephemeral"))


class BankCommandTest(BankCogTestCase):
    async def test_balance_shows_wallet_bank_and_interest(self):
        await self.fund(self.alice, wallet=40, balance=60)
        ctx = self.ctx()

        await self.cog.balance.callback(self.cog, ctx)

        embed = ctx.respond.await_args.kwargs["embed"]
        self.assertIn("$40", embed.fields[0].value)
        self.assertIn("$60", embed.fields[1].value)
        self.assertIn("0.1%", embed.fields[1].value)

    async def test_balance_works_in_an_unregistered_guild(self):
        ctx = self.ctx()

        await self.cog.balance.callback(self.cog, ctx)

        self.assertEqual(await self.balance(self.alice), Balance(0, 0))

    async def test_deposit_moves_money_and_confirms(self):
        await self.fund(self.alice, wallet=100)
        ctx = self.ctx()

        await self.cog.deposit.callback(self.cog, ctx, 60)

        self.assertEqual(await self.balance(self.alice), Balance(40, 60))
        self.assertEqual(self.text(ctx), "You deposited 60 :coin:!")

    async def test_deposit_too_much_is_refused_ephemeral(self):
        await self.fund(self.alice, wallet=100)
        ctx = self.ctx()

        await self.cog.deposit.callback(self.cog, ctx, 500)

        self.assertEqual(await self.balance(self.alice), Balance(100, 0))
        self.assertEqual(self.text(ctx), "You don't have that much money!")
        self.assertTrue(self.is_private(ctx))

    async def test_negative_amount_is_refused(self):
        await self.fund(self.alice, wallet=100)
        ctx = self.ctx()

        await self.cog.deposit.callback(self.cog, ctx, -5)

        self.assertEqual(self.text(ctx), "Amount must be at least 1.")

    async def test_deposit_when_disabled_tells_user(self):
        await self.fund(self.alice, wallet=100)
        await bank.update_settings(1, allow_deposits=False)
        ctx = self.ctx()

        await self.cog.deposit.callback(self.cog, ctx, 60)

        self.assertEqual(self.text(ctx), "Deposits are disabled on this server.")

    async def test_withdraw_moves_money(self):
        await self.fund(self.alice, balance=100)
        ctx = self.ctx()

        await self.cog.withdraw.callback(self.cog, ctx, 30)

        self.assertEqual(await self.balance(self.alice), Balance(30, 70))
        self.assertEqual(self.text(ctx), "You Withdraw 30 :coin:!")

    async def test_send_moves_money_to_member(self):
        await self.fund(self.alice, wallet=100)
        ctx = self.ctx()

        await self.cog.send.callback(self.cog, ctx, self.bob, 30)

        self.assertEqual(await self.balance(self.alice), Balance(70, 0))
        self.assertEqual(await self.balance(self.bob), Balance(30, 0))
        self.assertEqual(self.text(ctx), "You gave 30:coin:! to <@11>")

    async def test_send_to_self_and_to_bot_is_refused(self):
        await self.fund(self.alice, wallet=100)
        robot = make_member(99, "robot", bot=True, guild=self.guild)

        to_self = self.ctx()
        await self.cog.send.callback(self.cog, to_self, self.alice, 30)
        to_bot = self.ctx()
        await self.cog.send.callback(self.cog, to_bot, robot, 30)

        self.assertEqual(self.text(to_self), "You can't send to yourself...")
        self.assertEqual(self.text(to_bot), "You can't send money to a bot.")
        self.assertEqual(await self.balance(self.alice), Balance(100, 0))
        self.assertFalse(
            await UserBankAccount.objects.filter(user__user_id=99).aexists()
        )

    async def test_bank_has_no_create_command(self):
        names = [command.name for command in self.cog.bank.subcommands]

        self.assertEqual(sorted(names), ["balance", "deposit", "send", "withdraw"])


class BankAdminCommandTest(BankCogTestCase):
    async def test_give_money_works_for_member_without_profile(self):
        ctx = self.ctx()

        await self.admin.give_money.callback(self.admin, ctx, self.bob, 500)

        self.assertEqual(await self.balance(self.bob), Balance(500, 0))
        self.assertEqual(self.text(ctx), "You gave 500:coin:! to <@11>")
        self.assertTrue(self.is_private(ctx))

    async def test_give_money_refuses_bad_amount(self):
        ctx = self.ctx()

        await self.admin.give_money.callback(self.admin, ctx, self.bob, 0)

        self.assertEqual(self.text(ctx), "Amount must be at least 1.")

    async def test_remove_money_takes_at_most_what_is_there(self):
        await self.fund(self.bob, wallet=40, balance=10)
        ctx = self.ctx()

        await self.admin.remove_money.callback(self.admin, ctx, self.bob, 100, "wallet")

        self.assertEqual(await self.balance(self.bob), Balance(0, 10))
        self.assertEqual(self.text(ctx), "You removed 40:coin:! from <@11>")

    async def test_remove_money_from_bank(self):
        await self.fund(self.bob, wallet=40, balance=10)

        await self.admin.remove_money.callback(
            self.admin, self.ctx(), self.bob, 5, "bank"
        )

        self.assertEqual(await self.balance(self.bob), Balance(40, 5))

    async def test_remove_bank_resets_both_balances(self):
        await self.fund(self.bob, wallet=40, balance=10)
        ctx = self.ctx()

        await self.admin.reset_money.callback(self.admin, ctx, self.bob)

        self.assertEqual(await self.balance(self.bob), Balance(0, 0))
        self.assertEqual(self.text(ctx), "Bankaccount from <@11> has been reset.")


class BankCogSourceTest(SimpleTestCase):
    def test_cogs_contain_no_orm_access(self):
        for module in (banksystem, banksystem_admin):
            with self.subTest(module=module.__name__):
                self.assertNotIn(".objects.", inspect.getsource(module))
