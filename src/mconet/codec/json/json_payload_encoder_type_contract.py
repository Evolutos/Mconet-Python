"""Type contract connecting a JSON adapter payload to the encoder."""

from __future__ import annotations

from mconet.core.domain import MediaType, OpenIdentifier
from mconet.core.spi.component_type_contract import ComponentTypeContract
from mconet.core.spi.component_type_port import ComponentTypePort

_JSON_VALUE_TYPE_ID = OpenIdentifier("json.value")
_JSON_MEDIA_TYPE = MediaType("application", "json")

# Schema identity is omitted so an adapter can keep its own schema and still
# connect. There is no output port: encode returns transport bytes, which are
# not another JSON value.
JSON_PAYLOAD_ENCODER_TYPE_CONTRACT = ComponentTypeContract(
    inputs=(
        ComponentTypePort(
            "input",
            _JSON_VALUE_TYPE_ID,
            None,
            _JSON_MEDIA_TYPE,
        ),
    ),
)
"""Input port for the JSON payload encoder.

The port carries ``json.value`` as parameter-free ``application/json``. It
does not require a schema id. The encoder result is a transport body, so this
contract declares no output port.
"""
