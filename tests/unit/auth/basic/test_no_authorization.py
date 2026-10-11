"""Tests for the explicit no-authorization decision."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.auth.basic import NO_AUTHORIZATION_KIND, NoAuthorization
from mconet.core.domain import (
    Authorization,
    Extensions,
    Headers,
    ModelInteractionError,
    OpenIdentifier,
    QueryParameters,
    ServiceAccess,
    UriValue,
)
from mconet.core.runtime.default_service_access_resolver import (
    DefaultServiceAccessResolver,
)


def _empty_extensions() -> Extensions:
    """Create independent extension storage for one access fixture."""
    return {}


@dataclass(slots=True)
class _Access:
    """Minimal access layer that can carry either a decision or an omission."""

    endpoint: UriValue | None
    authorization: Authorization | None
    headers: Headers
    query: QueryParameters
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_no_authorization_is_an_explicit_credential_free_decision() -> None:
    """Verify the value exposes only the stable no-authorization kind."""
    authorization = NoAuthorization()

    # Structural authorization recognition uses the kind. No credential field is
    # part of the decision, so omission and no-auth stay different objects.
    assert isinstance(authorization, Authorization)
    assert not isinstance(authorization, ServiceAccess)
    assert authorization.kind is NO_AUTHORIZATION_KIND
    assert authorization.kind == OpenIdentifier("authorization.none")
    assert not hasattr(authorization, "credential")
    assert not hasattr(authorization, "token")
    assert not hasattr(authorization, "__dict__")


def test_no_authorization_instances_are_interchangeable() -> None:
    """Verify separate instances remain one decision and reject new fields."""
    first = NoAuthorization()
    second = NoAuthorization()

    # Equality follows the decision, not object identity. There is no per-instance
    # secret or header that a caller could vary.
    assert first == second
    assert hash(first) == hash(second)
    assert repr(first) == "NoAuthorization()"
    _assert_raises(
        AttributeError,
        lambda: setattr(first, "credential", "not-a-credential"),
        "does not accept attributes",
    )


def test_no_authorization_rejects_a_substituted_kind() -> None:
    """Verify callers cannot turn the decision into another authorization kind."""
    construct = cast(Callable[..., NoAuthorization], NoAuthorization)
    _assert_raises(
        TypeError,
        lambda: construct(OpenIdentifier("authorization.other")),
        "takes no arguments",
    )


def test_no_authorization_is_distinct_from_missing_configuration() -> None:
    """Verify resolution accepts the decision and rejects an omitted field."""
    endpoint = UriValue("https://models.example.test/v1", True)
    explicit = _Access(
        endpoint=endpoint,
        authorization=NoAuthorization(),
        headers=Headers(),
        query=QueryParameters(),
    )
    omitted = _Access(
        endpoint=endpoint,
        authorization=None,
        headers=Headers(),
        query=QueryParameters(),
    )

    resolved = DefaultServiceAccessResolver().resolve(explicit, None, None, None)
    error = _assert_raises(
        ModelInteractionError,
        lambda: DefaultServiceAccessResolver().resolve(omitted, None, None, None),
        "authorization is not configured",
    )

    # The selected object remains the explicit decision. The omitted layer fails
    # before any credential read or header is produced.
    assert resolved.authorization == NoAuthorization()
    assert resolved.authorization.kind == NO_AUTHORIZATION_KIND
    assert isinstance(error, ModelInteractionError)
    assert error.code == "missing_authorization"
    assert "authorization.none" not in error.message
