"""Type contract connecting a JSON adapter payload to a transport body."""

from __future__ import annotations

from mconet.core.domain import MediaType, OpenIdentifier
from mconet.core.spi.component_type_contract import ComponentTypeContract
from mconet.core.spi.component_type_port import ComponentTypePort

_JSON_VALUE_TYPE_ID = OpenIdentifier("json.value")
_TRANSPORT_BODY_TYPE_ID = OpenIdentifier("transport.body")
_JSON_MEDIA_TYPE = MediaType("application", "json")

# The input accepts any JSON payload schema. An omitted schema id lets an
# adapter keep its own schema and still connect. The output is transport bytes
# with the same JSON media type, not another JSON value.
JSON_PAYLOAD_ENCODER_TYPE_CONTRACT = ComponentTypeContract(
    inputs=(
        ComponentTypePort(
            "input",
            _JSON_VALUE_TYPE_ID,
            None,
            _JSON_MEDIA_TYPE,
        ),
    ),
    outputs=(
        ComponentTypePort(
            "output",
            _TRANSPORT_BODY_TYPE_ID,
            None,
            _JSON_MEDIA_TYPE,
        ),
    ),
)
"""Input and output ports for the JSON payload encoder.

The input port carries ``json.value`` as ``application/json``. It does not
require a schema id, so an adapter payload with its own schema can connect.
The output port carries ``transport.body`` with that same media type.
"""
