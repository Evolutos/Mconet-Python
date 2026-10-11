"""R1 JSON codec contracts.

The frozen payload envelope is the only public surface of this module until
later work packages add encoding, decoding, and component metadata.
"""

from mconet.codec.json.json_payload import JsonPayload

__all__: tuple[str, ...] = ("JsonPayload",)
