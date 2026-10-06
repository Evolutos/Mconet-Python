"""Normalized failures raised by model interaction operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.recovery_hint import RecoveryHint


@dataclass(frozen=True, slots=True)
class ModelInteractionError(Exception):
    """Carry stable normalized error fields as a Python exception.

    Service-specific error codes remain separate from the SDK-owned ``code``.
    ``cause`` retains an allowed underlying exception and is also connected to
    Python's explicit exception chain for normal traceback behavior.
    """

    category: ErrorCategory
    """Normalized high-level error category."""

    phase: InteractionPhase
    """Interaction phase in which the failure became final."""

    code: str
    """Stable SDK-owned error code."""

    message: str
    """Human-readable non-secret failure summary."""

    status_code: int | None = None
    """Optional native numeric service or transport status."""

    service_error_code: str | None = None
    """Optional service-owned error code, separate from ``code``."""

    request_id: str | None = None
    """Optional service request identifier for diagnostics."""

    recovery: RecoveryHint | None = None
    """Optional factual recovery metadata; it does not execute a retry."""

    cause: BaseException | None = None
    """Optional underlying exception retained for permitted diagnostics."""

    def __post_init__(self) -> None:
        """Validate every field and initialize standard exception behavior."""
        category = cast(object, self.category)
        phase = cast(object, self.phase)
        code = cast(object, self.code)
        message = cast(object, self.message)
        status_code = cast(object, self.status_code)
        service_error_code = cast(object, self.service_error_code)
        request_id = cast(object, self.request_id)
        recovery = cast(object, self.recovery)
        cause = cast(object, self.cause)

        # Required domain values and text fields are checked first so exception
        # construction cannot hide an invalid normalized error contract.
        if not isinstance(category, ErrorCategory):
            raise TypeError("ModelInteractionError category must be an ErrorCategory.")
        if not isinstance(phase, InteractionPhase):
            raise TypeError("ModelInteractionError phase must be an InteractionPhase.")
        if not isinstance(code, str):
            raise TypeError("ModelInteractionError code must be a string.")
        if not isinstance(message, str):
            raise TypeError("ModelInteractionError message must be a string.")
        # bool is an int subclass, so status_code requires an exact integer when
        # present; all other optional metadata preserves its declared type.
        if status_code is not None and type(status_code) is not int:
            raise TypeError(
                "ModelInteractionError status_code must be an integer or None."
            )
        if service_error_code is not None and not isinstance(service_error_code, str):
            raise TypeError(
                "ModelInteractionError service_error_code must be a string or None."
            )
        if request_id is not None and not isinstance(request_id, str):
            raise TypeError(
                "ModelInteractionError request_id must be a string or None."
            )
        if recovery is not None and not isinstance(recovery, RecoveryHint):
            raise TypeError(
                "ModelInteractionError recovery must be a RecoveryHint or None."
            )
        if cause is not None and not isinstance(cause, BaseException):
            raise TypeError(
                "ModelInteractionError cause must be a BaseException or None."
            )

        # Initialize BaseException only after validation, then connect the
        # retained cause to Python's explicit traceback chain without mutation.
        Exception.__init__(self, message)
        if cause is not None:
            object.__setattr__(self, "__cause__", cause)
