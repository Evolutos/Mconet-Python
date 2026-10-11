"""Tests for default authorization handler resolution."""

from mconet.auth.basic.api_key_header_authorization import ApiKeyHeaderAuthorization
from mconet.auth.basic.dynamic_credential_source import DynamicCredentialSource
from mconet.auth.basic.no_authorization import NoAuthorization
from mconet.auth.basic.no_authorization_handler import NoAuthorizationHandler
from mconet.core.domain import (
    Authorization,
    ModelInteractionError,
    SecretValue,
)
from mconet.core.runtime.default_authorization_handler_resolver import (
    DefaultAuthorizationHandlerResolver,
)
from mconet.core.spi import (
    AuthorizationContext,
    AuthorizationHandler,
    AuthorizationHandlerResolver,
    BodySigningMode,
    BodySigningRequirement,
    ComponentDescriptor,
    MutableTransportRequest,
)
from mconet.testing import AuthorizationHandlerResolverContractSuite

_PLACEHOLDER = "mconet-test-api-key-not-secret"


class _RecordingHandler:
    """Candidate that records compatibility checks and never applies them."""

    def __init__(self, supported: frozenset[BodySigningMode]) -> None:
        """Retain the modes this fixture reports as compatible."""
        self.descriptor = ComponentDescriptor(
            "recording-handler",
            "1.0.0",
            "application",
        )
        self._supported = supported
        self.support_calls = 0
        self.apply_calls = 0

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Count one compatibility check and return the configured modes."""
        del authorization, body_signing_requirement
        self.support_calls += 1
        return self._supported

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Count an application that resolution must not perform."""
        del authorization, context, request
        self.apply_calls += 1


def _assert_unsupported(error: BaseException) -> None:
    """Require the stable no-match failure without caller-controlled text."""
    assert isinstance(error, ModelInteractionError)
    assert error.code == "unsupported_authorization"
    assert error.message == "No authorization handler supports this decision."
    assert str(error.category.id) == "authentication"
    assert str(error.phase.id) == "authorization_resolution"


def test_resolver_rejects_an_empty_candidate_tuple() -> None:
    """Verify no candidates produce the no-match failure."""
    resolver = DefaultAuthorizationHandlerResolver()

    AuthorizationHandlerResolverContractSuite(resolver).assert_no_match(
        NoAuthorization(),
        BodySigningRequirement(),
        (),
        assertion=_assert_unsupported,
    )
    assert isinstance(resolver, AuthorizationHandlerResolver)


def test_resolver_rejects_candidates_that_do_not_support_the_decision() -> None:
    """Verify every candidate is checked and credentials stay unread."""
    calls: list[str] = []

    async def provider(_context: AuthorizationContext) -> SecretValue:
        calls.append("resolved")
        return SecretValue(_PLACEHOLDER)

    authorization = ApiKeyHeaderAuthorization(
        "X-Api-Key",
        "",
        DynamicCredentialSource(provider),
    )
    first = _RecordingHandler(frozenset())
    second = _RecordingHandler(frozenset())
    handlers: tuple[AuthorizationHandler, ...] = (
        first,
        NoAuthorizationHandler(),
        second,
    )

    AuthorizationHandlerResolverContractSuite(
        DefaultAuthorizationHandlerResolver()
    ).assert_no_match(
        authorization,
        BodySigningRequirement(),
        handlers,
        assertion=_assert_unsupported,
    )

    assert calls == []
    assert first.support_calls == 1
    assert second.support_calls == 1
    assert first.apply_calls == 0
    assert second.apply_calls == 0


def test_resolver_rejects_a_handler_that_supports_only_another_signing_mode() -> None:
    """Verify a mode outside the requirement is not a match."""
    handler = _RecordingHandler(frozenset(("unsigned_payload",)))

    AuthorizationHandlerResolverContractSuite(
        DefaultAuthorizationHandlerResolver()
    ).assert_no_match(
        NoAuthorization(),
        BodySigningRequirement(),
        (handler,),
        assertion=_assert_unsupported,
    )
    assert handler.apply_calls == 0
