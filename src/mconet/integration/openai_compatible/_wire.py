"""Shared reading rules for decoded OpenAI-compatible wire values."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import cast

from mconet.core.domain import (
    ErrorCategory,
    Extensions,
    InteractionPhase,
    JsonValue,
    ModelInteractionError,
    OpenIdentifier,
    validate_json_value_numbers,
)

INVALID_PROTOCOL_RESPONSE_CODE = "invalid_protocol_response"
"""Stable code for a decoded payload that violates the frozen wire shape."""

_PROTOCOL_CATEGORY = ErrorCategory(OpenIdentifier("protocol"))
_RESPONSE_PARSING_PHASE = InteractionPhase(OpenIdentifier("response_parsing"))
_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})


def invalid_protocol_response(path: str, expectation: str) -> ModelInteractionError:
    """Create the normalized failure for one wire field that has the wrong shape.

    Args:
        path: JSON Pointer of the offending field. The root is ``""``.
        expectation: Short statement of the frozen wire rule that failed.

    Returns:
        A protocol error whose message names the location but never the value.
    """
    # Only the location and rule enter the message. Service text can echo
    # request content, so the observed value is never copied.
    location = path or "/"
    return ModelInteractionError(
        category=_PROTOCOL_CATEGORY,
        phase=_RESPONSE_PARSING_PHASE,
        code=INVALID_PROTOCOL_RESPONSE_CODE,
        message=f"OpenAI-compatible response field {location} {expectation}.",
    )


def child_path(path: str, name: str | int) -> str:
    """Append one object member or array index to a JSON Pointer."""
    # RFC 6901 escaping keeps member names containing "/" or "~" unambiguous.
    token = str(name).replace("~", "~0").replace("/", "~1")
    return f"{path}/{token}"


def require_object(value: JsonValue | None, path: str) -> dict[str, JsonValue]:
    """Return a decoded JSON object or reject any other JSON kind."""
    if not isinstance(value, dict):
        raise invalid_protocol_response(path, "must be an object")
    return value


def require_string(document: dict[str, JsonValue], name: str, path: str) -> str:
    """Return one required, non-null string member."""
    # A missing member and an explicit null both fail: the frozen profile marks
    # these fields required and not nullable.
    value = document.get(name)
    if not isinstance(value, str):
        raise invalid_protocol_response(child_path(path, name), "must be a string")
    return value


def require_count(document: dict[str, JsonValue], name: str, path: str) -> int:
    """Return one required, non-null, non-negative integer member."""
    # bool is an int subclass but a different JSON kind, so exact type checks
    # keep true and false from passing as a count or index.
    value = document.get(name)
    if type(value) is not int or value < 0:
        raise invalid_protocol_response(
            child_path(path, name), "must be a non-negative integer"
        )
    return value


def optional_count(document: dict[str, JsonValue], name: str, path: str) -> int | None:
    """Return one optional non-negative integer member, or None when absent."""
    # Absence is allowed, but an explicit null is not: the frozen profile marks
    # these members optional and not nullable.
    if name not in document:
        return None
    return require_count(document, name, path)


def unknown_members(
    document: dict[str, JsonValue],
    known: frozenset[str],
) -> Extensions:
    """Capture members outside the frozen shape as a read-only snapshot.

    The response profile ignores unknown members after capture, so they are
    preserved here and never interpreted.
    """
    # Keep the original member order so later observers see the service order.
    captured = {name: value for name, value in document.items() if name not in known}
    if not captured:
        return _EMPTY_EXTENSIONS
    return MappingProxyType(captured)


def snapshot_extensions(value: object, owner: str) -> Extensions:
    """Validate and freeze string-keyed portable JSON extension members."""
    if not isinstance(value, Mapping):
        raise TypeError(f"{owner} extensions must be a mapping.")
    source = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(f"{owner} extensions keys must be strings.")

    # Extensions travel into domain results, so every member must already be
    # portable JSON rather than an arbitrary Python object.
    typed = cast(Mapping[str, JsonValue], source)
    for member in typed.values():
        validate_json_value_numbers(member)
    if not typed:
        return _EMPTY_EXTENSIONS
    return MappingProxyType(dict(typed))
