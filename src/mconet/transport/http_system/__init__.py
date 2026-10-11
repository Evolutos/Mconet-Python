"""Default HTTP transport backed by Python platform networking.

The HTTP request mappers, response media-type extraction, response header
summary, caller-cancellation bridge, deadline gate, network-timeout
normalization, bounded response reading, connection release on an
oversized body, redirect header policy, and TLS verification rules are
the public surface of this module until later work adds proxy rules and the
transport implementation.
"""

from mconet.transport.http_system.http_body import map_http_body
from mconet.transport.http_system.http_cancellation import HttpCancellationBridge
from mconet.transport.http_system.http_content_length import apply_http_content_length
from mconet.transport.http_system.http_content_type import apply_http_content_type
from mconet.transport.http_system.http_deadline import ensure_http_deadline
from mconet.transport.http_system.http_default_header import apply_default_http_headers
from mconet.transport.http_system.http_header import HttpHeaderField, map_http_headers
from mconet.transport.http_system.http_method import map_http_method
from mconet.transport.http_system.http_network_timeout import (
    normalize_http_network_timeout,
)
from mconet.transport.http_system.http_query import map_http_query
from mconet.transport.http_system.http_redirect import headers_for_http_redirect
from mconet.transport.http_system.http_response_body import (
    read_bounded_http_response_body,
)
from mconet.transport.http_system.http_response_header_summary import (
    summarize_http_response_headers,
)
from mconet.transport.http_system.http_response_limit_release import (
    read_bounded_http_response_releasing_connection,
)
from mconet.transport.http_system.http_response_media_type import (
    extract_http_response_media_type,
)
from mconet.transport.http_system.http_status import HttpStatusOutcome, map_http_status
from mconet.transport.http_system.http_tls import HttpTlsPolicy, system_http_tls_policy
from mconet.transport.http_system.http_url import HttpBaseUrl, map_http_url

__all__: tuple[str, ...] = (
    "HttpBaseUrl",
    "HttpCancellationBridge",
    "HttpHeaderField",
    "HttpStatusOutcome",
    "HttpTlsPolicy",
    "apply_default_http_headers",
    "apply_http_content_length",
    "apply_http_content_type",
    "ensure_http_deadline",
    "extract_http_response_media_type",
    "headers_for_http_redirect",
    "map_http_body",
    "map_http_headers",
    "map_http_method",
    "map_http_query",
    "map_http_status",
    "map_http_url",
    "normalize_http_network_timeout",
    "read_bounded_http_response_body",
    "read_bounded_http_response_releasing_connection",
    "summarize_http_response_headers",
    "system_http_tls_policy",
)
