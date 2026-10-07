"""Tests for response media-type validation against a fixed decoder."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from mconet.core.domain import (
    Bytes,
    CompatibilityPolicy,
    Headers,
    MediaType,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.core.runtime._response_media_type_validation import (
    validate_response_media_type,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ComponentTypeContract,
    ComponentTypePort,
    DecoderSelection,
    ErasedRuntimeValue,
    PayloadDecoder,
    TransportOutcome,
    TransportResponseMetadata,
)

_JSON = MediaType("application", "json")
_JSON_UTF8 = MediaType("application", "json", (("charset", "utf-8"),))
_PROBLEM_JSON = MediaType("application", "problem+json")


@dataclass(slots=True)
class _Decoder:
    """Complete decoder fixture with observable forbidden execution."""

    descriptor: ComponentDescriptor
    decode_calls: int = 0

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Record actual decode calls while returning a valid runtime value."""
        # Media validation must finish before this behavior can execute. Keeping
        # it valid makes isinstance checks exercise the real PayloadDecoder SPI.
        self.decode_calls += 1
        return ErasedRuntimeValue(OpenIdentifier("protocol.payload"), raw_data)


def _decoder(*media_types: MediaType, contract: bool = True) -> _Decoder:
    """Build one decoder with ordered encoded-input representation alternatives."""
    # Each input port declares one accepted wire representation. Output metadata
    # is irrelevant to Content-Type validation and intentionally omitted.
    type_contract = None
    if contract:
        type_contract = ComponentTypeContract(
            inputs=tuple(
                ComponentTypePort(
                    f"encoded{index}",
                    OpenIdentifier("transport.bytes"),
                    media_type=media_type,
                )
                for index, media_type in enumerate(media_types)
            ),
            outputs=(
                ComponentTypePort(
                    "payload",
                    OpenIdentifier("protocol.payload"),
                    media_type=_PROBLEM_JSON,
                ),
            ),
        )
    return _Decoder(ComponentDescriptor("decoder", "1", "plugin", type_contract))


def _metadata(
    media_type: MediaType | None,
    *,
    status_code: int | None = None,
    request_id: str | None = None,
) -> TransportResponseMetadata:
    """Build immutable response metadata with one actual media observation."""
    # Outcome is already normalized and deliberately irrelevant to this gate;
    # status and request ID support stable error-correlation assertions.
    return TransportResponseMetadata(
        TransportOutcome(OpenIdentifier("success")),
        Headers(),
        status_code=status_code,
        media_type=media_type,
        request_id=request_id,
    )


