"""Single-interaction authorization window for transport request mutation."""

from __future__ import annotations

from mconet.core.domain import Headers, QueryParameters, UriValue
from mconet.core.spi.transport_body import TransportBody
from mconet.core.spi.transport_request import TransportRequest


class MutableTransportRequest:
    """Allow bounded authorization changes before producing a frozen request.

    The protocol-selected method is read-only. Authorization handlers may replace
    the final URL, headers, query parameters, or encoded body through explicit
    operations. :meth:`freeze` closes that window and returns one immutable
    :class:`TransportRequest`; no later authorization mutation is accepted.

    This builder is interaction-local mutable state. It intentionally has
    identity rather than value semantics and must never be retained by a client,
    exposed to monitors, or passed to a transport before freezing.
    """

    __slots__ = (
        "_body",
        "_frozen_request",
        "_headers",
        "_method",
        "_query",
        "_url",
    )

    _method: str
    _url: UriValue
    _headers: Headers
    _query: QueryParameters
    _body: TransportBody
    _frozen_request: TransportRequest | None

    def __init__(
        self,
        method: str,
        url: UriValue,
        headers: Headers,
        query: QueryParameters,
        body: TransportBody,
    ) -> None:
        """Create an open authorization window from transport-ready values.

        Args:
            method: Protocol method that authorization cannot replace.
            url: Final destination URI before authorization adjustments.
            headers: Ordered headers before authorization fields are applied.
            query: Ordered query parameters before authorization values are applied.
            body: Complete encoded body available to signing handlers.

        Raises:
            TypeError: If any input bypasses its established request value boundary.
        """
        # Validate the complete initial state before publishing any partially
        # initialized builder to an authorization handler.
        _validate_method(method)
        _validate_url(url)
        _validate_headers(headers)
        _validate_query(query)
        _validate_body(body)

        # Internal writes bypass the public assignment guard. The cached request
        # starts absent, which is the sole source of the open/frozen state.
        object.__setattr__(self, "_method", method)
        object.__setattr__(self, "_url", url)
        object.__setattr__(self, "_headers", headers)
        object.__setattr__(self, "_query", query)
        object.__setattr__(self, "_body", body)
        object.__setattr__(self, "_frozen_request", None)

    def __setattr__(self, name: str, value: object) -> None:
        """Reject direct field writes outside the bounded replacement methods."""
        # A single assignment guard prevents callers from changing private slots,
        # reopening a frozen builder, or bypassing nominal validation. Authorized
        # mutations use the explicit replace methods below.
        del name, value
        raise AttributeError(
            "MutableTransportRequest fields must be changed through replace methods."
        )

    @property
    def method(self) -> str:
        """Return the protocol-selected method, which authorization cannot change."""
        # The method participates in signing input but stays owned by the protocol
        # request mapping stage rather than the authorization handler.
        return self._method

    @property
    def url(self) -> UriValue:
        """Return the current final destination URI value."""
        # Query authorization may instead use QueryParameters, while signature
        # schemes that replace the entire final URI can use replace_url.
        return self._url

    @property
    def headers(self) -> Headers:
        """Return the current ordered request headers."""
        # Headers is itself immutable, so readers cannot mutate the authorization
        # window through the value returned by this property.
        return self._headers

    @property
    def query(self) -> QueryParameters:
        """Return the current ordered request query parameters."""
        # Repeated parameters and their ordering remain stable until an explicit
        # replacement supplies another validated immutable collection.
        return self._query

    @property
    def body(self) -> TransportBody:
        """Return the current encoded request body."""
        # Signing handlers may replace the whole immutable body representation;
        # they cannot mutate its byte storage through this property.
        return self._body

    @property
    def is_frozen(self) -> bool:
        """Return whether the authorization window has been permanently closed."""
        # The cached immutable request is both the frozen-state marker and the
        # value returned by every idempotent freeze call.
        return self._frozen_request is not None

    def replace_url(self, value: UriValue) -> None:
        """Replace the final destination URI while the authorization window is open."""
        # Check lifecycle before input shape so a closed window always reports the
        # state violation and never appears writable based on a supplied value.
        self._require_open()
        _validate_url(value)
        object.__setattr__(self, "_url", value)

    def replace_headers(self, value: Headers) -> None:
        """Replace all ordered headers while the authorization window is open."""
        # Handlers construct a new immutable Headers value, preserving explicit
        # replacement semantics without exposing an in-place mutable collection.
        self._require_open()
        _validate_headers(value)
        object.__setattr__(self, "_headers", value)

    def replace_query(self, value: QueryParameters) -> None:
        """Replace all query parameters while the authorization window is open."""
        # Whole-value replacement keeps duplicate membership and ordering under
        # the QueryParameters contract rather than a lossy mapping abstraction.
        self._require_open()
        _validate_query(value)
        object.__setattr__(self, "_query", value)

    def replace_body(self, value: TransportBody) -> None:
        """Replace the encoded body while the authorization window is open."""
        # Body-signing implementations replace the complete immutable body so its
        # bytes and representation media type cannot become partially inconsistent.
        self._require_open()
        _validate_body(value)
        object.__setattr__(self, "_body", value)

    def freeze(self) -> TransportRequest:
        """Close authorization and return the unique immutable request snapshot."""
        frozen_request = self._frozen_request
        if frozen_request is not None:
            # Freezing is idempotent: every consumer receives the same snapshot,
            # and repeated lifecycle orchestration cannot create divergent values.
            return frozen_request

        # TransportRequest performs the final nominal composition check before
        # the snapshot becomes the permanent frozen-state marker.
        frozen_request = TransportRequest(
            method=self._method,
            url=self._url,
            headers=self._headers,
            query=self._query,
            body=self._body,
        )
        object.__setattr__(self, "_frozen_request", frozen_request)
        return frozen_request

    def _require_open(self) -> None:
        """Reject an authorization mutation after the request has been frozen."""
        # Use one stable failure for every mutation path so handlers cannot
        # partially update a request based on which field they attempt first.
        if self._frozen_request is not None:
            raise RuntimeError("MutableTransportRequest is frozen.")


def _validate_method(value: object) -> None:
    """Require exact protocol method text without normalizing it."""
    # Concrete transports own method grammar; this boundary only prevents a
    # dynamically supplied non-string value from entering either request form.
    if not isinstance(value, str):
        raise TypeError("MutableTransportRequest method must be a string.")


def _validate_url(value: object) -> None:
    """Require the structured URI value used by immutable transport requests."""
    # Retain absolute/relative classification and exact URI text rather than
    # accepting a raw string that authorization could reinterpret inconsistently.
    if not isinstance(value, UriValue):
        raise TypeError("MutableTransportRequest url must be a UriValue.")


def _validate_headers(value: object) -> None:
    """Require the immutable ordered header collection."""
    # Header name and injection semantics are validated by their dedicated gate;
    # this builder preserves the nominal ordered collection boundary.
    if not isinstance(value, Headers):
        raise TypeError("MutableTransportRequest headers must be Headers.")


def _validate_query(value: object) -> None:
    """Require the immutable ordered query-parameter collection."""
    # Query serialization remains transport-owned; replacement only verifies the
    # value can preserve duplicate parameters and their declared order.
    if not isinstance(value, QueryParameters):
        raise TypeError("MutableTransportRequest query must be QueryParameters.")


def _validate_body(value: object) -> None:
    """Require the completed encoded transport body value."""
    # A raw bytes object lacks media-type and future body metadata boundaries, so
    # only the established TransportBody may enter the authorization window.
    if not isinstance(value, TransportBody):
        raise TypeError("MutableTransportRequest body must be a TransportBody.")
