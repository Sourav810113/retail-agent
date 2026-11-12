"""Errors raised by services and mapped to HTTP by api/errors.py (AD-8)."""

from .enums import DenialReason


class DomainError(Exception):
    """Base class. ``message`` is safe to return to clients."""

    default_message = "Domain error"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class NotFoundError(DomainError):
    default_message = "Not found"


class ReturnDeniedError(DomainError):
    default_message = "Return request denied"

    def __init__(self, reason: DenialReason, message: str | None = None) -> None:
        self.reason = reason
        super().__init__(message)


class ServiceUnavailableError(DomainError):
    default_message = "Service unhealthy"
