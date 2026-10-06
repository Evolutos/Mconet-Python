"""Type-boundary tests for SafeConfigurationSnapshot."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from inspect import Parameter, signature
from typing import cast, get_type_hints

import mconet.core.domain
import mconet.core.runtime
from mconet.core.domain import (
    Authorization,
    CancellationSignal,
    ModelTarget,
    SecretValue,
    ServiceAccess,
)
from mconet.core.runtime.safe_configuration_snapshot import (
    SafeConfigurationSnapshot,
)

_EXPECTED_FIELDS = (
    "service_id",
    "protocol_id",
    "model_name",
    "deployment_id",
    "service_access_configured",
    "compatibility_policy",
    "max_response_body_bytes",
    "max_streaming_error_body_bytes",
    "max_frame_bytes",
    "cancellation_configured",
)
_FORBIDDEN_TYPE_NAMES = (
    Authorization.__name__,
    CancellationSignal.__name__,
    ModelTarget.__name__,
    SecretValue.__name__,
    ServiceAccess.__name__,
)


def _snapshot_with(
    *,
    service_id: str = "service.vendor",
    protocol_id: str = "protocol.vendor",
    model_name: str = "model-a",
    deployment_id: str | None = "deployment-a",
    service_access_configured: bool = True,
    compatibility_policy: str = "compatible",
    max_response_body_bytes: int = 100,
    max_streaming_error_body_bytes: int = 200,
    max_frame_bytes: int = 300,
    cancellation_configured: bool = False,
) -> SafeConfigurationSnapshot:
    """Create a snapshot while allowing one typed field override per test."""
    # Distinct limits make transposition visible while ordinary strings avoid
    # relying on unresolved domain objects or sensitive access representation.
    return SafeConfigurationSnapshot(
        service_id=service_id,
        protocol_id=protocol_id,
        model_name=model_name,
        deployment_id=deployment_id,
        service_access_configured=service_access_configured,
        compatibility_policy=compatibility_policy,
        max_response_body_bytes=max_response_body_bytes,
        max_streaming_error_body_bytes=max_streaming_error_body_bytes,
        max_frame_bytes=max_frame_bytes,
        cancellation_configured=cancellation_configured,
    )


def _snapshot() -> SafeConfigurationSnapshot:
    """Create one complete safe snapshot with the standard distinct values."""
    # Keep the common valid path concise while all field defaults remain visible
    # in the typed factory used by negative tests.
    return _snapshot_with()


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Matching the exact field diagnostic prevents a different invalid argument
    # from making a negative storage-boundary test pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_safe_configuration_snapshot_requires_every_field() -> None:
    """Verify the closed constructor has no omitted or implicitly defaulted facts."""
    parameters = signature(SafeConfigurationSnapshot).parameters

    # Presence booleans and optional-valued deployment are still explicit fields;
    # a mapper cannot silently omit a security-relevant configuration dimension.
    assert tuple(parameters) == _EXPECTED_FIELDS
    for field_name in _EXPECTED_FIELDS:
        assert parameters[field_name].default is Parameter.empty


def test_safe_configuration_snapshot_stores_complete_scalar_values() -> None:
    """Verify every non-sensitive scalar remains exact and independently visible."""
    snapshot = _snapshot()

    # The snapshot is already mapped data: construction performs no identifier
    # normalization, defaulting, value inference, or access-object traversal.
    assert snapshot.service_id == "service.vendor"
    assert snapshot.protocol_id == "protocol.vendor"
    assert snapshot.model_name == "model-a"
    assert snapshot.deployment_id == "deployment-a"
    assert snapshot.service_access_configured is True
    assert snapshot.compatibility_policy == "compatible"
    assert snapshot.max_response_body_bytes == 100
    assert snapshot.max_streaming_error_body_bytes == 200
    assert snapshot.max_frame_bytes == 300
    assert snapshot.cancellation_configured is False


def test_safe_configuration_snapshot_allows_explicit_deployment_absence() -> None:
    """Verify deployment absence remains an explicit safe scalar state."""
    snapshot = SafeConfigurationSnapshot(
        service_id="service.vendor",
        protocol_id="protocol.vendor",
        model_name="model-a",
        deployment_id=None,
        service_access_configured=False,
        compatibility_policy="strict",
        max_response_body_bytes=100,
        max_streaming_error_body_bytes=200,
        max_frame_bytes=300,
        cancellation_configured=True,
    )

    # None conveys only absent deployment; access and cancellation use separate
    # booleans so one nullable field never carries multiple meanings.
    assert snapshot.deployment_id is None
    assert snapshot.service_access_configured is False
    assert snapshot.cancellation_configured is True


def test_safe_configuration_snapshot_has_no_sensitive_payload_fields() -> None:
    """Verify the exact shape excludes broad containers and sensitive contracts."""
    snapshot_fields = tuple(field.name for field in fields(SafeConfigurationSnapshot))
    type_hints = get_type_hints(SafeConfigurationSnapshot)
    annotation_text = " ".join(str(annotation) for annotation in type_hints.values())

    # An exact flat shape prevents future Authorization, headers, query, metadata,
    # extensions, credential material, cancellation reason, or generic payload
    # containers from entering snapshots without an explicit contract change.
    assert snapshot_fields == _EXPECTED_FIELDS
    assert type_hints == {
        "service_id": str,
        "protocol_id": str,
        "model_name": str,
        "deployment_id": str | None,
        "service_access_configured": bool,
        "compatibility_policy": str,
        "max_response_body_bytes": int,
        "max_streaming_error_body_bytes": int,
        "max_frame_bytes": int,
        "cancellation_configured": bool,
    }
    for forbidden_name in _FORBIDDEN_TYPE_NAMES:
        assert forbidden_name not in annotation_text
    assert not hasattr(_snapshot(), "__dict__")


def test_safe_configuration_snapshot_representation_contains_only_safe_facts() -> None:
    """Verify ordinary representation cannot traverse unresolved domain objects."""
    snapshot = _snapshot()
    representation = repr(snapshot)

    # Dataclass repr is safe because every field is an exact built-in scalar and
    # no arbitrary object can execute custom repr logic or reveal authorization.
    assert "service.vendor" in representation
    assert "model-a" in representation
    for forbidden_name in _FORBIDDEN_TYPE_NAMES:
        assert forbidden_name not in representation


def test_safe_configuration_snapshot_defers_numeric_semantics() -> None:
    """Verify storage does not duplicate the preceding resolved validator's work."""
    snapshot = SafeConfigurationSnapshot(
        service_id="",
        protocol_id="",
        model_name="",
        deployment_id=None,
        service_access_configured=False,
        compatibility_policy="",
        max_response_body_bytes=0,
        max_streaming_error_body_bytes=-1,
        max_frame_bytes=1 << 63,
        cancellation_configured=False,
    )

    # The later mapper is required to run only after semantic validation. This
    # carrier enforces safe primitive storage without becoming a second Validator.
    assert snapshot.max_response_body_bytes == 0
    assert snapshot.max_streaming_error_body_bytes == -1
    assert snapshot.max_frame_bytes == 1 << 63


