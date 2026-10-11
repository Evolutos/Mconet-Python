"""R1 JSON codec contracts.

The frozen payload envelope, UTF-8 text utility, JSON payload encoder and its
descriptor, type contract, and encode capability, bounded body collector,
success payload decoder and its diagnostic descriptor, error payload
decoder, and JSON media-type matcher are the public surface of this module
until later work packages add the remaining decoder metadata.
"""

from mconet.codec.json.collect_bounded_bytes import collect_bounded_bytes
from mconet.codec.json.json_error_payload_decoder import JsonErrorPayloadDecoder
from mconet.codec.json.json_media_type import is_json_media_type
from mconet.codec.json.json_payload import JsonPayload
from mconet.codec.json.json_payload_encoder import JsonPayloadEncoder
from mconet.codec.json.json_payload_encoder_descriptor import (
    JSON_PAYLOAD_ENCODER_CAPABILITY,
    JSON_PAYLOAD_ENCODER_DESCRIPTOR,
)
from mconet.codec.json.json_payload_encoder_type_contract import (
    JSON_PAYLOAD_ENCODER_TYPE_CONTRACT,
)
from mconet.codec.json.json_success_payload_decoder import (
    JsonSuccessPayloadDecoder,
)
from mconet.codec.json.json_success_payload_decoder_descriptor import (
    JSON_SUCCESS_PAYLOAD_DECODER_DESCRIPTOR,
)
from mconet.codec.json.utf8 import encode_utf8

__all__: tuple[str, ...] = (
    "JSON_PAYLOAD_ENCODER_CAPABILITY",
    "JSON_PAYLOAD_ENCODER_DESCRIPTOR",
    "JSON_PAYLOAD_ENCODER_TYPE_CONTRACT",
    "JSON_SUCCESS_PAYLOAD_DECODER_DESCRIPTOR",
    "JsonErrorPayloadDecoder",
    "JsonPayload",
    "JsonPayloadEncoder",
    "JsonSuccessPayloadDecoder",
    "collect_bounded_bytes",
    "encode_utf8",
    "is_json_media_type",
)
