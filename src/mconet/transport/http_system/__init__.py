"""Default HTTP transport backed by Python platform networking.

The HTTP request mappers, response media-type extraction, response header
summary, caller-cancellation bridge, and deadline gate are the public
surface of this module until later work adds the transport implementation.
"""

from mconet.transport.http_system.http_body import map_http_body
from mconet.transport.http_system.http_cancellation import HttpCancellationBridge
from mconet.transport.http_system.http_content_length import apply_http_content_length
from mconet.transport.http_system.http_content_type import apply_http_content_type
from mconet.transport.http_system.http_deadline import ensure_http_deadline
from mconet.transport.http_system.http_default_header import apply_default_http_headers
from mconet.transport.http_system.http_header import HttpHeaderField, map_http_headers
from mconet.transport.http_system.http_method import map_http_method
from mconet.transport.http_system.http_query import map_http_query
from mconet.transport.http_system.http_response_header_summary import (
    summarize_http_response_headers,
)
from mconet.transport.http_system.http_response_media_type import (
    extract_http_response_media_type,
)
from mconet.transport.http_system.http_status import HttpStatusOutcome, map_http_status
from mconet.transport.http_system.http_url import HttpBaseUrl, map_http_url

__all__: tuple[str, ...] = (
    "HttpBaseUrl",
    "HttpCancellationBridge",
    "HttpHeaderField",
    "HttpStatusOutcome",
    "apply_default_http_headers",
    "apply_http_content_length",
    "apply_http_content_type",
    "ensure_http_deadline",
    "extract_http_response_media_type",
    "map_http_body",
    "map_http_headers",
    "map_http_method",
    "map_http_query",
    "map_http_status",
    "map_http_url",
    "summarize_http_response_headers",
)
