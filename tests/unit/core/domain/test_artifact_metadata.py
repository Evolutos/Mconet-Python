"""Type-contract tests for read-only ArtifactMetadata mappings."""

from __future__ import annotations

import json
from collections.abc import Mapping
from types import MappingProxyType
from typing import assert_type, get_args, get_origin

from mconet.core.domain import ArtifactMetadata, JsonValue


def _accept_artifact_metadata(value: ArtifactMetadata) -> ArtifactMetadata:
    """Expose the metadata alias boundary to strict static type checks."""
    # Returning the same read-only view proves the contract describes data and
    # does not copy, mutate, validate, fetch, or otherwise execute behavior.
    return value


def test_artifact_metadata_accepts_read_only_recursive_json_data() -> None:
    """Verify nested portable data remains observable through a read-only view."""
    values: dict[str, JsonValue] = {
        "source": "camera-7",
        "dimensions": {"width": 640, "height": 480},
        "labels": ["depth", "calibrated"],
        "verified": True,
    }
    metadata: ArtifactMetadata = MappingProxyType(values)

    # Static and runtime checks jointly prove the alias accepts recursive JSON
    # while exposing no item-assignment operation to consumers.
    assert_type(_accept_artifact_metadata(metadata), ArtifactMetadata)
    assert _accept_artifact_metadata(metadata) is metadata
    assert metadata["dimensions"] == {"width": 640, "height": 480}
    assert not hasattr(metadata, "__setitem__")


def test_artifact_metadata_round_trips_as_plain_json_data() -> None:
    """Verify metadata needs no executable object encoding to cross platforms."""
    metadata: ArtifactMetadata = MappingProxyType(
        {
            "producer": "sensor-array",
            "calibration": {"version": 3, "offsets": [0.25, -0.5]},
            "optional": None,
        }
    )

    # Convert only the read-only outer view for the standard JSON encoder; all
    # values remain native JsonValue data with no custom serialization hooks.
    encoded = json.dumps(dict(metadata), sort_keys=True)
    decoded: JsonValue = json.loads(encoded)

    assert decoded == dict(metadata)
    assert json.dumps(decoded, sort_keys=True) == encoded


def test_artifact_metadata_fixes_string_keys_and_json_values() -> None:
    """Verify the public alias cannot admit arbitrary keys or runtime objects."""
    key_type, value_type = get_args(ArtifactMetadata)

    # Alias introspection makes the no-behavior data boundary explicit: the
    # surface is exactly a Mapping whose values use the shared JSON union.
    assert get_origin(ArtifactMetadata) is Mapping
    assert key_type is str
    assert value_type == JsonValue
