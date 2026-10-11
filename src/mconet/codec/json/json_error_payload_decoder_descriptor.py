"""Diagnostic metadata for the JSON error payload decoder."""

from __future__ import annotations

from mconet.codec.json.json_error_payload_decoder_type_contract import (
    JSON_ERROR_PAYLOAD_DECODER_TYPE_CONTRACT,
)
from mconet.core.spi.component_descriptor import ComponentDescriptor

_DECODER_NAME = "json-error-payload-decoder"
_DECODER_VERSION = "1.0.0"

# Builtin provenance records that the SDK owns this error decoder. The
# capability set stays empty so capability resolution cannot treat this decoder
# as the JSON encoder. The type contract is the error payload output.
JSON_ERROR_PAYLOAD_DECODER_DESCRIPTOR = ComponentDescriptor(
    _DECODER_NAME,
    _DECODER_VERSION,
    "builtin",
    JSON_ERROR_PAYLOAD_DECODER_TYPE_CONTRACT,
)
"""Shared diagnostic metadata for every JSON error payload decoder.

Name, version, and source are stable labels for diagnostics and monitoring.
They are not component identifiers and are not selection keys. This object is
distinct from the success-decoder descriptor. The type contract is the error
payload output. The capability set stays empty.
"""
