"""Errors raised by the service layer."""


class ServiceError(Exception):
    """Base class for all service layer errors."""


class GuildNotRegistered(ServiceError):
    """The guild has no profile in the database."""

    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        super().__init__(f"Guild {guild_id} is not registered.")


class UnknownCog(ServiceError):
    """The cog key is not part of the registry."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(f"Unknown cog '{key}'.")


class CogNotToggleable(ServiceError):
    """The cog is always active and cannot be switched per guild."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(f"Cog '{key}' cannot be enabled or disabled.")


class DependencyConflict(ServiceError):
    """Switching the cog needs other cogs to be switched with it.

    ``affected`` lists the cogs that depend on ``key`` and are still active
    (when disabling), or the cogs ``key`` requires that are off (when enabling).
    """

    def __init__(self, key: str, enabled: bool, affected: list[str]):
        self.key = key
        self.enabled = enabled
        self.affected = affected
        action = "enabled" if enabled else "disabled"
        super().__init__(
            f"Cog '{key}' cannot be {action} on its own; affected: {', '.join(affected)}."
        )


class TicketError(ServiceError):
    """Base class of ticket errors. ``message`` is meant to be shown to the user."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class TicketNotFound(TicketError):
    """There is no ticket for the channel."""


class TicketPermissionDenied(TicketError):
    """The actor may not perform the action on the ticket."""


class TicketStateError(TicketError):
    """The action does not fit the ticket's current state."""


class TicketLimitReached(TicketError):
    """The member already has the maximum number of open tickets."""


class TicketNotConfigured(TicketError):
    """The guild has not finished setting up the ticket system."""


class InvalidTicketSetting(TicketError):
    """A ticket setting was given an unknown name or an invalid value."""


class BankError(ServiceError):
    """Base class of bank errors. ``message`` is meant to be shown to the user."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class InvalidAmount(BankError):
    """The amount is not a whole number within the allowed range."""


class InsufficientFunds(BankError):
    """The account does not hold enough money for the booking."""


class BankActionDisabled(BankError):
    """The guild has switched deposits or withdrawals off."""


class InvalidTransfer(BankError):
    """Money cannot be sent this way, for example to oneself."""


class InvalidBankSetting(BankError):
    """A bank setting was given an unknown name or an invalid value."""


class ShopError(ServiceError):
    """Base class of shop errors. ``message`` is meant to be shown to the user."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ItemNotFound(ShopError):
    """The shop does not sell the item."""


class InvalidQuantity(ShopError):
    """The quantity is not a whole number within the allowed range."""


class ItemNotOwned(ShopError):
    """The member has none of the item."""


class NotEnoughItems(ShopError):
    """The member has fewer of the item than they want to use."""


class MissionError(ServiceError):
    """Base class of daily, work and mission errors. ``message`` is for the user."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class OnCooldown(MissionError):
    """The action is not available yet. ``remaining`` says for how long."""

    def __init__(self, remaining):
        self.remaining = remaining
        super().__init__("This is not available yet.")


class NoShip(MissionError):
    """The member has no ship for this kind of mission."""


class NoActiveMission(MissionError):
    """There is no active mission to act on."""


class AlreadySettled(MissionError):
    """The mission was reported already; it is paid out only once."""


class ShipNotFound(MissionError):
    """No such ship is for sale in this category."""


class ShipAlreadyOwned(MissionError):
    """The member already flies this ship."""


class PriceError(ServiceError):
    """Base class of price lookup errors. ``message`` is meant to be shown to the user."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class PriceNotFound(PriceError):
    """The trade hub has no price for the item."""

    def __init__(self, item_name: str, tradehub: str):
        super().__init__(f"No market price found for **{item_name}** in {tradehub}.")


class PriceUnavailable(PriceError):
    """The price service could not be asked."""

    def __init__(self, tradehub: str):
        super().__init__(
            f"The price service did not answer for {tradehub}. Please try again later."
        )
