"""Default HTTP transport backed by Python platform networking.

The HTTP method mapper is the public surface of this module until later work
adds request mapping, response normalization, and the transport implementation.
"""

from mconet.transport.http_system.http_method import map_http_method

__all__: tuple[str, ...] = ("map_http_method",)
