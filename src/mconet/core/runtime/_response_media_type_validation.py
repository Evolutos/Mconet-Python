"""Compatibility validation for response media types and fixed decoders."""

from __future__ import annotations

from typing import Literal, cast

from mconet.core.domain import (
    CompatibilityPolicy,
    Diagnostic,
    ErrorCategory,
    InteractionPhase,
    MediaType,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.core.spi import (
    DecoderSelection,
    PayloadDecoder,
    TransportResponseMetadata,
)

_PROTOCOL_CATEGORY = ErrorCategory(OpenIdentifier("protocol"))
_UNSUPPORTED_FEATURE_CATEGORY = ErrorCategory(OpenIdentifier("unsupported_feature"))
_DECODING_PHASE = InteractionPhase(OpenIdentifier("decoding"))
_MEDIA_TYPE_MISMATCH_CODE = "response_media_type_mismatch"
_MEDIA_TYPE_MISMATCH_MESSAGE = (
    "Response media type is incompatible with the preselected decoder."
)
_MEDIA_TYPE_RELAXED_CODE = "response_media_type_compatibility_relaxed"
_MEDIA_TYPE_RELAXED_MESSAGE = (
    "Response media type was accepted by an explicit compatibility rule."
)
_UNSUPPORTED_POLICY_CODE = "unsupported_compatibility_policy"
_UNSUPPORTED_POLICY_MESSAGE = (
    "The response media type compatibility policy is not supported."
)
_STRICT_MODE = OpenIdentifier("strict")
_COMPATIBLE_MODE = OpenIdentifier("compatible")
_PERMISSIVE_MODE = OpenIdentifier("permissive")
_SUPPORTED_MODES = frozenset((_STRICT_MODE, _COMPATIBLE_MODE, _PERMISSIVE_MODE))

_MediaTypeMatch = Literal["exact", "relaxed", "incompatible"]


def validate_response_media_type(
    metadata: TransportResponseMetadata,
    selection: DecoderSelection,
    decoder: PayloadDecoder,
    policy: CompatibilityPolicy,
) -> tuple[Diagnostic, ...]:
    """Validate actual media type without replacing the preselected decoder.

    The actual response observation must satisfy both the planned media type,
    when present, and one media type declared by the fixed decoder's input
    contract, when any are declared. Strict mode requires exact immutable value
    equality. Compatible and permissive modes may accept parameter differences
    or an explicitly declared wildcard and return one warning diagnostic.

    Missing actual media type is valid only when neither the plan nor decoder
    constrains it. Unrelated types, undeclared aliases, and every other mismatch
    fail before decoding with a stable protocol error. Decoder behavior is never
    invoked and no candidate set is available for response-driven replacement.
    """
    metadata_value = cast(object, metadata)
    selection_value = cast(object, selection)
    decoder_value = cast(object, decoder)
    policy_value = cast(object, policy)

    # Validate every nominal boundary before reading nested facts. Checking all
    # four inputs independently keeps a malformed shadow field from being hidden
    # by a response that would otherwise take an early success branch.
    if not isinstance(metadata_value, TransportResponseMetadata):
        raise TypeError("metadata must be TransportResponseMetadata.")
    if not isinstance(selection_value, DecoderSelection):
        raise TypeError("selection must be a DecoderSelection.")
    if not isinstance(decoder_value, PayloadDecoder):
        raise TypeError("decoder must be a PayloadDecoder.")
    if not isinstance(policy_value, CompatibilityPolicy):
        raise TypeError("policy must be a CompatibilityPolicy.")

    # An open policy value is preserved by configuration, but this validator can
    # execute only strategies whose media-type semantics are defined here. It
    # must not silently reinterpret an unknown strategy as a standard mode.
    if policy.mode not in _SUPPORTED_MODES:
        raise _unsupported_policy_error()

    actual = metadata.media_type
    planned = selection.media_type
    decoder_media_types = _decoder_input_media_types(decoder)
    has_constraint = planned is not None or bool(decoder_media_types)

    # Absence cannot satisfy a declared plan or decoder representation. When no
    # constraint exists, preserving None is valid and does not invent a default.
    if actual is None:
        if has_constraint:
            raise _media_type_mismatch_error(metadata)
        return ()

    allow_relaxation = policy.mode != _STRICT_MODE
    plan_match = _match_media_type(actual, planned, allow_relaxation)
    decoder_match = _match_any_media_type(
        actual,
        decoder_media_types,
        allow_relaxation,
    )

    # Multiple input declarations form the fixed decoder's explicit accepted
    # representation set. Compatible modes may treat another declared member as
    # a plan alias only when the planned value itself is also declared; this
    # never infers +suffix, vendor, or binary aliases from spelling conventions.
    if (
        allow_relaxation
        and plan_match == "incompatible"
        and planned is not None
        and planned in decoder_media_types
        and decoder_match != "incompatible"
    ):
        plan_match = "relaxed"

    # Actual media must satisfy both independent sources of truth. In particular,
    # matching the plan cannot bypass the fixed decoder's declared inputs, while
    # only the explicit alias branch above can relax a different planned type.
    if plan_match == "incompatible" or decoder_match == "incompatible":
        raise _media_type_mismatch_error(metadata)

    # Exact validation is silent. A single warning represents any combination of
    # parameter or wildcard relaxations without exposing response/header values.
    if plan_match == "relaxed" or decoder_match == "relaxed":
        return (_media_type_relaxed_diagnostic(),)
    return ()


def _decoder_input_media_types(decoder: PayloadDecoder) -> tuple[MediaType, ...]:
    """Return declared decoder-input media types in contract order."""
    type_contract = decoder.descriptor.type_contract
    # Contract presence and port connectivity are validated before an execution
    # snapshot is built. Remaining defensive absence means this validator has no
    # descriptor media constraint; it does not duplicate the earlier error gate.
    if type_contract is None:
        return ()

    # Only encoded input representations constrain response Content-Type. Output
    # media metadata, if present, describes decoded values and cannot validate the
    # wire observation. Preserve duplicates and order because no mutation or
    # normalization is required for deterministic any-match evaluation.
    return tuple(
        port.media_type for port in type_contract.inputs if port.media_type is not None
    )


def _match_any_media_type(
    actual: MediaType,
    expected_values: tuple[MediaType, ...],
    allow_relaxation: bool,
) -> _MediaTypeMatch:
    """Match one actual type against optional decoder input alternatives."""
    # No declared decoder media types means this source contributes no constraint;
    # the plan may still independently constrain the same response observation.
    if not expected_values:
        return "exact"

    relaxed = False
    for expected in expected_values:
        # Exact acceptance dominates relaxed alternatives so declaration order
        # cannot turn an exact contract match into an unnecessary warning.
        match = _match_media_type(actual, expected, allow_relaxation)
        if match == "exact":
            return "exact"
        if match == "relaxed":
            relaxed = True
    return "relaxed" if relaxed else "incompatible"


def _match_media_type(
    actual: MediaType,
    expected: MediaType | None,
    allow_relaxation: bool,
) -> _MediaTypeMatch:
    """Classify exact, explicit relaxed, or incompatible media matching."""
    # An omitted plan value is non-restrictive. Descriptor alternatives are
    # evaluated separately so missing plan data cannot erase decoder constraints.
    if expected is None:
        return "exact"
    if actual == expected:
        return "exact"
    if not allow_relaxation:
        return "incompatible"

    # Compatible modes may ignore parameter differences only after type and
    # subtype match exactly. This never invents suffix aliases such as +json.
    if actual.type == expected.type and actual.subtype == expected.subtype:
        return "relaxed"

    # Wildcard behavior must be explicitly present in the expected plan or
    # decoder contract. A global */* or same-type subtype wildcard is supported;
    # malformed */concrete shapes do not acquire implicit matching semantics.
    if expected.type == "*" and expected.subtype == "*":
        return "relaxed"
    if expected.type == actual.type and expected.subtype == "*":
        return "relaxed"
    return "incompatible"


def _media_type_mismatch_error(
    metadata: TransportResponseMetadata,
) -> ModelInteractionError:
    """Create the stable protocol failure for an incompatible response type."""
    # Native status and request ID are already approved transport metadata and
    # aid correlation. Media values, headers, body bytes, decoder descriptors,
    # and policy details stay out of ordinary exception text and metadata.
    return ModelInteractionError(
        category=_PROTOCOL_CATEGORY,
        phase=_DECODING_PHASE,
        code=_MEDIA_TYPE_MISMATCH_CODE,
        message=_MEDIA_TYPE_MISMATCH_MESSAGE,
        status_code=metadata.status_code,
        request_id=metadata.request_id,
    )


def _unsupported_policy_error() -> ModelInteractionError:
    """Create a normalized failure for an unknown media compatibility strategy."""
    # Keep the open policy identifier out of ordinary exception text. Older SDKs
    # preserve the value in configuration but must fail safely when they cannot
    # execute its semantics instead of silently substituting a standard mode.
    return ModelInteractionError(
        category=_UNSUPPORTED_FEATURE_CATEGORY,
        phase=_DECODING_PHASE,
        code=_UNSUPPORTED_POLICY_CODE,
        message=_UNSUPPORTED_POLICY_MESSAGE,
    )


def _media_type_relaxed_diagnostic() -> Diagnostic:
    """Create one non-sensitive warning for explicit compatibility relaxation."""
    # The fixed diagnostic reports that a declared rule was used without copying
    # actual or expected Content-Type values into logs or output diagnostics.
    return Diagnostic(
        code=_MEDIA_TYPE_RELAXED_CODE,
        severity="warning",
        phase=_DECODING_PHASE,
        message=_MEDIA_TYPE_RELAXED_MESSAGE,
    )
