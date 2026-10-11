"""Type contract for a decoded JSON success payload."""

from __future__ import annotations

from mconet.core.domain import MediaType, OpenIdentifier
from mconet.core.spi.component_type_contract import ComponentTypeContract
from mconet.core.spi.component_type_port import ComponentTypePort

_JSON_VALUE_TYPE_ID = OpenIdentifier("json.value")
_JSON_MEDIA_TYPE = MediaType("application", "json")

# The decoder consumes response bytes, so there is no input port. Schema
# identity is omitted so a consumer can accept the payload without adopting a
# protocol schema. This object stays independent from the error-decoder contract.
JSON_SUCCESS_PAYLOAD_DECODER_TYPE_CONTRACT = ComponentTypeContract(
    outputs=(
        ComponentTypePort(
            "output",
            _JSON_VALUE_TYPE_ID,
            None,
            _JSON_MEDIA_TYPE,
        ),
    ),
)
"""Output port for the JSON success payload decoder.

The port carries ``json.value`` as parameter-free ``application/json`` and
does not require a schema id. Response bytes are not a JSON port, so this
contract declares no input.
"""
