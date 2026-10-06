"""Semantic validation tests for open TaskDescriptor implementations."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
    Extensions,
    JsonValue,
    OpenIdentifier,
    TaskDescriptor,
    validate_task_descriptor,
)


def _empty_extensions() -> Extensions:
    """Create independent mapping storage for descriptor test defaults."""
    # A fresh dictionary prevents one negative case from changing another case's
    # metadata or extensions through shared mutable default state.
    return {}


@dataclass(frozen=True, slots=True)
class _Descriptor:
    """Provide a complete structural descriptor with replaceable test fields."""

    type: OpenIdentifier
    """Open task identity."""

    version: str | None = None
    """Optional opaque task contract version."""

    input_schema_id: str | None = None
    """Optional input schema identity."""

    output_schema_id: str | None = None
    """Optional output schema identity."""

    metadata: Extensions = field(default_factory=_empty_extensions)
    """Portable task metadata."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown portable task fields."""


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Keep the try boundary narrow so an unrelated setup or assertion failure
    # cannot satisfy a specific TaskDescriptor validation scenario.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_task_descriptor_validator_preserves_valid_open_implementation() -> None:
    """Verify valid unknown task data returns by identity without normalization."""
    descriptor = _Descriptor(
        type=OpenIdentifier("vendor.document_compare"),
        version="future-version",
        input_schema_id="schema.vendor.document_pair",
        output_schema_id="schema.vendor.comparison_result",
        metadata={"language": "zh-CN"},
        extensions={"vendor.options": {"explainDifferences": True}},
    )

    validated = validate_task_descriptor(descriptor)

    # Identity and exact values prove validation neither replaces the custom
    # object nor parses unknown type, version, schema, metadata, or extension data.
    assert validated is descriptor
    assert validated.type == OpenIdentifier("vendor.document_compare")
    assert validated.version == "future-version"
    assert validated.input_schema_id == "schema.vendor.document_pair"
    assert validated.output_schema_id == "schema.vendor.comparison_result"


def test_task_descriptor_validator_rejects_missing_or_invalid_type() -> None:
    """Verify the required task type exists and uses the nominal identifier."""

    @dataclass(frozen=True, slots=True)
    class _MissingType:
        """Intentionally omit the required task type property."""

        version: str | None = None
        """Optional version retained only to complete the negative fixture."""

        input_schema_id: str | None = None
        """Optional input schema identity."""

        output_schema_id: str | None = None
        """Optional output schema identity."""

        metadata: Extensions = field(default_factory=_empty_extensions)
        """Portable task metadata."""

        extensions: Extensions = field(default_factory=_empty_extensions)
        """Unknown portable fields."""

    # A missing property fails structural recognition. Present raw strings and
    # null values fail the nominal boundary before identifier syntax is accessed.
    _assert_raises(
        TypeError,
        lambda: validate_task_descriptor(cast(TaskDescriptor, _MissingType())),
        "must implement TaskDescriptor",
    )
    for task_type in (cast(OpenIdentifier, "conversation.generate"), None):
        _assert_raises(
            TypeError,
            lambda task_type=task_type: validate_task_descriptor(
                _Descriptor(cast(OpenIdentifier, task_type))
            ),
            "type must be an OpenIdentifier",
        )


def test_task_descriptor_validator_checks_open_type_syntax() -> None:
    """Verify standard and future types share the portable open grammar."""
    for task_type in ("conversation.generate", "vendor.future_task"):
        descriptor = _Descriptor(OpenIdentifier(task_type))

        # Known and unknown values are both accepted without a registry lookup.
        assert validate_task_descriptor(descriptor) is descriptor

    for invalid_type in ("", "Conversation.Generate", "vendor/task"):
        _assert_raises(
            ValueError,
            lambda invalid_type=invalid_type: validate_task_descriptor(
                _Descriptor(OpenIdentifier(invalid_type))
            ),
            "OpenIdentifier",
        )


def test_task_descriptor_validator_checks_optional_version() -> None:
    """Verify absent and opaque future versions pass while blank values fail."""
    for version in (None, "1.0", "future-version"):
        descriptor = _Descriptor(OpenIdentifier("conversation.generate"), version)

        # Validation preserves the exact optional string and never converts it
        # to SchemaVersion, SemVer, or another normalized representation.
        assert validate_task_descriptor(descriptor) is descriptor
        assert descriptor.version == version

    _assert_raises(
        TypeError,
        lambda: validate_task_descriptor(
            _Descriptor(
                OpenIdentifier("conversation.generate"),
                cast(str, 1),
            )
        ),
        "version must be a string or None",
    )
    for version in ("", " \t\n"):
        _assert_raises(
            ValueError,
            lambda version=version: validate_task_descriptor(
                _Descriptor(OpenIdentifier("conversation.generate"), version)
            ),
            "version must not be empty or whitespace",
        )


def test_task_descriptor_validator_checks_schema_ids_independently() -> None:
    """Verify each optional schema identity retains its own string boundary."""
    valid = _Descriptor(
        OpenIdentifier("conversation.generate"),
        input_schema_id="schema.conversation.input",
        output_schema_id=None,
    )

    # Independent optionality allows one schema identity without fabricating the
    # other, while malformed storage is reported at the exact field boundary.
    assert validate_task_descriptor(valid) is valid
    assert valid.input_schema_id == "schema.conversation.input"
    assert valid.output_schema_id is None
    for field_name, input_schema_id, output_schema_id in (
        ("input_schema_id", cast(str, 1), None),
        ("output_schema_id", None, cast(str, [])),
    ):
        _assert_raises(
            TypeError,
            lambda input_schema_id=input_schema_id, output_schema_id=output_schema_id: (
                validate_task_descriptor(
                    _Descriptor(
                        OpenIdentifier("conversation.generate"),
                        input_schema_id=input_schema_id,
                        output_schema_id=output_schema_id,
                    )
                )
            ),
            f"{field_name} must be a string or None",
        )


def test_task_descriptor_validator_checks_metadata_portability() -> None:
    """Verify metadata requires string keys and recursive portable JSON values."""
    cyclic: list[JsonValue] = []
    cyclic.append(cyclic)
    invalid_values: tuple[tuple[Extensions, type[BaseException], str], ...] = (
        (cast(Extensions, []), TypeError, "metadata must be a mapping"),
        (cast(Extensions, {1: "value"}), TypeError, "metadata keys"),
        (cast(Extensions, {"tuple": (1, 2)}), TypeError, "structurally valid"),
        ({"cycle": cyclic}, TypeError, "structurally valid"),
        ({"overflow": 2**53}, ValueError, "safe range"),
        ({"notFinite": math.inf}, ValueError, "must be finite"),
    )

    # Each malformed mapping varies one portable JSON rule while all descriptor
    # identity and extension fields remain valid.
    for metadata, exception_type, message in invalid_values:
        _assert_raises(
            exception_type,
            lambda metadata=metadata: validate_task_descriptor(
                _Descriptor(
                    OpenIdentifier("conversation.generate"),
                    metadata=metadata,
                )
            ),
            message,
        )


def test_task_descriptor_validator_checks_extensions_independently() -> None:
    """Verify unknown extensions use the same JSON policy after valid metadata."""
    descriptor = _Descriptor(
        OpenIdentifier("conversation.generate"),
        metadata={"valid": True},
        extensions={"future": math.nan},
    )

    # Valid metadata must not mask a later extension failure; the field-specific
    # boundary retains unknown keys but rejects non-portable values.
    _assert_raises(
        ValueError,
        lambda: validate_task_descriptor(descriptor),
        "must be finite",
    )
