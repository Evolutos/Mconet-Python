"""Type-contract tests for read-only Extensions mappings."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import assert_type, get_args, get_origin

from mconet.core.domain import Extensions, JsonValue


def _accept_extensions(value: Extensions) -> Extensions:
    """Expose the alias boundary to Pyright contract checks."""
    return value


def test_extensions_accept_read_only_recursive_json_mapping() -> None:
    """Verify extension values support nested JSON through a read-only view."""
    values: dict[str, JsonValue] = {
        "vendor.enabled": True,
        "vendor.options": {"modes": ["fast", "safe"]},
    }
    extensions: Extensions = MappingProxyType(values)

    assert_type(_accept_extensions(extensions), Extensions)
    assert _accept_extensions(extensions) is extensions
    assert extensions["vendor.options"] == {"modes": ["fast", "safe"]}
    assert not hasattr(extensions, "__setitem__")


def test_extensions_fix_string_keys_and_json_values() -> None:
    """Verify the public alias has the exact key and value type arguments."""
    key_type, value_type = get_args(Extensions)

    assert get_origin(Extensions) is Mapping
    assert key_type is str
    assert value_type == JsonValue
