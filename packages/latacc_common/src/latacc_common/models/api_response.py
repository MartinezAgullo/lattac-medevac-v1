"""Standardized API response wrapper for all CMOP interactions."""

from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorAction(StrEnum):
    """Signal to the LLM about how to handle an error."""

    RETRY = "retry"      # Transient error (503, timeout) — try again
    CORRECT = "correct"  # Logic error (400, bad params) — fix arguments
    INFORM = "inform"    # Domain error (entity evacuated) — incorporate info


class ApiResponse(BaseModel, Generic[T]):
    """
    Standardized response wrapper returned by all tools.

    The LLM receives this as JSON and uses `action` to decide
    whether to retry, correct its call, or incorporate the info.
    """

    success: bool
    data: T | None = None
    error: str | None = None
    message: str | None = None
    action: ErrorAction | None = None
    retry_after_seconds: int | None = None