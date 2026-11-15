"""The bank: accounts and bookings.

Every booking runs in a transaction on locked rows and reads the balances from
the database. Two bookings at the same time therefore cannot create or destroy
money, which they could while balances were changed on objects in memory.
"""

# Standard Library
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

# Third Party
from asgiref.sync import sync_to_async

# Django
from django.db import transaction
from django.db.models import BigIntegerField, ExpressionWrapper, F, Value
from django.db.models.functions import Floor
from django.utils import timezone

# Demolizzen
from demolizzen.models import (
    GuildBankSettings,
    GuildProfile,
    UserBankAccount,
    UserProfile,
)
from demolizzen.services import guilds
from demolizzen.services.errors import (
    BankActionDisabled,
    GuildNotRegistered,
    InsufficientFunds,
    InvalidAmount,
    InvalidBankSetting,
    InvalidTransfer,
)

# Largest amount a single booking may move.
MAX_AMOUNT = 1_000_000_000_000

ACCOUNT_KINDS = ("wallet", "bank")

# Highest interest rate that can be set, and how often interest is paid.
MAX_INTEREST_RATE = 0.10
INTEREST_PERIOD = timedelta(days=7)

# Interest is computed in whole millionths so the database does exact integer maths.
_RATE_SCALE = 1_000_000


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


def _wager_sync(account_id: int, stake: int, won: bool) -> Balance:
    with transaction.atomic():
        (account,) = _lock_accounts(account_id)
        if account.wallet < stake:
            raise InsufficientFunds("You don't have that much money!")
        account.wallet += 2 * stake if won else -stake
        account.save(update_fields=["wallet"])
    return _balance(account)


async def wager(
    guild_id: int, user_id: int, user_name: str, stake: int, won: bool
) -> Balance:
    """Settle a bet: a win adds twice the stake, a loss takes the stake.

    The member must hold the stake either way.
    """
    _check_amount(stake)
    account = await ensure_account(guild_id, user_id, user_name)
    return await sync_to_async(_wager_sync)(account.pk, stake, won)


def _adjust_sync(account_id: int, delta: int) -> int:
    with transaction.atomic():
        (account,) = _lock_accounts(account_id)
        applied = max(delta, -account.wallet)
        account.wallet += applied
        account.save(update_fields=["wallet"])
    return applied


async def adjust(guild_id: int, user_id: int, user_name: str, delta: int) -> int:
    """Change the wallet by ``delta`` and return the change that was booked.

    A negative ``delta`` takes at most what the wallet holds.
    """
    if isinstance(delta, bool) or not isinstance(delta, int) or abs(delta) > MAX_AMOUNT:
        raise InvalidAmount("Amount is too large.")
    account = await ensure_account(guild_id, user_id, user_name)
    if delta == 0:
        return 0
    return await sync_to_async(_adjust_sync)(account.pk, delta)


# ---------------------------------------------------------------------- settings


def _validate_setting(field: str, value) -> None:
    if field == "interest_rate":
        valid = (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and 0 <= value <= MAX_INTEREST_RATE
        )
    elif field in ("allow_deposits", "allow_withdrawals"):
        valid = isinstance(value, bool)
    else:
        raise InvalidBankSetting(f"Unknown bank setting '{field}'.")
    if not valid:
        raise InvalidBankSetting(f"Invalid value for bank setting '{field}'.")


async def get_settings(guild_id: int) -> GuildBankSettings:
    """Return the guild's bank settings, creating the row when it is missing."""
    if not await GuildProfile.objects.filter(guild_id=guild_id).aexists():
        raise GuildNotRegistered(guild_id)
    settings, _ = await GuildBankSettings.objects.aget_or_create(guild_id=guild_id)
    return settings


async def update_settings(guild_id: int, **fields) -> GuildBankSettings:
    """Change bank settings. Nothing is saved unless every value is valid."""
    for field, value in fields.items():
        _validate_setting(field, value)
    settings = await get_settings(guild_id)
    for field, value in fields.items():
        setattr(settings, field, value)
    if fields:
        await settings.asave(update_fields=list(fields))
    return settings


# ---------------------------------------------------------------------- interest


def _is_due(last_update: datetime | None, now: datetime) -> bool:
    return last_update is None or now - last_update >= INTEREST_PERIOD


async def due_guild_ids(
    guild_ids: Iterable[int], now: datetime | None = None
) -> list[int]:
    """The registered guilds out of ``guild_ids`` whose weekly interest is due."""
    now = now or timezone.now()
    wanted = list(guild_ids)
    registered = {
        guild.guild_id
        async for guild in GuildProfile.objects.filter(guild_id__in=wanted)
    }
    last_updates = {
        settings.guild_id: settings.last_interest_update
        async for settings in GuildBankSettings.objects.filter(guild_id__in=wanted)
    }
    return sorted(
        guild_id for guild_id in registered if _is_due(last_updates.get(guild_id), now)
    )


def _pay_interest_sync(guild_id: int, now: datetime) -> int:
    with transaction.atomic():
        if not GuildProfile.objects.filter(guild_id=guild_id).exists():
            raise GuildNotRegistered(guild_id)
        GuildBankSettings.objects.get_or_create(guild_id=guild_id)
        # Lock the settings so two payouts cannot both find the guild due.
        settings = GuildBankSettings.objects.select_for_update().get(guild_id=guild_id)
        if not _is_due(settings.last_interest_update, now):
            return 0

        accounts = UserBankAccount.objects.filter(user__guild_id=guild_id, bank__gt=0)
        paid = accounts.count()
        rate = round(settings.interest_rate * _RATE_SCALE)
        if paid and rate > 0:
            # One UPDATE on the stored balances: a booking that happens at the
            # same time is neither lost nor paid twice.
            interest = ExpressionWrapper(
                Floor(F("bank") * Value(rate) / Value(_RATE_SCALE)),
                output_field=BigIntegerField(),
            )
            accounts.update(bank=F("bank") + interest)
        settings.last_interest_update = now
        settings.save(update_fields=["last_interest_update"])
    return paid


async def pay_interest(guild_id: int, now: datetime | None = None) -> int:
    """Pay the weekly interest of a guild if it is due.

    Returns the number of accounts that hold money in the bank, or 0 when the
    guild is not due yet.
    """
    return await sync_to_async(_pay_interest_sync)(guild_id, now or timezone.now())
