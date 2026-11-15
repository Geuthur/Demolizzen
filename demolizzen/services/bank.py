"""The bank: accounts and bookings.

Every booking runs in a transaction on locked rows and reads the balances from
the database. Two bookings at the same time therefore cannot create or destroy
money, which they could while balances were changed on objects in memory.
"""

# Standard Library
from dataclasses import dataclass

# Third Party
from asgiref.sync import sync_to_async

# Django
from django.db import transaction

# Demolizzen
from demolizzen.models import GuildBankSettings, UserBankAccount, UserProfile
from demolizzen.services import guilds
from demolizzen.services.errors import (
    BankActionDisabled,
    InsufficientFunds,
    InvalidAmount,
    InvalidTransfer,
)

# Largest amount a single booking may move.
MAX_AMOUNT = 1_000_000_000_000

ACCOUNT_KINDS = ("wallet", "bank")


@dataclass(frozen=True)
class Balance:
    """What a member owns: money at hand and money in the bank."""

    wallet: int
    bank: int


def _check_amount(amount) -> None:
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 1:
        raise InvalidAmount("Amount must be at least 1.")
    if amount > MAX_AMOUNT:
        raise InvalidAmount("Amount is too large.")


def _check_kind(account: str) -> None:
    if account not in ACCOUNT_KINDS:
        raise ValueError(f"Unknown account kind '{account}'.")


def _balance(account: UserBankAccount) -> Balance:
    return Balance(wallet=account.wallet, bank=account.bank)


def _lock_accounts(*account_ids: int) -> list[UserBankAccount]:
    """Lock the accounts for the current transaction.

    They are always locked in primary key order, so two transfers in opposite
    directions cannot wait for each other forever.
    """
    return list(
        UserBankAccount.objects.select_for_update()
        .filter(pk__in=account_ids)
        .order_by("pk")
    )


async def ensure_account(
    guild_id: int, user_id: int, user_name: str
) -> UserBankAccount:
    """Return the member's bank account, creating profile and account if needed."""
    await guilds.ensure_members(guild_id, [(user_id, user_name)])
    profile = (
        await UserProfile.objects.filter(guild_id=guild_id, user_id=user_id)
        .order_by("pk")
        .afirst()
    )
    account, _ = await UserBankAccount.objects.aget_or_create(user=profile)
    return account


async def get_balance(guild_id: int, user_id: int, user_name: str) -> Balance:
    """Return what the member owns."""
    return _balance(await ensure_account(guild_id, user_id, user_name))


def _move_sync(
    guild_id: int, account_id: int, source: str, target: str, amount: int
) -> Balance:
    with transaction.atomic():
        settings, _ = GuildBankSettings.objects.get_or_create(guild_id=guild_id)
        if target == "bank" and not settings.allow_deposits:
            raise BankActionDisabled("Deposits are disabled on this server.")
        if target == "wallet" and not settings.allow_withdrawals:
            raise BankActionDisabled("Withdrawals are disabled on this server.")
        (account,) = _lock_accounts(account_id)
        if getattr(account, source) < amount:
            raise InsufficientFunds("You don't have that much money!")
        setattr(account, source, getattr(account, source) - amount)
        setattr(account, target, getattr(account, target) + amount)
        account.save(update_fields=["wallet", "bank"])
    return _balance(account)


async def deposit(guild_id: int, user_id: int, user_name: str, amount: int) -> Balance:
    """Move money from the wallet into the bank."""
    _check_amount(amount)
    account = await ensure_account(guild_id, user_id, user_name)
    return await sync_to_async(_move_sync)(
        guild_id, account.pk, "wallet", "bank", amount
    )


async def withdraw(guild_id: int, user_id: int, user_name: str, amount: int) -> Balance:
    """Move money from the bank into the wallet."""
    _check_amount(amount)
    account = await ensure_account(guild_id, user_id, user_name)
    return await sync_to_async(_move_sync)(
        guild_id, account.pk, "bank", "wallet", amount
    )


def _transfer_sync(sender_id: int, receiver_id: int, amount: int) -> Balance:
    with transaction.atomic():
        accounts = {
            account.pk: account for account in _lock_accounts(sender_id, receiver_id)
        }
        sender, receiver = accounts[sender_id], accounts[receiver_id]
        if sender.wallet < amount:
            raise InsufficientFunds("You don't have that much money!")
        sender.wallet -= amount
        receiver.wallet += amount
        sender.save(update_fields=["wallet"])
        receiver.save(update_fields=["wallet"])
    return _balance(sender)


async def transfer(
    guild_id: int,
    sender_id: int,
    sender_name: str,
    receiver_id: int,
    receiver_name: str,
    amount: int,
) -> Balance:
    """Send money from one member's wallet to another's. Returns the sender's balance."""
    _check_amount(amount)
    if sender_id == receiver_id:
        raise InvalidTransfer("You can't send to yourself...")
    sender = await ensure_account(guild_id, sender_id, sender_name)
    receiver = await ensure_account(guild_id, receiver_id, receiver_name)
    return await sync_to_async(_transfer_sync)(sender.pk, receiver.pk, amount)


def _credit_sync(account_id: int, kind: str, amount: int) -> Balance:
    with transaction.atomic():
        (account,) = _lock_accounts(account_id)
        setattr(account, kind, getattr(account, kind) + amount)
        account.save(update_fields=[kind])
    return _balance(account)


async def credit(
    guild_id: int, user_id: int, user_name: str, amount: int, account: str = "wallet"
) -> Balance:
    """Add money to the member's wallet or bank."""
    _check_amount(amount)
    _check_kind(account)
    target = await ensure_account(guild_id, user_id, user_name)
    return await sync_to_async(_credit_sync)(target.pk, account, amount)


def _debit_sync(account_id: int, kind: str, amount: int, clamp: bool) -> int:
    with transaction.atomic():
        (account,) = _lock_accounts(account_id)
        available = getattr(account, kind)
        if available < amount:
            if not clamp:
                raise InsufficientFunds("You don't have that much money!")
            amount = available
        setattr(account, kind, available - amount)
        account.save(update_fields=[kind])
    return amount


async def debit(
    guild_id: int,
    user_id: int,
    user_name: str,
    amount: int,
    account: str = "wallet",
    clamp: bool = False,
) -> int:
    """Take money from the member's wallet or bank and return how much was taken.

    With ``clamp`` the booking takes at most what is there instead of failing.
    """
    _check_amount(amount)
    _check_kind(account)
    target = await ensure_account(guild_id, user_id, user_name)
    return await sync_to_async(_debit_sync)(target.pk, account, amount, clamp)


def _reset_sync(account_id: int) -> None:
    with transaction.atomic():
        (account,) = _lock_accounts(account_id)
        account.wallet = 0
        account.bank = 0
        account.save(update_fields=["wallet", "bank"])


async def reset(guild_id: int, user_id: int, user_name: str) -> None:
    """Set the member's wallet and bank to zero."""
    account = await ensure_account(guild_id, user_id, user_name)
    await sync_to_async(_reset_sync)(account.pk)
