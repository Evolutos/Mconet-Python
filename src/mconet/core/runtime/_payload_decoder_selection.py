"""Deterministic preselection of response payload decoders."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import OpenIdentifier
from mconet.core.runtime._component_source_merge import ComponentSourceLayers
from mconet.core.runtime._single_component_selection import select_required_component
from mconet.core.spi import (
    ComponentRole,
    DecoderSelection,
    PayloadDecoder,
    RuntimeComponent,
)

_SUCCESS_PAYLOAD_DECODER_ROLE = ComponentRole(
    OpenIdentifier("codec.response.success-decoder")
)


def select_success_payload_decoder(
    selection: DecoderSelection,
    layers: ComponentSourceLayers,
) -> PayloadDecoder:
    """Fix the unique success decoder from planned facts before network I/O.

    Planned media type constrains the decoder's byte-representation inputs,
    while planned schema identity constrains its decoded-payload outputs. The
    generic required-component selector owns source precedence and stable
    missing or ambiguity failures; this role-specific function only defines
    decoder compatibility and returns the exact selected runtime instance.

    No decoder behavior is invoked, no response metadata is inspected, and no
    lower source can become a fallback after a higher source is present.
    """
    # Success and error paths use the same compatibility rules but occupy
    # independent component roles. Fixing the role here prevents callers from
    # redirecting a successful response plan to another execution-chain slot.
    return _select_payload_decoder(
        _SUCCESS_PAYLOAD_DECODER_ROLE,
        selection,
        layers,
    )


def _select_payload_decoder(
    role: ComponentRole,
    selection: DecoderSelection,
    layers: ComponentSourceLayers,
) -> PayloadDecoder:
    """Select one payload decoder for a caller-fixed response-path role.

    The private shared primitive owns media and schema matching so later error
    response preselection cannot drift from the successful-response rules. The
    caller remains responsible for supplying a fixed Core-defined role rather
    than exposing role choice through configuration.
    """
    selection_value = cast(object, selection)

    # Validate the nominal plan boundary before the matcher closes over its
    # fields. This produces a direct configuration error instead of allowing an
    # arbitrary look-alike object to influence deterministic component choice.
    if not isinstance(selection_value, DecoderSelection):
        raise TypeError("selection must be a DecoderSelection.")

    def matches(component: RuntimeComponent) -> bool:
        """Return whether one runtime component satisfies the decoder plan."""
        # Structural protocol conformance prevents another component kind from
        # being selected merely because its descriptor contains similar ports.
        if not isinstance(component, PayloadDecoder):
            return False

        # With no media or schema constraint, every behavioral decoder remains
        # a candidate. Contract presence and port-to-port compatibility are
        # validated after component resolution, so this resolver must not hide
        # an invalid decoder or silently remove a genuine ambiguity.
        if selection.media_type is None and selection.schema_id is None:
            return True

        type_contract = component.descriptor.type_contract
        # A constrained plan needs descriptor evidence at selection time: media
        # compatibility is declared on encoded inputs and schema compatibility
        # on decoded outputs. A missing contract cannot prove either fact.
        if type_contract is None:
            return False

        # An omitted criterion is intentionally non-restrictive. When supplied,
        # equality remains exact, including MediaType parameters and schema text;
        # response-time Content-Type normalization belongs to a later validator.
        media_matches = selection.media_type is None or any(
            port.media_type == selection.media_type for port in type_contract.inputs
        )
        schema_matches = selection.schema_id is None or any(
            port.schema_id == selection.schema_id for port in type_contract.outputs
        )
        return media_matches and schema_matches

    # The generic selector validates the nominal role and four-layer source
    # shape, then snapshots the same component object. The matcher has already
    # proved PayloadDecoder conformance, so the cast narrows only static typing
    # and neither wraps the decoder nor calls ``decode``.
    selected = select_required_component(
        role,
        layers,
        matches,
    )
    return cast(PayloadDecoder, selected.component)
