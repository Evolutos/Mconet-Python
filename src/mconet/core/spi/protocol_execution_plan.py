"""Immutable component and transport requirements for protocol execution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from mconet.core.spi.component_type_contract import ComponentTypeContract
from mconet.core.spi.decoder_selection import DecoderSelection
from mconet.core.spi.encoder_selection import EncoderSelection
from mconet.core.spi.planned_component_selection import PlannedComponentSelection
from mconet.core.spi.transport_request_plan import TransportRequestPlan
from mconet.core.spi.transport_selection import TransportSelection

_EMPTY_EXTENSIONS: Mapping[str, object] = MappingProxyType({})


def _empty_extensions() -> Mapping[str, object]:
    """Return the shared immutable empty protocol-extension mapping."""
    # Empty membership contains no caller-owned bindings, so all default plans
    # can safely share one allocation without sharing mutable interaction state.
    return _EMPTY_EXTENSIONS


def _empty_type_contract() -> ComponentTypeContract:
    """Create an empty contract when a protocol declares no runtime ports."""
    # Use an explicit factory to satisfy dataclass default rules while keeping
    # construction local and making the absence of declared ports intentional.
    return ComponentTypeContract()


@dataclass(frozen=True, slots=True)
class ProtocolExecutionPlan:
    """Describe protocol-selected execution requirements before network I/O.

    The plan fixes request construction, separate success and error decoding,
    transport selection, mode-specific component requirements, and the runtime
    type boundary. It contains criteria rather than resolved component instances,
    allowing deterministic selection and compatibility checks to happen later.

    Open media types, transport kinds, component roles, and contracts are retained
    without applying release-scope policy. The runtime scope gate owns rejection
    of plans outside the currently supported unary, JSON, HTTP, and bytes path.
    """

    transport_plan: TransportRequestPlan
    """Protocol-owned request facts used by later payload and transport stages."""

    payload_encoder: EncoderSelection
    """Criteria for selecting the single payload encoder."""

    success_decoder: DecoderSelection
    """Criteria for selecting the successful-response decoder."""

    error_decoder: DecoderSelection
    """Independent criteria for selecting the error-response decoder."""

    transport: TransportSelection
    """Transport kind and capabilities required by the protocol."""

    mode_components: tuple[PlannedComponentSelection, ...] = ()
    """Ordered requirements for components introduced by an interaction mode."""

    type_contract: ComponentTypeContract = field(default_factory=_empty_type_contract)
    """Runtime input and output ports expected across the protocol boundary."""

    extensions: Mapping[str, object] = field(default_factory=_empty_extensions)
    """Read-only top-level snapshot of protocol-specific planning values."""

    def __post_init__(self) -> None:
        """Validate established boundaries and detach mutable collection membership."""
        transport_plan = cast(object, self.transport_plan)
        payload_encoder = cast(object, self.payload_encoder)
        success_decoder = cast(object, self.success_decoder)
        error_decoder = cast(object, self.error_decoder)
        transport = cast(object, self.transport)
        mode_components = cast(object, self.mode_components)
        type_contract = cast(object, self.type_contract)

        # Require each completed planning value by its nominal boundary. This
        # prevents raw mappings and strings from bypassing the invariants already
        # established by their dedicated value objects.
        if not isinstance(transport_plan, TransportRequestPlan):
            raise TypeError(
                "ProtocolExecutionPlan transport_plan must be a TransportRequestPlan."
            )
        if not isinstance(payload_encoder, EncoderSelection):
            raise TypeError(
                "ProtocolExecutionPlan payload_encoder must be an EncoderSelection."
            )
        if not isinstance(success_decoder, DecoderSelection):
            raise TypeError(
                "ProtocolExecutionPlan success_decoder must be a DecoderSelection."
            )
        if not isinstance(error_decoder, DecoderSelection):
            raise TypeError(
                "ProtocolExecutionPlan error_decoder must be a DecoderSelection."
            )
        if not isinstance(transport, TransportSelection):
            raise TypeError(
                "ProtocolExecutionPlan transport must be a TransportSelection."
            )

        # Tuple storage preserves adapter declaration order while preventing a
        # caller from adding or removing mode roles after component resolution.
        if not isinstance(mode_components, tuple):
            raise TypeError("ProtocolExecutionPlan mode_components must be a tuple.")
        for component in cast(tuple[object, ...], mode_components):
            if not isinstance(component, PlannedComponentSelection):
                raise TypeError(
                    "ProtocolExecutionPlan mode_components must contain "
                    "PlannedComponentSelection values."
                )

        # The contract is declarative and open: a later compatibility gate checks
        # adjacent ports and current bytes-only support without mutating this plan.
        if not isinstance(type_contract, ComponentTypeContract):
            raise TypeError(
                "ProtocolExecutionPlan type_contract must be a ComponentTypeContract."
            )

        # Snapshot only top-level membership. Extension values are deliberately
        # opaque local objects and therefore retain identity for their consumer.
        object.__setattr__(self, "extensions", _snapshot_extensions(self.extensions))


def _snapshot_extensions(value: object) -> Mapping[str, object]:
    """Copy a string-keyed extension mapping into read-only top-level storage."""
    # Named string keys form a stable cross-language extension surface; accepting
    # sequences or non-string keys would make lookup and serialization ambiguous.
    if not isinstance(value, Mapping):
        raise TypeError("ProtocolExecutionPlan extensions must be a mapping.")
    source = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in source):
        raise TypeError("ProtocolExecutionPlan extensions keys must be strings.")

    # Reuse the immutable singleton for the common empty plan and allocate a
    # detached dictionary only when caller-owned membership actually exists.
    if not source:
        return _EMPTY_EXTENSIONS
    snapshot = dict(cast(Mapping[str, object], source))
    return MappingProxyType(snapshot)
