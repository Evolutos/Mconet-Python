"""Diagnostic metadata for the JSON payload encoder."""

from __future__ import annotations

from mconet.codec.json.json_payload_encoder_type_contract import (
    JSON_PAYLOAD_ENCODER_TYPE_CONTRACT,
)
from mconet.core.domain import OpenIdentifier
from mconet.core.spi.component_descriptor import ComponentDescriptor

_ENCODER_NAME = "json-payload-encoder"
_ENCODER_VERSION = "1.0.0"

# The capability id is the resolution key. The diagnostic name is not, so a
# caller cannot select or satisfy encoding by matching "json-payload-encoder".
JSON_PAYLOAD_ENCODER_CAPABILITY = OpenIdentifier("codec.json.encode")
"""Open capability id declaring that this component can encode JSON."""

JSON_PAYLOAD_ENCODER_DESCRIPTOR = ComponentDescriptor(
    _ENCODER_NAME,
    _ENCODER_VERSION,
    "builtin",
    JSON_PAYLOAD_ENCODER_TYPE_CONTRACT,
    frozenset((JSON_PAYLOAD_ENCODER_CAPABILITY,)),
)
"""Shared diagnostic metadata for every JSON payload encoder.

Name, version, and source are stable labels for diagnostics and monitoring.
They are not component identifiers and are not selection keys. The type
contract is the JSON input port that an adapter payload connects to. The
capability set contains only ``codec.json.encode``.
"""
