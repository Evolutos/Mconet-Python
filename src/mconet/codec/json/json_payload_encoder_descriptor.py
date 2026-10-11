"""Diagnostic metadata for the JSON payload encoder."""

from __future__ import annotations

from mconet.core.spi.component_descriptor import ComponentDescriptor

_ENCODER_NAME = "json-payload-encoder"
_ENCODER_VERSION = "1.0.0"

# Builtin provenance records that the SDK owns this encoder. The omitted type
# contract and capability set are separate metadata work and are not inferred
# from the diagnostic name.
JSON_PAYLOAD_ENCODER_DESCRIPTOR = ComponentDescriptor(
    _ENCODER_NAME,
    _ENCODER_VERSION,
    "builtin",
)
"""Shared diagnostic metadata for every JSON payload encoder.

Name, version, and source are stable labels for diagnostics and monitoring.
They are not component identifiers and are not selection keys. The type
contract and capability set stay unset until their own metadata work items.
"""
