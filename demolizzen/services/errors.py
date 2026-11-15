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
