"""One function tool a conversation may offer to the model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from mconet.core.domain.json_value import JsonValue


def function_tool_parameters_json(tool: FunctionTool) -> JsonValue | None:
    """Return a detached JSON object for one tool schema.

    The stored schema rejects later writes. This copy is the value an encoder
    or numeric validator can walk with the ordinary JSON containers.

    Args:
        tool: The function tool whose schema is read.

    Returns:
        A fresh JSON object, or ``None`` when the tool has no schema.
    """
    parameters = tool.parameters
    if parameters is None:
        return None
    return _thaw_json(parameters)


def _freeze_json(value: JsonValue) -> object:
    """Return a read-only, hashable snapshot of one JSON value."""
    # Objects and arrays are the only mutable JSON kinds. A proxy and a tuple
    # keep a later write from changing a tool that has already been stored.
    if isinstance(value, dict):
        frozen = {key: _freeze_json(item) for key, item in value.items()}
        return MappingProxyType(frozen)
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    # Strings, numbers, booleans, and null have no membership to mutate.
    return value


def _thaw_json(value: object) -> JsonValue:
    """Return a plain JSON copy of one frozen schema node."""
    # Encoders accept dict and list, not a read-only proxy or a tuple. The
    # copy is detached, so changing it does not change the stored tool.
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, object], value)
        thawed: dict[str, JsonValue] = {}
        for key, raw_item in mapping.items():
            thawed[key] = _thaw_json(raw_item)
        return thawed
    if isinstance(value, tuple):
        items = cast(tuple[object, ...], value)
        return [_thaw_json(item) for item in items]
    return cast(JsonValue, value)


def _canonical_json(value: object) -> object:
    """Return a hashable form whose equality follows JSON object contents."""
    # Object key order is not part of JSON equality. Sorting the pairs keeps
    # two schemas with the same members in a different order on one hash.
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, object], value)
        pairs = [(key, _canonical_json(raw_item)) for key, raw_item in mapping.items()]
        # Sort so two objects with the same members hash together.
        return tuple(sorted(pairs))
    if isinstance(value, tuple):
        items = cast(tuple[object, ...], value)
        return tuple(_canonical_json(item) for item in items)
    return value


@dataclass(frozen=True, slots=True)
class FunctionTool:
    """Describe one function the model may call.

    ``parameters`` is a JSON Schema object when the caller supplies one. The
    value stays protocol-neutral: an adapter decides how the tool is spelled
    on the wire. Construction checks storage shape only. Empty names, duplicate
    names, and schema numbers belong to generation-parameter validation.
    """

    name: str
    """Function name the model must use when it calls this tool."""

    description: str | None = None
    """Optional guidance shown to the model, kept exactly as supplied."""

    parameters: JsonValue | None = None
    """Optional JSON Schema object describing the function arguments."""

    def __post_init__(self) -> None:
        """Require a string name and a detached object schema."""
        name = cast(object, self.name)
        description = cast(object, self.description)
        parameters = cast(object, self.parameters)
        # Storage shape only. A blank or duplicate name is still stored so the
        # generation-parameter validator can report it as a value error.
        if not isinstance(name, str):
            raise TypeError("FunctionTool name must be a string.")
        # None offers the tool without guidance. A non-string cannot be shown
        # to the model as description text.
        if description is not None and not isinstance(description, str):
            raise TypeError("FunctionTool description must be a string or None.")
        # A schema is a JSON object. Arrays and scalars have no parameter
        # fields for the model to fill, so they are not stored as a schema.
        if parameters is not None and not isinstance(parameters, dict):
            raise TypeError("FunctionTool parameters must be a JSON object or None.")
        if isinstance(parameters, dict):
            schema = cast(dict[str, JsonValue], parameters)
            # Replace the caller's mapping with a read-only snapshot. A later
            # edit of the original object, or of a value read back from this
            # tool, must not change a request that already captured it.
            object.__setattr__(self, "parameters", _freeze_json(schema))

    def __hash__(self) -> int:
        """Return a hash of the name, description, and schema contents."""
        # The stored schema is a read-only proxy, which has no hash of its
        # own. The canonical pairs follow the same contents as equality.
        return hash((self.name, self.description, _canonical_json(self.parameters)))