def test_safe_configuration_snapshot_is_immutable_and_internal() -> None:
    """Verify mapped facts cannot be replaced and do not expand public APIs."""
    snapshot = _snapshot()

    # Frozen slot storage makes one snapshot stable for concurrent observers;
    # absence from package exports keeps this monitoring boundary internal.
    _assert_raises(
        FrozenInstanceError,
        lambda: snapshot.__setattr__("model_name", "replacement"),
        "cannot assign to field",
    )
    assert "SafeConfigurationSnapshot" not in mconet.core.runtime.__all__
    assert "SafeConfigurationSnapshot" not in mconet.core.domain.__all__


def test_safe_configuration_snapshot_rejects_non_string_fields() -> None:
    """Verify required and optional text fields require exact built-in strings."""

    class _UnsafeString(str):
        """Represent a string subclass that must not cross the safe boundary."""

    invalid_calls = (
        (
            lambda: _snapshot_with(service_id=cast(str, object())),
            "service_id must be a string",
        ),
        (
            lambda: _snapshot_with(
                protocol_id=cast(str, _UnsafeString("protocol.vendor"))
            ),
            "protocol_id must be a string",
        ),
        (
            lambda: _snapshot_with(model_name=cast(str, object())),
            "model_name must be a string",
        ),
        (
            lambda: _snapshot_with(compatibility_policy=cast(str, object())),
            "compatibility_policy must be a string",
        ),
        (
            lambda: _snapshot_with(deployment_id=cast(str | None, object())),
            "deployment_id must be a string or None",
        ),
    )

    # Each typed factory call changes exactly one field so diagnostics prove the
    # intended boundary rejected it without weakening static argument checking.
    for create_snapshot, message in invalid_calls:
        _assert_raises(TypeError, create_snapshot, message)


def test_safe_configuration_snapshot_rejects_non_boolean_presence_flags() -> None:
    """Verify presence facts cannot be represented by numeric or arbitrary values."""
    invalid_calls = (
        (
            lambda: SafeConfigurationSnapshot(
                "service.vendor",
                "protocol.vendor",
                "model-a",
                None,
                cast(bool, 1),
                "compatible",
                100,
                200,
                300,
                False,
            ),
            "service_access_configured must be a boolean",
        ),
        (
            lambda: SafeConfigurationSnapshot(
                "service.vendor",
                "protocol.vendor",
                "model-a",
                None,
                False,
                "compatible",
                100,
                200,
                300,
                cast(bool, 0),
            ),
            "cancellation_configured must be a boolean",
        ),
    )

    # Python treats bool as an int subclass; exact checks preserve JSON boolean
    # semantics and prevent 0/1 from becoming ambiguous presence flags.
    for create_snapshot, message in invalid_calls:
        _assert_raises(TypeError, create_snapshot, message)


def test_safe_configuration_snapshot_rejects_non_integer_limits() -> None:
    """Verify each resolved limit requires exact finite integer storage."""
    invalid_calls = (
        (
            lambda: SafeConfigurationSnapshot(
                "service.vendor",
                "protocol.vendor",
                "model-a",
                None,
                False,
                "compatible",
                cast(int, True),
                200,
                300,
                False,
            ),
            "max_response_body_bytes must be an integer",
        ),
        (
            lambda: SafeConfigurationSnapshot(
                "service.vendor",
                "protocol.vendor",
                "model-a",
                None,
                False,
                "compatible",
                100,
                cast(int, 2.5),
                300,
                False,
            ),
            "max_streaming_error_body_bytes must be an integer",
        ),
        (
            lambda: SafeConfigurationSnapshot(
                "service.vendor",
                "protocol.vendor",
                "model-a",
                None,
                False,
                "compatible",
                100,
                200,
                cast(int, object()),
                False,
            ),
            "max_frame_bytes must be an integer",
        ),
    )

    # Each limit fails independently, including bool and float values that could
    # otherwise look numeric but violate the cross-language integer contract.
    for create_snapshot, message in invalid_calls:
        _assert_raises(TypeError, create_snapshot, message)
