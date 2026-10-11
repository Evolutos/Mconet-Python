"""Secret-scanner contract for authorization headers, snapshots, and failures."""

import asyncio
import pickle
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.auth.basic.api_key_header_authorization import ApiKeyHeaderAuthorization
from mconet.auth.basic.api_key_header_authorization_handler import (
    ApiKeyHeaderAuthorizationHandler,
)
from mconet.auth.basic.bearer_authorization import BearerAuthorization
from mconet.auth.basic.bearer_authorization_handler import BearerAuthorizationHandler
from mconet.auth.basic.fixed_credential_source import FixedCredentialSource
from mconet.auth.basic.no_authorization_handler import NoAuthorizationHandler
from mconet.core.domain import (
    Bytes,
    Extensions,
    HeaderField,
    Headers,
    MediaType,
    ModelDescriptor,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    SecretValue,
    Timestamp,
    UriValue,
)
from mconet.core.runtime.default_authorization_handler_resolver import (
    DefaultAuthorizationHandlerResolver,
)
from mconet.core.runtime.post_authorization_monitor import request_view_for_monitor
from mconet.core.runtime.pre_authorization_snapshot import (
    snapshot_pre_authorization_request,
)
from mconet.core.spi import (
    AuthorizationContext,
    BodySigningMode,
    BodySigningRequirement,
    MutableTransportRequest,
    TransportBody,
    TransportRequest,
)
from mconet.testing import SecretContractSuite

_API_KEY = "mconet-test-api-key-not-secret"
_BEARER = "mconet-test-bearer-token-not-secret"


def _empty_extensions() -> Extensions:
    """Create independent extension storage for one target fixture."""
    return {}


@dataclass(frozen=True, slots=True)
class _Target:
    """Complete structural model target for one authorization context."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


def _context(mode: BodySigningMode = "none") -> AuthorizationContext:
    """Build non-sensitive facts for one authorization attempt."""
    return AuthorizationContext(
        interaction_id="interaction-1",
        target=cast(
            ModelTarget,
            _Target(
                OpenIdentifier("service.example"),
                OpenIdentifier("protocol.example"),
                NamedModel("model-example"),
            ),
        ),
        endpoint=UriValue("https://models.example.test/v1", True),
        transport_kind=OpenIdentifier("http"),
        timestamp=Timestamp(1_800_000_000, 0),
        body_signing_mode=mode,
    )


def _open_request() -> MutableTransportRequest:
    """Build one encoded request that already carries both credential headers."""
    return MutableTransportRequest(
        method="POST",
        url=UriValue("https://models.example.test/v1/run", True),
        headers=Headers(
            (
                HeaderField("X-Trace", "trace-value"),
                HeaderField("Authorization", f"Bearer {_BEARER}"),
                HeaderField("X-Api-Key", _API_KEY),
            )
        ),
        query=QueryParameters(),
        body=TransportBody(
            Bytes(b'{"input":"hello"}'),
            MediaType("application", "json"),
        ),
    )


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one callable and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the authorization operation to fail.")


def test_authorization_observations_do_not_disclose_credentials() -> None:
    """Verify headers, snapshots, monitors, exceptions, and logs omit secrets."""
    suite = SecretContractSuite()
    api_source = FixedCredentialSource(SecretValue(_API_KEY))
    bearer_source = FixedCredentialSource(SecretValue(_BEARER))
    api_key = ApiKeyHeaderAuthorization("X-Api-Key", "Key ", api_source)
    bearer = BearerAuthorization(bearer_source)
    request = _open_request()

    snapshot = snapshot_pre_authorization_request(request, api_key)
    authorized = TransportRequest(
        method=request.method,
        url=request.url,
        headers=Headers(
            (
                HeaderField("X-Trace", "trace-value"),
                HeaderField("Authorization", f"Bearer {_BEARER}"),
                HeaderField("X-Api-Key", f"Key {_API_KEY}"),
            )
        ),
        query=request.query,
        body=request.body,
    )
    monitor_view = request_view_for_monitor(authorized, api_key)

    # The wire header carries the credential. Every observation derived from it
    # for diagnostics must not.
    suite.assert_snapshot_safe(_API_KEY, snapshot)
    suite.assert_snapshot_safe(_BEARER, snapshot)
    suite.assert_snapshot_safe(_API_KEY, snapshot.headers)
    suite.assert_snapshot_safe(_API_KEY, monitor_view)
    suite.assert_snapshot_safe(_BEARER, monitor_view)
    suite.assert_snapshot_safe(_BEARER, monitor_view.headers)

    suite.assert_log_safe(
        _API_KEY,
        repr(api_key),
        repr(api_source),
        repr(ApiKeyHeaderAuthorizationHandler()),
        str(snapshot),
        str(monitor_view),
    )
    suite.assert_log_safe(
        _BEARER,
        repr(bearer),
        repr(bearer_source),
        repr(BearerAuthorizationHandler()),
        str(snapshot),
        str(monitor_view),
    )

    name_error = _capture(
        lambda: asyncio.run(
            ApiKeyHeaderAuthorizationHandler().apply(
                ApiKeyHeaderAuthorization("X:Api-Key", "", api_source),
                _context(),
                _open_request(),
            )
        )
    )
    value_error = _capture(
        lambda: asyncio.run(
            ApiKeyHeaderAuthorizationHandler().apply(
                ApiKeyHeaderAuthorization(
                    "X-Api-Key",
                    "",
                    FixedCredentialSource(SecretValue(f"{_API_KEY}\n")),
                ),
                _context(),
                _open_request(),
            )
        )
    )
    signing_error = _capture(
        lambda: asyncio.run(
            BearerAuthorizationHandler().apply(
                bearer,
                _context("unsigned_payload"),
                _open_request(),
            )
        )
    )
    resolution_error = _capture(
        lambda: DefaultAuthorizationHandlerResolver().resolve(
            api_key,
            BodySigningRequirement(),
            (NoAuthorizationHandler(),),
        )
    )
    suite.assert_exception_safe(_API_KEY, name_error)
    suite.assert_exception_safe(_API_KEY, value_error)
    suite.assert_exception_safe(_BEARER, signing_error)
    suite.assert_exception_safe(_API_KEY, resolution_error)

    serialization_error = _capture(lambda: pickle.dumps(api_source))
    suite.assert_exception_safe(_API_KEY, serialization_error)
    suite.assert_serialization_safe(_API_KEY, str(serialization_error))
