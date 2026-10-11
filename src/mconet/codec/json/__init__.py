"""R1 JSON codec contracts.

The frozen payload envelope, UTF-8 text utility, JSON payload encoder, bounded
body collector, and success payload decoder are the public surface of this
module until later work packages add error decoding and component metadata.
"""

from mconet.codec.json.collect_bounded_bytes import collect_bounded_bytes
from mconet.codec.json.json_payload import JsonPayload
from mconet.codec.json.json_payload_encoder import JsonPayloadEncoder
from mconet.codec.json.json_success_payload_decoder import (
    JsonSuccessPayloadDecoder,
)
from mconet.codec.json.utf8 import encode_utf8

__all__: tuple[str, ...] = (
    "JsonPayload",
    "JsonPayloadEncoder",
    "JsonSuccessPayloadDecoder",
    "collect_bounded_bytes",
    "encode_utf8",
)
