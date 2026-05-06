"""Global application exceptions hierarchy.

Provides a structured exception hierarchy for the application
with consistent error messages and optional error codes.
"""

from __future__ import annotations


class BaseAppException(Exception):  # noqa: N818
    """Base exception for all application errors.

    Args:
        message: Human-readable error description
        code: Optional machine-readable error code
    """

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code

    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


class NotFoundError(BaseAppException):
    """Resource not found exception."""

    def __init__(self, message: str = "Resource not found", code: str | None = "NOT_FOUND") -> None:
        super().__init__(message, code)


class ValidationError(BaseAppException):
    """Input validation exception."""

    def __init__(
        self, message: str = "Validation failed", code: str | None = "VALIDATION_ERROR"
    ) -> None:
        super().__init__(message, code)


class UnauthorizedError(BaseAppException):
    """Authentication/authorization exception."""

    def __init__(self, message: str = "Unauthorized", code: str | None = "UNAUTHORIZED") -> None:
        super().__init__(message, code)


class StorageError(BaseAppException):
    """Storage operation exception (Supabase, S3, etc)."""

    def __init__(
        self, message: str = "Storage operation failed", code: str | None = "STORAGE_ERROR"
    ) -> None:
        super().__init__(message, code)


class ProcessingError(BaseAppException):
    """Document/text processing exception."""

    def __init__(
        self, message: str = "Processing failed", code: str | None = "PROCESSING_ERROR"
    ) -> None:
        super().__init__(message, code)
