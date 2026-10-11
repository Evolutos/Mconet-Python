"""Diagnostic metadata for the JSON error payload decoder."""

from __future__ import annotations

from mconet.core.spi.component_descriptor import ComponentDescriptor

_DECODER_NAME = "json-error-payload-decoder"
_DECODER_VERSION = "1.0.0"

# Builtin provenance records that the SDK owns this error decoder. The type
# contract and capability set stay unset until their own metadata work items
# and are not inferred from the diagnostic name.
JSON_ERROR_PAYLOAD_DECODER_DESCRIPTOR = ComponentDescriptor(
    _DECODER_NAME,
    _DECODER_VERSION,
    "builtin",
)
"""Shared diagnostic metadata for every JSON error payload decoder.

Name, version, and source are stable labels for diagnostics and monitoring.
They are not component identifiers and are not selection keys. This object is
distinct from the success-decoder descriptor. The type contract and capability
set stay unset until their own metadata work items.
"""
