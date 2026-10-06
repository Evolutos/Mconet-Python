"""Per-field precedence tests for interaction resource-limit resolution."""

from collections.abc import Callable
from functools import partial
from typing import cast

from mconet.core.domain import (
    InteractionResourceLimits,
    ResolvedInteractionResourceLimits,
    resolve_resource_limits,
)

_SDK_DEFAULTS = ResolvedInteractionResourceLimits(
    max_response_body_bytes=100,
    max_streaming_error_body_bytes=200,
    max_frame_bytes=300,
)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Match the source or field diagnostic so an unrelated resolution failure
    # cannot make an invalid-layer test pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_resource_limits_resolver_uses_complete_sdk_defaults() -> None:
    """Verify absent interaction and client layers preserve all SDK defaults."""
    resolved = resolve_resource_limits(_SDK_DEFAULTS)

    # Resolution always produces a complete immutable value rather than exposing
    # an optional layer or an implicit unlimited sentinel.
    assert resolved == _SDK_DEFAULTS


def test_resource_limits_resolver_applies_client_overrides_per_field() -> None:
    """Verify a client value replaces only its explicitly supplied fields."""
    client_limits = InteractionResourceLimits(
        max_response_body_bytes=110,
        max_frame_bytes=330,
    )

    resolved = resolve_resource_limits(
        _SDK_DEFAULTS,
        client_limits=client_limits,
    )

    # The absent streaming-error field falls through independently to its SDK
    # default instead of being captured by the client layer as a whole.
    assert resolved == ResolvedInteractionResourceLimits(110, 200, 330)


def test_resource_limits_resolver_applies_interaction_overrides_per_field() -> None:
    """Verify interaction values override client values one field at a time."""
    client_limits = InteractionResourceLimits(
        max_response_body_bytes=110,
        max_streaming_error_body_bytes=220,
    )
    interaction_limits = InteractionResourceLimits(
        max_response_body_bytes=111,
        max_frame_bytes=333,
    )

    resolved = resolve_resource_limits(
        _SDK_DEFAULTS,
        client_limits=client_limits,
        interaction_limits=interaction_limits,
    )

    # Each result records its own winning layer: interaction, client, and
    # interaction respectively, proving resolution does not replace whole objects.
    assert resolved == ResolvedInteractionResourceLimits(111, 220, 333)


def test_resource_limits_resolver_treats_empty_layers_as_no_overrides() -> None:
    """Verify present but empty optional layers do not mask lower priorities."""
    resolved = resolve_resource_limits(
        _SDK_DEFAULTS,
        client_limits=InteractionResourceLimits(),
        interaction_limits=InteractionResourceLimits(),
    )

    # Explicit layer presence alone has no precedence effect; only non-None
    # fields override a lower-priority value.
    assert resolved == _SDK_DEFAULTS


def test_resource_limits_resolver_does_not_mutate_source_layers() -> None:
    """Verify reusable client and single-interaction inputs remain unchanged."""
    client_limits = InteractionResourceLimits(max_response_body_bytes=110)
    interaction_limits = InteractionResourceLimits(max_frame_bytes=333)

    resolve_resource_limits(
        _SDK_DEFAULTS,
        client_limits=client_limits,
        interaction_limits=interaction_limits,
    )

    # Source values retain both explicit and absent fields, so resolving one
    # interaction cannot write defaults back into reusable client configuration.
    assert client_limits == InteractionResourceLimits(110, None, None)
    assert interaction_limits == InteractionResourceLimits(None, None, 333)


def test_resource_limits_resolver_rejects_invalid_overridden_layers() -> None:
    """Verify invalid explicit values fail even when a higher layer replaces them."""
    client_limits = InteractionResourceLimits(max_response_body_bytes=0)
    interaction_limits = InteractionResourceLimits(max_response_body_bytes=111)

    # Every provided value has its own validity contract; precedence cannot hide
    # a broken reusable Client configuration from initialization checks.
    _assert_raises(
        ValueError,
        lambda: resolve_resource_limits(
            _SDK_DEFAULTS,
            client_limits=client_limits,
            interaction_limits=interaction_limits,
        ),
        "max_response_body_bytes must be positive",
    )


def test_resource_limits_resolver_validates_every_source_tier() -> None:
    """Verify invalid SDK, client, and interaction fields all fail resolution."""
    invalid_cases = (
        (
            ResolvedInteractionResourceLimits(0, 200, 300),
            None,
            None,
            "max_response_body_bytes must be positive",
        ),
        (
            _SDK_DEFAULTS,
            InteractionResourceLimits(max_streaming_error_body_bytes=1 << 63),
            None,
            "max_streaming_error_body_bytes must fit signed 64-bit range",
        ),
        (
            _SDK_DEFAULTS,
            None,
            InteractionResourceLimits(max_frame_bytes=-1),
            "max_frame_bytes must be positive",
        ),
    )

    # The resolver validates complete defaults and both optional override tiers
    # before choosing any winner, keeping errors deterministic and pre-I/O.
    for sdk_defaults, client_limits, interaction_limits, message in invalid_cases:
        # Bind this iteration's layers into a zero-argument action without a
        # closure whose late-bound loop variables could select the wrong case.
        resolve_invalid_case = partial(
            resolve_resource_limits,
            sdk_defaults,
            client_limits=client_limits,
            interaction_limits=interaction_limits,
        )
        _assert_raises(
            ValueError,
            resolve_invalid_case,
            message,
        )


def test_resource_limits_resolver_rejects_wrong_layer_types() -> None:
    """Verify every source tier enforces its distinct nominal input contract."""
    invalid_calls = (
        (
            lambda: resolve_resource_limits(
                cast(ResolvedInteractionResourceLimits, InteractionResourceLimits())
            ),
            "sdk_defaults must be ResolvedInteractionResourceLimits",
        ),
        (
            lambda: resolve_resource_limits(
                _SDK_DEFAULTS,
                client_limits=cast(InteractionResourceLimits, _SDK_DEFAULTS),
            ),
            "client_limits must be InteractionResourceLimits or None",
        ),
        (
            lambda: resolve_resource_limits(
                _SDK_DEFAULTS,
                interaction_limits=cast(InteractionResourceLimits, object()),
            ),
            "interaction_limits must be InteractionResourceLimits or None",
        ),
    )

    # Complete resolved defaults cannot be confused with optional override
    # layers, and arbitrary objects cannot enter any tier through dynamic calls.
    for resolve_limits, message in invalid_calls:
        _assert_raises(TypeError, resolve_limits, message)
