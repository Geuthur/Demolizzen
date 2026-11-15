"""The shop: buying items and using them."""

# Standard Library
from dataclasses import dataclass

# Third Party
from asgiref.sync import sync_to_async

# Django
from django.db import transaction

# Demolizzen
from demolizzen.models import EconomyShop, UserBag, UserBagItems
from demolizzen.services import bank
from demolizzen.services.errors import (
    InsufficientFunds,
    InvalidQuantity,
    ItemNotFound,
    ItemNotOwned,
    NotEnoughItems,
)

# Largest number of items one purchase or use may cover.
MAX_QUANTITY = 1000


@dataclass(frozen=True)
class BagItem:
    name: str
    quantity: int


@dataclass(frozen=True)
class Purchase:
    """What a purchase bought and what the member owns afterwards."""

    item_name: str
    quantity: int
    total_price: int
    owned: int


@dataclass(frozen=True)
class ItemUse:
    """The item that was used and how many are left."""

    item_name: str
    item_type: str
    remaining: int


def _check_quantity(quantity) -> None:
    if (
        isinstance(quantity, bool)
        or not isinstance(quantity, int)
        or not 1 <= quantity <= MAX_QUANTITY
    ):
        raise InvalidQuantity(f"The number must be between 1 and {MAX_QUANTITY}.")


def _buy_sync(account_id: int, profile_id: int, item_name: str, quantity: int):
    # Paying and receiving are one transaction: either both happen or neither.
    with transaction.atomic():
        item = (
            EconomyShop.objects.filter(name__iexact=item_name, active=True)
            .order_by("pk")
            .first()
        )
        if item is None or item.price < 0:
            raise ItemNotFound(f"The Item `{item_name}` was not found!")
        total = item.price * quantity
        (account,) = bank._lock_accounts(account_id)
        if account.wallet < total:
            raise InsufficientFunds("You don't have that much money!")
        account.wallet -= total
        account.save(update_fields=["wallet"])

        bag, _ = UserBag.objects.get_or_create(user_id=profile_id)
        entry, _ = UserBagItems.objects.select_for_update().get_or_create(
            user_bag=bag,
            item_name=item.name,
            defaults={"item_type": item.shop_type, "quantity": 0},
        )
        entry.quantity += quantity
        entry.save(update_fields=["quantity"])
    return Purchase(item.name, quantity, total, entry.quantity)


async def buy(
    guild_id: int, user_id: int, user_name: str, item_name: str, quantity: int
) -> Purchase:
    """Buy ``quantity`` of a shop item with money from the wallet."""
    _check_quantity(quantity)
    account = await bank.ensure_account(guild_id, user_id, user_name)
    return await sync_to_async(_buy_sync)(
        account.pk, account.user_id, item_name, quantity
    )


def _use_sync(profile_id: int, item_name: str, quantity: int) -> ItemUse:
    with transaction.atomic():
        entry = (
            UserBagItems.objects.select_for_update()
            .filter(user_bag__user_id=profile_id, item_name__iexact=item_name)
            .order_by("pk")
            .first()
        )
        if entry is None or entry.quantity <= 0:
            raise ItemNotOwned(f"You don't have `{item_name}` in your bag")
        if entry.quantity < quantity:
            raise NotEnoughItems(
                f"You don't have enough `{entry.item_name}` in your bag"
            )
        entry.quantity -= quantity
        entry.save(update_fields=["quantity"])
    return ItemUse(entry.item_name, entry.item_type, entry.quantity)


async def use_item(
    guild_id: int, user_id: int, user_name: str, item_name: str, quantity: int
) -> ItemUse:
    """Use up ``quantity`` of an item from the member's bag."""
    _check_quantity(quantity)
    account = await bank.ensure_account(guild_id, user_id, user_name)
    return await sync_to_async(_use_sync)(account.user_id, item_name, quantity)


async def get_bag(guild_id: int, user_id: int) -> list[BagItem]:
    """The items a member owns, sorted by name. Used-up items are left out."""
    return [
        BagItem(name=item.item_name, quantity=item.quantity)
        async for item in UserBagItems.objects.filter(
            user_bag__user__guild_id=guild_id,
            user_bag__user__user_id=user_id,
            quantity__gt=0,
        ).order_by("item_name", "pk")
    ]
