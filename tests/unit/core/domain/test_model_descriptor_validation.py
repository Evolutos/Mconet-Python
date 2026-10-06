"""Semantic validation tests for open ModelDescriptor implementations."""

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
    Extensions,
    ModelDescriptor,
    NamedModel,
    OpenIdentifier,
    validate_model_descriptor,
)


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


def _empty_extensions() -> Extensions:
    """Create an explicitly typed empty mapping for test descriptor defaults."""
    return {}


@dataclass(frozen=True, slots=True)
class _CustomDescriptor:
    """Custom structural descriptor used to exercise runtime field validation."""

    name: str
    display_name: str | None = None
    family: OpenIdentifier | None = None
    version: str | None = None
    description: str | None = None
    metadata: Extensions = field(default_factory=_empty_extensions)
    extensions: Extensions = field(default_factory=_empty_extensions)


def test_model_descriptor_validator_returns_original_custom_implementation() -> None:
    """Verify valid open implementations preserve identity and unknown fields."""
    descriptor = _CustomDescriptor(
        name="provider/model",
        family=OpenIdentifier("vendor.future_family"),
        metadata={"contextWindow": 128_000},
        extensions={"futureField": {"enabled": True}},
    )

    assert validate_model_descriptor(descriptor) is descriptor


def test_model_descriptor_validator_rejects_missing_or_blank_name() -> None:
    """Verify the required model name exists and contains visible content."""

    @dataclass(frozen=True, slots=True)
    class _MissingName:
        """Intentionally omit the required name property."""

        display_name: str | None = None
        family: OpenIdentifier | None = None
        version: str | None = None
        description: str | None = None
        metadata: Extensions = field(default_factory=_empty_extensions)
        extensions: Extensions = field(default_factory=_empty_extensions)

    _assert_raises(
        TypeError,
        lambda: validate_model_descriptor(cast(ModelDescriptor, _MissingName())),
        "must implement ModelDescriptor",
    )
    for name in ("", "   "):
        _assert_raises(
            ValueError,
            lambda name=name: validate_model_descriptor(NamedModel(name)),
            "must not be empty or whitespace",
        )


def test_model_descriptor_validator_rejects_invalid_family() -> None:
    """Verify optional family values satisfy the portable open grammar."""
    _assert_raises(
        ValueError,
        lambda: validate_model_descriptor(
            NamedModel("model", family=OpenIdentifier("Invalid Family"))
        ),
        "OpenIdentifier",
    )


def test_model_descriptor_validator_rejects_invalid_metadata() -> None:
    """Verify metadata keys, structure, and numeric ranges are enforced."""
    invalid_values: tuple[tuple[Extensions, type[BaseException], str], ...] = (
        (cast(Extensions, {1: "value"}), TypeError, "metadata keys"),
        (cast(Extensions, {"tuple": (1, 2)}), TypeError, "structurally valid"),
        ({"overflow": 2**53}, ValueError, "safe range"),
        ({"notFinite": math.inf}, ValueError, "must be finite"),
    )

    for metadata, exception_type, message in invalid_values:
        _assert_raises(
            exception_type,
            lambda metadata=metadata: validate_model_descriptor(
                _CustomDescriptor("model", metadata=metadata, extensions={})
            ),
            message,
        )


def test_model_descriptor_validator_checks_extensions_independently() -> None:
    """Verify unknown extension data follows the same portable JSON policy."""
    _assert_raises(
        ValueError,
        lambda: validate_model_descriptor(
            _CustomDescriptor(
                "model",
                metadata={},
                extensions={"future": math.nan},
            )
        ),
        "must be finite",
    )
