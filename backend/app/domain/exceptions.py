"""Domain-level exceptions.

These carry no knowledge of HTTP — they express failures in terms the
business understands (a user wasn't found, credentials were wrong, a rule
was violated). The interface layer's exception handlers (see
``app.interface.api.errors``) translate each of these into an HTTP response.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for every exception raised by domain or application code."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EntityNotFoundError(DomainError):
    """A requested entity does not exist."""

    def __init__(self, entity: str, identifier: object) -> None:
        self.entity = entity
        self.identifier = identifier
        super().__init__(f"{entity} not found: {identifier}")


class EntityAlreadyExistsError(DomainError):
    """A uniqueness constraint owned by the domain was violated."""

    def __init__(self, entity: str, field: str, value: object) -> None:
        self.entity = entity
        self.field = field
        self.value = value
        super().__init__(f"{entity} with {field}={value!r} already exists")


class ValidationError(DomainError):
    """A value violates a domain invariant (e.g. weak password, bad email)."""


class InvalidCredentialsError(DomainError):
    """Login failed — wrong email/password combination."""

    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class InactiveUserError(DomainError):
    """The user account exists but is deactivated."""

    def __init__(self) -> None:
        super().__init__("User account is inactive")


class InvalidTokenError(DomainError):
    """A JWT or refresh token is malformed, expired, or has a bad signature."""

    def __init__(self, reason: str = "Invalid or expired token") -> None:
        super().__init__(reason)


class TokenRevokedError(DomainError):
    """A refresh token was already used or explicitly revoked (reuse detected)."""

    def __init__(self) -> None:
        super().__init__("Token has been revoked")


class PermissionDeniedError(DomainError):
    """The authenticated principal lacks a required permission."""

    def __init__(self, permission: str) -> None:
        self.permission = permission
        super().__init__(f"Missing required permission: {permission}")
