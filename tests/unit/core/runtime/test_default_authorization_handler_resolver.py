"""Tests for default authorization handler resolution."""

from mconet.auth.basic.api_key_header_authorization import ApiKeyHeaderAuthorization
from mconet.auth.basic.api_key_header_authorization_handler import (
    ApiKeyHeaderAuthorizationHandler,
)
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
    ResolvedAuthorizationHandler,
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


def test_resolver_returns_the_only_matching_handler_in_any_position() -> None:
    """Verify the unique instance is returned wherever it sits in the tuple."""
    selected = NoAuthorizationHandler()
    before = _RecordingHandler(frozenset())
    after = _RecordingHandler(frozenset())
    orders = (
        (selected, before, after),
        (before, selected, after),
        (before, after, selected),
    )

    for handlers in orders:

        def assert_selected(actual: ResolvedAuthorizationHandler) -> None:
            """Require this loop's selected instance and the unsigned mode."""
            assert actual.handler is selected
            assert actual.body_signing_mode == "none"

        AuthorizationHandlerResolverContractSuite(
            DefaultAuthorizationHandlerResolver()
        ).assert_unique_match(
            NoAuthorization(),
            BodySigningRequirement(),
            handlers,
            assertion=assert_selected,
        )

    assert before.support_calls == 3
    assert after.support_calls == 3
    assert before.apply_calls == 0
    assert after.apply_calls == 0


def test_resolver_returns_the_api_key_handler_without_reading_the_key() -> None:
    """Verify the matching API key handler is selected before any credential read."""
    calls: list[str] = []

    async def provider(_context: AuthorizationContext) -> SecretValue:
        calls.append("resolved")
        return SecretValue(_PLACEHOLDER)

    selected = ApiKeyHeaderAuthorizationHandler()
    authorization = ApiKeyHeaderAuthorization(
        "X-Api-Key",
        "",
        DynamicCredentialSource(provider),
    )

    def assert_selected(actual: ResolvedAuthorizationHandler) -> None:
        """Require the API key handler instance and the unsigned mode."""
        assert actual.handler is selected
        assert actual.body_signing_mode == "none"

    AuthorizationHandlerResolverContractSuite(
        DefaultAuthorizationHandlerResolver()
    ).assert_unique_match(
        authorization,
        BodySigningRequirement(),
        (NoAuthorizationHandler(), selected),
        assertion=assert_selected,
    )
    assert calls == []


def test_resolver_selects_the_requirement_preferred_shared_mode() -> None:
    """Verify one handler uses requirement order rather than its own set order."""
    handler = _RecordingHandler(
        frozenset(("unsigned_payload", "precomputed_digest")),
    )
    preferred_first = BodySigningRequirement(
        required=True,
        acceptable_modes=("precomputed_digest", "unsigned_payload"),
    )
    preferred_second = BodySigningRequirement(
        required=True,
        acceptable_modes=("unsigned_payload", "precomputed_digest"),
    )

    def assert_precomputed(actual: ResolvedAuthorizationHandler) -> None:
        """Require the mode listed first by the requirement."""
        assert actual.handler is handler
        assert actual.body_signing_mode == "precomputed_digest"

    def assert_unsigned(actual: ResolvedAuthorizationHandler) -> None:
        """Require the other shared mode when the requirement lists it first."""
        assert actual.handler is handler
        assert actual.body_signing_mode == "unsigned_payload"

    suite = AuthorizationHandlerResolverContractSuite(
        DefaultAuthorizationHandlerResolver()
    )
    suite.assert_unique_match(
        NoAuthorization(),
        preferred_first,
        (handler,),
        assertion=assert_precomputed,
    )
    suite.assert_unique_match(
        NoAuthorization(),
        preferred_second,
        (handler,),
        assertion=assert_unsigned,
    )
    assert handler.apply_calls == 0


def _assert_ambiguous(error: BaseException) -> None:
    """Require the stable multiple-match failure without handler names."""
    assert isinstance(error, ModelInteractionError)
    assert error.code == "ambiguous_authorization_handler"
    assert error.message == (
        "More than one authorization handler supports this decision."
    )
    assert str(error.category.id) == "authentication"
    assert str(error.phase.id) == "authorization_resolution"


def test_resolver_rejects_two_handlers_for_the_same_decision() -> None:
    """Verify two compatible handlers fail instead of using tuple order."""
    first = NoAuthorizationHandler()
    second = NoAuthorizationHandler()
    ignored = _RecordingHandler(frozenset())
    orders = (
        (first, second),
        (second, first),
        (ignored, first, second),
        (first, ignored, second),
    )

    for handlers in orders:
        AuthorizationHandlerResolverContractSuite(
            DefaultAuthorizationHandlerResolver()
        ).assert_ambiguous_match(
            NoAuthorization(),
            BodySigningRequirement(),
            handlers,
            assertion=_assert_ambiguous,
        )

    assert ignored.apply_calls == 0


def test_resolver_rejects_handlers_that_support_different_accepted_modes() -> None:
    """Verify distinct modes do not choose one of two compatible handlers."""
    digest = _RecordingHandler(frozenset(("precomputed_digest",)))
    unsigned = _RecordingHandler(frozenset(("unsigned_payload",)))
    requirement = BodySigningRequirement(
        required=True,
        acceptable_modes=("precomputed_digest", "unsigned_payload"),
    )
    orders = ((digest, unsigned), (unsigned, digest))

    for handlers in orders:
        AuthorizationHandlerResolverContractSuite(
            DefaultAuthorizationHandlerResolver()
        ).assert_ambiguous_match(
            NoAuthorization(),
            requirement,
            handlers,
            assertion=_assert_ambiguous,
        )

    assert digest.apply_calls == 0
    assert unsigned.apply_calls == 0


def test_resolver_rejects_duplicate_api_key_handlers_before_credentials() -> None:
    """Verify an ambiguous API key match does not read the key."""
    calls: list[str] = []

    async def provider(_context: AuthorizationContext) -> SecretValue:
        calls.append("resolved")
        return SecretValue(_PLACEHOLDER)

    authorization = ApiKeyHeaderAuthorization(
        "X-Api-Key",
        "",
        DynamicCredentialSource(provider),
    )

    AuthorizationHandlerResolverContractSuite(
        DefaultAuthorizationHandlerResolver()
    ).assert_ambiguous_match(
        authorization,
        BodySigningRequirement(),
        (ApiKeyHeaderAuthorizationHandler(), ApiKeyHeaderAuthorizationHandler()),
        assertion=_assert_ambiguous,
    )
    assert calls == []
