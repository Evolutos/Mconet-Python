"""R1 JSON codec contracts.

The frozen payload envelope and UTF-8 text utility are the public surface of
this module until later work packages add JSON encoding, decoding, and
component metadata.
"""

from mconet.codec.json.json_payload import JsonPayload
from mconet.codec.json.utf8 import encode_utf8

__all__: tuple[str, ...] = ("JsonPayload", "encode_utf8")
