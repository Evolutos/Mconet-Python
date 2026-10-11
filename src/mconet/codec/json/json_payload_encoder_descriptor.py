"""Diagnostic metadata for the JSON payload encoder."""

from __future__ import annotations

from mconet.codec.json.json_payload_encoder_type_contract import (
    JSON_PAYLOAD_ENCODER_TYPE_CONTRACT,
)
from mconet.core.spi.component_descriptor import ComponentDescriptor

_ENCODER_NAME = "json-payload-encoder"
_ENCODER_VERSION = "1.0.0"

# Builtin provenance records that the SDK owns this encoder. The capability set
# stays unset until its own metadata work item and is not inferred from the name.
JSON_PAYLOAD_ENCODER_DESCRIPTOR = ComponentDescriptor(
    _ENCODER_NAME,
    _ENCODER_VERSION,
    "builtin",
    JSON_PAYLOAD_ENCODER_TYPE_CONTRACT,
)
"""Shared diagnostic metadata for every JSON payload encoder.

Name, version, and source are stable labels for diagnostics and monitoring.
They are not component identifiers and are not selection keys. The type
contract declares how a JSON payload connects to a transport body. The
capability set stays unset until its own metadata work item.
"""
