"""Closed immutable shape for non-sensitive resolved configuration snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True, slots=True)
class SafeConfigurationSnapshot:
    """Store only explicit non-sensitive scalar configuration facts.

    The closed field set intentionally contains no ModelTarget, ServiceAccess,
    Authorization, SecretValue, CancellationSignal, header/query collection,
    arbitrary metadata, extension map, or credential-derived value. A later
    mapper constructs this type from validated resolved configuration without
    copying authorization payloads or cancellation reasons.

    All members use exact built-in immutable scalar types that are JSON value
    leaves. This prevents custom objects, mutable JSON containers, and objects
    with unsafe representation or serialization behavior from entering a
    snapshot through structural compatibility.
    """

    service_id: str
    """The validated model service identifier text."""

    protocol_id: str
    """The validated interaction protocol identifier text."""

    model_name: str
    """The validated selected model name."""

    deployment_id: str | None
    """The optional non-sensitive deployment identifier."""

    service_access_configured: bool
    """Whether an unresolved service access input was selected."""

    compatibility_policy: str
    """The exact validated compatibility policy identifier text."""

    max_response_body_bytes: int
    """The resolved unary response body byte limit."""

    max_streaming_error_body_bytes: int
    """The resolved initial streaming error body byte limit."""

    max_frame_bytes: int
    """The resolved encoded streaming frame byte limit."""

    cancellation_configured: bool
    """Whether this interaction owns a cancellation signal reference."""

    def __post_init__(self) -> None:
        """Require the closed snapshot fields to use exact safe scalar storage."""
        # Exact string checks reject arbitrary objects and str subclasses whose
        # repr/serialization behavior could expose data during monitoring.
        for field_name, value in (
            ("service_id", cast(object, self.service_id)),
            ("protocol_id", cast(object, self.protocol_id)),
            ("model_name", cast(object, self.model_name)),
            ("compatibility_policy", cast(object, self.compatibility_policy)),
        ):
            if type(value) is not str:
                raise TypeError(
                    f"SafeConfigurationSnapshot {field_name} must be a string."
                )

        deployment_id = cast(object, self.deployment_id)
        # Deployment absence is the only optional scalar state. A present value
        # follows the same exact-string boundary as the required identifiers.
        if deployment_id is not None and type(deployment_id) is not str:
            raise TypeError(
                "SafeConfigurationSnapshot deployment_id must be a string or None."
            )

        # Exact bool checks keep presence flags distinct from integers, which are
        # subclasses in Python and could otherwise serialize as numeric 0/1.
        for field_name, value in (
            (
                "service_access_configured",
                cast(object, self.service_access_configured),
            ),
            (
                "cancellation_configured",
                cast(object, self.cancellation_configured),
            ),
        ):
            if type(value) is not bool:
                raise TypeError(
                    f"SafeConfigurationSnapshot {field_name} must be a boolean."
                )

        # The snapshot enforces finite integer storage but deliberately leaves
        # positivity and signed-range semantics to the resolved-config validator
        # that runs before the later snapshot mapper.
        for field_name, value in (
            (
                "max_response_body_bytes",
                cast(object, self.max_response_body_bytes),
            ),
            (
                "max_streaming_error_body_bytes",
                cast(object, self.max_streaming_error_body_bytes),
            ),
            ("max_frame_bytes", cast(object, self.max_frame_bytes)),
        ):
            if type(value) is not int:
                raise TypeError(
                    f"SafeConfigurationSnapshot {field_name} must be an integer."
                )
