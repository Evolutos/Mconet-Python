"""Frozen R1 JSON payload contract aligned with the erased runtime port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain import JsonValue, validate_json_value_numbers
from mconet.core.spi.erased_runtime_value import ErasedRuntimeValue


@dataclass(frozen=True, slots=True, eq=False)
class JsonPayload(ErasedRuntimeValue):
    """Carry one JSON value through the erased adapter and codec port.

    ``type_id`` and ``schema_id`` keep the semantic port facts produced by a
    protocol adapter. ``value`` is narrowed to :data:`JsonValue`, so bytes,
    class instances, tuples, and other non-JSON representations cannot cross
    the JSON codec boundary. The envelope is an :class:`ErasedRuntimeValue`,
    which lets a task protocol adapter place it directly on
    ``ProtocolRequestPlan.payload`` without reconstructing the port.

    The contract does not encode or decode bytes, match a media type, declare
    component capabilities, select a component, or read task, access, or
    authorization state. String content is preserved exactly; UTF-8 transcoding
    belongs to the separate encoding utility. The envelope does not copy the
    JSON object, so ownership of a mutable array or object stays with the
    producer, matching the erased runtime carrier. Envelope equality stays
    identity-based, so JSON contents do not define payload equality.
    """

    value: JsonValue
    """JSON value carried by the erased payload port."""

    def __post_init__(self) -> None:
        """Require erased port metadata, then narrow the value to portable JSON.

        Raises:
            TypeError: If metadata has the wrong shape or ``value`` is not
                structurally JSON.
            ValueError: If a JSON number is outside the portable range.
        """
        # Metadata stays on the same nominal contract as every other erased
        # port. JSON narrowing must not invent a second type-id or schema-id
        # grammar, and slots dataclasses do not support super() here.
        ErasedRuntimeValue.__post_init__(self)

        candidate = cast(object, self.value)
        try:
            # Structural and numeric checks share the domain JSON contract so
            # the codec port cannot accept a value the rest of the SDK rejects.
            validate_json_value_numbers(cast(JsonValue, candidate))
        except TypeError as error:
            raise TypeError(
                "JsonPayload value must be a structurally valid JsonValue."
            ) from error
        except ValueError as error:
            raise ValueError(
                "JsonPayload value must use portable JSON numbers."
            ) from error

    @classmethod
    def from_erased(cls, erased: ErasedRuntimeValue) -> JsonPayload:
        """Narrow an erased runtime port to the frozen JSON value contract.

        Args:
            erased: Adapter or decoder payload whose value must already be JSON.

        Returns:
            The same instance when ``erased`` is already a JsonPayload.
            Otherwise a new envelope that retains the original type id, schema
            id, and JSON object.

        Raises:
            TypeError: If ``erased`` is not an erased runtime value or its
                value is not structurally JSON.
            ValueError: If a JSON number is outside the portable range.
        """
        candidate = cast(object, erased)
        if isinstance(candidate, JsonPayload):
            # The contract is already frozen. Reconstructing would give callers
            # that cache the adapter payload a different envelope identity.
            return candidate
        if not isinstance(candidate, ErasedRuntimeValue):
            raise TypeError("JsonPayload source must be an ErasedRuntimeValue.")

        # Route every widened value through the validating constructor so a
        # caller cannot skip the JSON port check by using the parent initializer.
        return cls(
            candidate.type_id,
            cast(JsonValue, candidate.value),
            candidate.schema_id,
        )
