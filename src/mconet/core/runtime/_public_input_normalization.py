"""Runtime scheduling for the single public model-request input."""

from __future__ import annotations

from mconet.core.domain.model_request import ModelRequest
from mconet.core.domain.model_request_validation import validate_model_request


def normalize_public_input(request: ModelRequest) -> ModelRequest:
    """Return the one validated model request for an interaction.

    Every public entry reaches the runtime as one ``ModelRequest``. This
    function is that entry's only normalization step. It asks the domain
    validator to accept the request and then returns that same object. It does
    not build a replacement request, merge client configuration, resolve
    components or service access, or perform I/O.

    R1 has no public ``RequestNormalizer`` chain. Text and builder convenience
    APIs become a ``ModelRequest`` before they reach this function, so this
    step does not accept strings, builders, or a second request shape.

    Args:
        request: The public model request supplied for one interaction.

    Returns:
        The same request object after domain validation succeeds.

    Raises:
        TypeError: If the request surface or a nested value has an invalid type.
        ValueError: If target, task, access, or JSON semantics are invalid.
        ModelInteractionError: If a known task exceeds its supported scope.
    """
    # The validator returns its input unchanged. Using that object as the only
    # result keeps target, task, access, metadata, and extensions on one
    # identity for every later runtime stage.
    normalized = validate_model_request(request)
    return normalized