def _policy(mode: str) -> CompatibilityPolicy:
    """Build one standard or extension compatibility strategy value."""
    # Construction preserves unknown identifiers so the validator, rather than
    # the value object, owns supported media-policy behavior.
    return CompatibilityPolicy(OpenIdentifier(mode))


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Require one action to fail through the intended stable boundary."""
    try:
        action()
    except exception_type as error:
        # Match a stable fragment so an incidental fixture or protocol exception
        # cannot make a negative compatibility test appear successful.
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_exact_actual_plan_and_decoder_media_type_is_silent() -> None:
    """Accept one exact response representation without a diagnostic."""
    decoder = _decoder(_JSON)

    diagnostics = validate_response_media_type(
        _metadata(_JSON),
        DecoderSelection(media_type=_JSON),
        decoder,
        _policy("strict"),
    )

    assert diagnostics == ()
    assert decoder.decode_calls == 0


def test_strict_mode_rejects_parameter_difference() -> None:
    """Require complete MediaType equality, including parameters, in strict mode."""
    decoder = _decoder(_JSON)

    raised = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: validate_response_media_type(
                _metadata(_JSON_UTF8, status_code=200, request_id="request-7"),
                DecoderSelection(media_type=_JSON),
                decoder,
                _policy("strict"),
            ),
            "Response media type is incompatible",
        ),
    )

    # Stable protocol fields retain safe correlation metadata without including
    # actual/expected media values, decoder labels, headers, or response bytes.
    assert str(raised.category) == "protocol"
    assert str(raised.phase) == "decoding"
    assert raised.code == "response_media_type_mismatch"
    assert raised.status_code == 200
    assert raised.request_id == "request-7"
    assert raised.service_error_code is None
    assert raised.recovery is None
    assert raised.cause is None
    assert "application" not in str(raised)
    assert decoder.decode_calls == 0


def test_compatible_mode_accepts_parameter_difference_with_warning() -> None:
    """Allow same type/subtype parameter drift and report one warning."""
    decoder = _decoder(_JSON)

    diagnostics = validate_response_media_type(
        _metadata(_JSON_UTF8),
        DecoderSelection(media_type=_JSON),
        decoder,
        _policy("compatible"),
    )

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.code == "response_media_type_compatibility_relaxed"
    assert diagnostic.severity == "warning"
    assert str(diagnostic.phase) == "decoding"
    assert diagnostic.path is None
    assert diagnostic.service_id is None
    assert diagnostic.details is None
    assert "application" not in diagnostic.message
    assert decoder.decode_calls == 0


def test_permissive_mode_uses_same_bounded_parameter_relaxation() -> None:
    """Keep permissive media relaxation bounded by matching type and subtype."""
    decoder = _decoder(_JSON_UTF8)

    diagnostics = validate_response_media_type(
        _metadata(_JSON),
        DecoderSelection(media_type=_JSON_UTF8),
        decoder,
        _policy("permissive"),
    )

    assert tuple(item.code for item in diagnostics) == (
        "response_media_type_compatibility_relaxed",
    )
    assert decoder.decode_calls == 0


def test_incompatible_subtype_fails_under_every_policy() -> None:
    """Never treat an undeclared suffix or different subtype as compatible."""
    for mode in ("strict", "compatible", "permissive"):
        decoder = _decoder(_JSON)

        raised = cast(
            ModelInteractionError,
            _assert_raises(
                ModelInteractionError,
                lambda mode=mode, decoder=decoder: validate_response_media_type(
                    _metadata(_PROBLEM_JSON),
                    DecoderSelection(media_type=_JSON),
                    decoder,
                    _policy(mode),
                ),
                "Response media type is incompatible",
            ),
        )

        # +json does not become an alias merely because its suffix resembles the
        # planned JSON subtype; aliases require an explicit future declaration.
        assert raised.code == "response_media_type_mismatch"
        assert decoder.decode_calls == 0


def test_missing_actual_media_type_fails_when_constrained() -> None:
    """Reject an absent response observation when plan or decoder constrains it."""
    plan_constrained = _decoder(contract=False)
    decoder_constrained = _decoder(_JSON)

    for selection, decoder in (
        (DecoderSelection(media_type=_JSON), plan_constrained),
        (DecoderSelection(), decoder_constrained),
    ):
        raised = cast(
            ModelInteractionError,
            _assert_raises(
                ModelInteractionError,
                lambda selection=selection, decoder=decoder: (
                    validate_response_media_type(
                        _metadata(None),
                        selection,
                        decoder,
                        _policy("compatible"),
                    )
                ),
                "Response media type is incompatible",
            ),
        )
        assert raised.code == "response_media_type_mismatch"
        assert decoder.decode_calls == 0


def test_missing_or_present_actual_type_passes_without_constraints() -> None:
    """Avoid inventing a required representation when neither source declares one."""
    decoder = _decoder(contract=False)

    missing = validate_response_media_type(
        _metadata(None),
        DecoderSelection(),
        decoder,
        _policy("strict"),
    )
    present = validate_response_media_type(
        _metadata(_PROBLEM_JSON),
        DecoderSelection(),
        decoder,
        _policy("strict"),
    )

    assert missing == present == ()
    assert decoder.decode_calls == 0


def test_decoder_input_alternatives_apply_when_plan_is_unconstrained() -> None:
    """Accept any explicitly declared decoder input representation alternative."""
    decoder = _decoder(_JSON, _PROBLEM_JSON)

    diagnostics = validate_response_media_type(
        _metadata(_PROBLEM_JSON),
        DecoderSelection(),
        decoder,
        _policy("strict"),
    )

    # The output port carries an intentionally unrelated media value and must not
    # influence actual Content-Type validation in either direction.
    assert diagnostics == ()
    assert decoder.decode_calls == 0


def test_declared_decoder_alias_requires_relaxed_policy_and_warns() -> None:
    """Allow plan drift only across alternatives declared by the fixed decoder."""
    decoder = _decoder(_JSON, _PROBLEM_JSON)

    strict_error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: validate_response_media_type(
                _metadata(_PROBLEM_JSON),
                DecoderSelection(media_type=_JSON),
                decoder,
                _policy("strict"),
            ),
            "Response media type is incompatible",
        ),
    )
    diagnostics = validate_response_media_type(
        _metadata(_PROBLEM_JSON),
        DecoderSelection(media_type=_JSON),
        decoder,
        _policy("compatible"),
    )

    # Both values are explicit members of this decoder's input contract. The
    # policy relaxes only their plan mismatch and reports the decision.
    assert strict_error.code == "response_media_type_mismatch"
    assert tuple(item.code for item in diagnostics) == (
        "response_media_type_compatibility_relaxed",
    )
    assert decoder.decode_calls == 0


def test_explicit_wildcard_requires_relaxed_policy_and_warns() -> None:
    """Honor only declared wildcard ranges under compatible policy modes."""
    application_wildcard = MediaType("application", "*")
    decoder = _decoder(application_wildcard)

    strict_error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: validate_response_media_type(
                _metadata(_PROBLEM_JSON),
                DecoderSelection(media_type=application_wildcard),
                decoder,
                _policy("strict"),
            ),
            "Response media type is incompatible",
        ),
    )
    diagnostics = validate_response_media_type(
        _metadata(_PROBLEM_JSON),
        DecoderSelection(media_type=application_wildcard),
        decoder,
        _policy("compatible"),
    )

    assert strict_error.code == "response_media_type_mismatch"
    assert tuple(item.code for item in diagnostics) == (
        "response_media_type_compatibility_relaxed",
    )
    assert decoder.decode_calls == 0


def test_rejects_unsupported_open_policy_without_fallback() -> None:
    """Do not reinterpret an unknown compatibility strategy as a standard mode."""
    decoder = _decoder(_JSON)

    raised = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: validate_response_media_type(
                _metadata(_JSON),
                DecoderSelection(media_type=_JSON),
                decoder,
                _policy("vendor.audit_compatible"),
            ),
            "compatibility policy is not supported",
        ),
    )

    assert str(raised.category) == "unsupported_feature"
    assert str(raised.phase) == "decoding"
    assert raised.code == "unsupported_compatibility_policy"
    assert "vendor" not in str(raised)
    assert decoder.decode_calls == 0


def test_rejects_malformed_inputs_before_media_validation() -> None:
    """Require complete nominal metadata, plan, decoder, and policy boundaries."""
    decoder = _decoder(_JSON)
    metadata = _metadata(_JSON)
    selection = DecoderSelection(media_type=_JSON)
    policy = _policy("strict")

    invalid_calls: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: validate_response_media_type(
                cast(TransportResponseMetadata, object()),
                selection,
                decoder,
                policy,
            ),
            "metadata must be TransportResponseMetadata",
        ),
        (
            lambda: validate_response_media_type(
                metadata,
                cast(DecoderSelection, object()),
                decoder,
                policy,
            ),
            "selection must be a DecoderSelection",
        ),
        (
            lambda: validate_response_media_type(
                metadata,
                selection,
                cast(PayloadDecoder, object()),
                policy,
            ),
            "decoder must be a PayloadDecoder",
        ),
        (
            lambda: validate_response_media_type(
                metadata,
                selection,
                decoder,
                cast(CompatibilityPolicy, object()),
            ),
            "policy must be a CompatibilityPolicy",
        ),
    )

    # Evaluate every invalid position independently so earlier arguments cannot
    # mask validation of a later shadow field.
    for action, message in invalid_calls:
        _assert_raises(TypeError, action, message)
    assert decoder.decode_calls == 0
