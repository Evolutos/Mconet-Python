"""Factual recovery metadata for normalized interaction failures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.duration import Duration, validate_duration


@dataclass(frozen=True, slots=True)
class RecoveryHint:
    """Describe retry and request-processing facts without performing recovery.

    ``transient`` reports whether retry can be meaningful. ``retry_after`` is an
    optional non-negative portable duration. Processing state is tri-valued:
    ``True`` means the request may have been processed, ``False`` means it was
    not processed, and ``None`` means the state is unknown.
    """

    transient: bool
    """Whether the failure condition can be temporary."""

    retry_after: Duration | None = None
    """The minimum suggested delay before retrying, when supplied."""

    request_may_have_been_processed: bool | None = None
    """Whether processing may have occurred, or ``None`` when unknown."""

    def __post_init__(self) -> None:
        """Require exact booleans and a coherent portable retry delay."""
        transient = cast(object, self.transient)
        retry_after = cast(object, self.retry_after)
        processed = cast(object, self.request_may_have_been_processed)

        if type(transient) is not bool:
            raise TypeError("RecoveryHint transient must be a boolean.")
        if retry_after is not None and not isinstance(retry_after, Duration):
            raise TypeError("RecoveryHint retry_after must be a Duration or None.")
        if processed is not None and type(processed) is not bool:
            raise TypeError(
                "RecoveryHint request_may_have_been_processed must be a boolean "
                "or None."
            )
        if retry_after is None:
            return
        if retry_after.total_nanoseconds < 0:
            raise ValueError("RecoveryHint retry_after must not be negative.")
        validate_duration(retry_after.total_nanoseconds)
        if not transient:
            raise ValueError("RecoveryHint retry_after requires a transient failure.")
