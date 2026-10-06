"""Pre-I/O semantic validation tests for open ModelTarget implementations."""

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
    Extensions,
    ModelDescriptor,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    validate_model_target,
)


def _empty_extensions() -> Extensions:
    """Create a typed empty extension mapping for test target defaults."""
    return {}


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Target:
    """Custom structural target used to exercise runtime validation."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


def test_model_target_validator_returns_original_custom_target() -> None:
    """Verify a valid open target preserves identity and separated dimensions."""
    target = _Target(
        service_id=OpenIdentifier("service.vendor"),
        protocol_id=OpenIdentifier("protocol.compatible"),
        model=NamedModel("opaque-model"),
        deployment_id="deployment-a",
        extensions={"futureRouting": {"region": "east"}},
    )

    assert validate_model_target(target) is target


def test_model_target_validator_rejects_incomplete_surface_or_missing_model() -> None:
    """Verify absent and null model states fail before downstream side effects."""

    @dataclass(frozen=True, slots=True)
    class _MissingModel:
        """Intentionally omit the required model property."""

        service_id: OpenIdentifier
        protocol_id: OpenIdentifier
        deployment_id: str | None = None
        extensions: Extensions = field(default_factory=_empty_extensions)

    _assert_raises(
        TypeError,
        lambda: validate_model_target(
            cast(
                ModelTarget,
                _MissingModel(
                    OpenIdentifier("service.vendor"),
                    OpenIdentifier("protocol.compatible"),
                ),
            )
        ),
        "must implement ModelTarget",
    )
    _assert_raises(
        TypeError,
        lambda: validate_model_target(
            _Target(
                OpenIdentifier("service.vendor"),
                OpenIdentifier("protocol.compatible"),
                cast(ModelDescriptor, None),
            )
        ),
        "model must implement ModelDescriptor",
    )


def test_model_target_validator_rejects_invalid_open_identifiers() -> None:
    """Verify service and protocol syntax fail independently."""
    for service_id, protocol_id in (
        ("Invalid Service", "protocol.valid"),
        ("service.valid", "Invalid Protocol"),
    ):
        _assert_raises(
            ValueError,
            lambda service_id=service_id, protocol_id=protocol_id: (
                validate_model_target(
                    _Target(
                        OpenIdentifier(service_id),
                        OpenIdentifier(protocol_id),
                        NamedModel("model"),
                    )
                )
            ),
            "OpenIdentifier",
        )


def test_model_target_validator_delegates_model_validation() -> None:
    """Verify an invalid descriptor fails through the shared model validator."""
    _assert_raises(
        ValueError,
        lambda: validate_model_target(
            _Target(
                OpenIdentifier("service.vendor"),
                OpenIdentifier("protocol.compatible"),
                NamedModel("   "),
            )
        ),
        "name must not be empty or whitespace",
    )


def test_model_target_validator_checks_deployment_and_extensions() -> None:
    """Verify opaque deployment type and portable extension data are enforced."""
    _assert_raises(
        TypeError,
        lambda: validate_model_target(
            _Target(
                OpenIdentifier("service.vendor"),
                OpenIdentifier("protocol.compatible"),
                NamedModel("model"),
                deployment_id=cast(str, 1),
            )
        ),
        "deployment_id must be a string or None",
    )
    _assert_raises(
        ValueError,
        lambda: validate_model_target(
            _Target(
                OpenIdentifier("service.vendor"),
                OpenIdentifier("protocol.compatible"),
                NamedModel("model"),
                extensions={"future": math.inf},
            )
        ),
        "must be finite",
    )
