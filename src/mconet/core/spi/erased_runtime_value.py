"""Non-serializable carrier for runtime values with portable type metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar, cast

from mconet.core.domain import (
    ErrorCategory,
    InteractionPhase,
    ModelInteractionError,
    OpenIdentifier,
)

_COMPONENT_TYPE_MISMATCH_CATEGORY = ErrorCategory(
    OpenIdentifier("invalid_component_configuration")
)
_COMPONENT_TYPE_VALIDATION_PHASE = InteractionPhase(
    OpenIdentifier("component_type_validation")
)
_COMPONENT_TYPE_MISMATCH_CODE = "component_type_mismatch"
_COMPONENT_TYPE_MISMATCH_MESSAGE = (
    "Erased runtime value does not match the requested Python type."
)

_ValueT = TypeVar("_ValueT")


@dataclass(frozen=True, slots=True, eq=False)
class ErasedRuntimeValue:
    """Wrap one native runtime object with portable type metadata.

    ``type_id`` and ``schema_id`` describe the cross-language contract while
    ``value`` retains the exact platform-native object. The wrapper is immutable
    but does not copy, serialize, compare, or take ownership of the wrapped
    object. Logical contract compatibility is validated before component use;
    :meth:`value_as` provides the final safe Python runtime type boundary.
    """

    type_id: OpenIdentifier
    """Portable identifier for the wrapped value's logical type."""

    value: object
    """Exact platform-native object hidden behind the non-generic SPI surface."""

    schema_id: str | None = None
    """Optional schema identifier refining the logical value contract."""

    def __post_init__(self) -> None:
        """Require nominal metadata shapes without inspecting the native value."""
        type_id = cast(object, self.type_id)
        schema_id = cast(object, self.schema_id)

        # Metadata stays nominal and lossless. Syntax and component-port
        # compatibility belong to their dedicated validators and resolvers.
        if not isinstance(type_id, OpenIdentifier):
            raise TypeError("ErasedRuntimeValue type_id must be an OpenIdentifier.")
        if schema_id is not None and not isinstance(schema_id, str):
            raise TypeError("ErasedRuntimeValue schema_id must be a string or None.")

        # The native value intentionally accepts every Python object, including
        # None and mutable integration-owned instances, without copying it.

    def value_as(self, expected_type: type[_ValueT]) -> _ValueT:
        """Return the wrapped object after a safe Python runtime type check.

        Args:
            expected_type: Concrete Python class or runtime-checkable protocol
                expected by the consuming component.

        Returns:
            The exact wrapped object, narrowed to ``expected_type``.

        Raises:
            TypeError: If ``expected_type`` is not a runtime class.
            ModelInteractionError: If the wrapped object does not implement the
                requested Python runtime type.

        Notes:
            This check does not replace ``type_id``, Schema, media type, or port
            compatibility validation. Core completes those checks before a
            component attempts platform-native retrieval.
        """
        candidate_type = cast(object, expected_type)
        # Validate the retrieval request itself before calling isinstance so a
        # dynamically supplied non-type produces a stable programming error.
        if not isinstance(candidate_type, type):
            raise TypeError("expected_type must be a Python runtime type.")

        # isinstance preserves normal Python subtype semantics. A mismatch is a
        # normalized component-boundary failure and never exposes value repr.
        if not isinstance(self.value, expected_type):
            raise _component_type_mismatch_error()
        return self.value


def _component_type_mismatch_error() -> ModelInteractionError:
    """Create the stable normalized error for a failed native value retrieval."""
    # Keep the error independent of producer type IDs, schema IDs, Python class
    # names, and value representations so diagnostics cannot expose payload data.
    return ModelInteractionError(
        category=_COMPONENT_TYPE_MISMATCH_CATEGORY,
        phase=_COMPONENT_TYPE_VALIDATION_PHASE,
        code=_COMPONENT_TYPE_MISMATCH_CODE,
        message=_COMPONENT_TYPE_MISMATCH_MESSAGE,
    )
