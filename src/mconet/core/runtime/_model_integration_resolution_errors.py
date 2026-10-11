"""Normalized failures of default model integration resolution."""

from __future__ import annotations

from mconet.core.domain import (
    ErrorCategory,
    InteractionPhase,
    ModelInteractionError,
    OpenIdentifier,
)

UNSUPPORTED_MODEL_INTEGRATION_CODE = "unsupported_model_integration"
"""Stable code when no integration combination serves the request."""

AMBIGUOUS_MODEL_INTEGRATION_CODE = "ambiguous_model_integration"
"""Stable code for a duplicate type key or an undeterminable chain order."""

_UNSUPPORTED_FEATURE = ErrorCategory(OpenIdentifier("unsupported_feature"))
_INVALID_COMPONENT_CONFIGURATION = ErrorCategory(
    OpenIdentifier("invalid_component_configuration")
)
_MODEL_INTEGRATION_RESOLUTION = InteractionPhase(
    OpenIdentifier("model_integration_resolution")
)


def unsupported_model_integration_error() -> ModelInteractionError:
    """Return the failure for a request no integration combination serves.

    The message is fixed. It names neither the request's protocol, task, or
    mode nor any binding, so it reveals no plugin or application assembly.

    Returns:
        A new ``unsupported_feature`` error in the resolution phase.
    """
    return ModelInteractionError(
        category=_UNSUPPORTED_FEATURE,
        phase=_MODEL_INTEGRATION_RESOLUTION,
        code=UNSUPPORTED_MODEL_INTEGRATION_CODE,
        message="No model integration supports the target, task, and mode.",
    )


def unsupported_direct_adapter_error() -> ModelInteractionError:
    """Return the failure for an injected adapter that rejects the request.

    It shares the ``unsupported_model_integration`` code, because the only
    integration the caller allowed cannot serve the request, but its message
    tells the caller the injected adapter, not the default resolver, refused.

    Returns:
        A new ``unsupported_feature`` error in the resolution phase.
    """
    return ModelInteractionError(
        category=_UNSUPPORTED_FEATURE,
        phase=_MODEL_INTEGRATION_RESOLUTION,
        code=UNSUPPORTED_MODEL_INTEGRATION_CODE,
        message=(
            "The injected task protocol adapter does not support the target, "
            "task, and mode."
        ),
    )


def ambiguous_model_integration_error() -> ModelInteractionError:
    """Return the failure for resolver assembly with no single answer.

    It is raised while the resolver is constructed, never on a request, so a
    misassembled resolver fails before any interaction or network I/O.

    Returns:
        A new ``invalid_component_configuration`` error in the resolution phase.
    """
    return ModelInteractionError(
        category=_INVALID_COMPONENT_CONFIGURATION,
        phase=_MODEL_INTEGRATION_RESOLUTION,
        code=AMBIGUOUS_MODEL_INTEGRATION_CODE,
        message=(
            "Model integration resolver assembly has a duplicate type key or "
            "an undeterminable chain order."
        ),
    )
