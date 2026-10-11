"""R1 JSON codec contracts.

The frozen payload envelope, UTF-8 text utility, and JSON payload encoder are
the public surface of this module until later work packages add decoding and
component metadata.
"""

from mconet.codec.json.json_payload import JsonPayload
from mconet.codec.json.json_payload_encoder import JsonPayloadEncoder
from mconet.codec.json.utf8 import encode_utf8

__all__: tuple[str, ...] = ("JsonPayload", "JsonPayloadEncoder", "encode_utf8")
