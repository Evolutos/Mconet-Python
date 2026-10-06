"""Immutable service-protocol state carried by parsed model responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.open_identifier import (
    OpenIdentifier,
    validate_open_identifier,
)


@dataclass(frozen=True, slots=True)
class ProtocolState:
    """Preserve one typed opaque state value from a service protocol.

    Service identity, protocol identity, and state-type identity remain separate
    so the same protocol can expose multiple states and the same state name from
    different services cannot become ambiguous. Core validates but does not
    interpret ``state_value``; the owning integration defines its semantics.

    A required JsonValue may explicitly be ``None`` when the protocol reported
    JSON null. Absence of an entire ProtocolState remains a collection-level fact
    owned by the parsed response or output that contains these values.
    """

    service_id: OpenIdentifier
    """Open identifier of the model service that produced the state."""

    protocol_id: OpenIdentifier
    """Open identifier of the protocol that defines the state semantics."""

    state_type: OpenIdentifier
    """Open identifier classifying the opaque state value shape and meaning."""

    state_value: JsonValue
    """Required portable JSON state retained without Core interpretation."""

    def __post_init__(self) -> None:
        """Validate all identities and the complete portable JSON state value."""
        # Validate each identity independently so service routing, protocol
        # ownership, and state classification cannot substitute for one another.
        for field_name, value in (
            ("service_id", cast(object, self.service_id)),
            ("protocol_id", cast(object, self.protocol_id)),
            ("state_type", cast(object, self.state_type)),
        ):
            _validate_identifier(value, field_name)

        # State remains opaque to Core, but recursive shape, cycles, numeric range,
        # and finiteness must be safe before it crosses platform or process bounds.
        validate_json_value_numbers(self.state_value)


def _validate_identifier(value: object, field_name: str) -> None:
    """Require one nominal portable open identifier field."""
    # A bare string cannot act as an alternate identity representation even when
    # it contains valid identifier text; all three fields share one nominal type.
    if not isinstance(value, OpenIdentifier):
        raise TypeError(f"ProtocolState {field_name} must be an OpenIdentifier.")

    # Apply the common portable grammar without comparing against known services,
    # protocols, or state types, preserving future integration namespaces.
    validate_open_identifier(value)
