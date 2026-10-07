"""Composition and boundary tests for immutable transport request plans."""

from collections.abc import Callable, Mapping
from dataclasses import FrozenInstanceError, dataclass, fields
from typing import cast

from mconet.core.domain import (
    Authorization,
    HeaderField,
    Headers,
    OpenIdentifier,
    QueryParameter,
    QueryParameters,
    UriValue,
)
from mconet.core.spi import BodySigningRequirement, TransportRequestPlan


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match plan-owned wording so an unrelated fixture or nested constructor
        # failure cannot accidentally satisfy a negative composition test.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Application authorization satisfying the open structural boundary."""

    kind: OpenIdentifier
    """Open discriminator consumed only by a compatible handler resolver."""


@dataclass(frozen=True, slots=True)
class _MissingAuthorizationKind:
    """Object intentionally lacking the Authorization protocol property."""

    label: str
    """Unrelated text that cannot identify an authorization mechanism."""


@dataclass(frozen=True, slots=True)
class _MalformedAuthorization:
    """Structurally matching authorization with an invalid discriminator value."""

    kind: object
    """Invalid dynamic kind used to test nominal discriminator validation."""


def _plan(
    *,
    transport_extensions: Mapping[str, object] | None = None,
) -> TransportRequestPlan:
    """Build a complete request plan with repeated ordered protocol values."""
    # Use distinct repeated values and non-default signing so the fixture exposes
    # every field without relying on normalization or hidden plan defaults.
    extensions: Mapping[str, object]
    if transport_extensions is None:
        # Keep the branch-local empty mapping fully typed under strict analysis.
        extensions = {}
    else:
        extensions = transport_extensions
    return TransportRequestPlan(
        endpoint=UriValue("https://models.example.test/v1", True),
        path="/chat/completions",
        method="VENDOR-CALL",
        headers=Headers(
            (
                HeaderField("X-Feature", "one"),
                HeaderField("x-feature", "two"),
            )
        ),
        query=QueryParameters(
            (
                QueryParameter("api-version", "one"),
                QueryParameter("api-version", "two"),
            )
        ),
        authorization=_Authorization(OpenIdentifier("authorization.vendor")),
        body_signing_requirement=BodySigningRequirement(True, ("unsigned_payload",)),
        transport_extensions=extensions,
    )


def test_transport_request_plan_preserves_complete_request_facts() -> None:
    """Verify endpoint, routing, collections, authorization, and signing remain exact."""
    marker = object()
    plan = _plan(transport_extensions={"vendorOption": marker})

    # URI identity and primitive text remain exact because the plan does not join
    # endpoint/path, normalize a method, or validate transport-specific syntax.
    assert plan.endpoint == UriValue("https://models.example.test/v1", True)
    assert plan.path == "/chat/completions"
    assert plan.method == "VENDOR-CALL"

    # Repeated fields and parameters preserve protocol order, while opaque values
    # stay available to their later handler and selected transport.
    assert plan.headers.values == (
        HeaderField("X-Feature", "one"),
        HeaderField("x-feature", "two"),
    )
    assert plan.query.values == (
        QueryParameter("api-version", "one"),
        QueryParameter("api-version", "two"),
    )
    assert str(plan.authorization.kind) == "authorization.vendor"
    assert plan.body_signing_requirement.acceptable_modes == ("unsigned_payload",)
    assert plan.transport_extensions["vendorOption"] is marker


def test_transport_request_plan_retains_established_value_identity() -> None:
    """Verify construction reuses immutable values instead of rebuilding them."""
    endpoint = UriValue("https://models.example.test", True)
    headers = Headers()
    query = QueryParameters()
    authorization = _Authorization(OpenIdentifier("authorization.none"))
    signing = BodySigningRequirement()

    plan = TransportRequestPlan(
        endpoint,
        "",
        "POST",
        headers,
        query,
        authorization,
        signing,
    )

    # Every established nominal value retains identity. Only caller-owned mapping
    # membership requires a defensive snapshot because Mapping can be mutable.
    assert plan.endpoint is endpoint
    assert plan.headers is headers
    assert plan.query is query
    assert plan.authorization is authorization
    assert plan.body_signing_requirement is signing


def test_transport_request_plan_snapshots_extension_membership() -> None:
    """Verify caller mapping changes cannot alter a completed transport plan."""
    nested_value: list[str] = ["opaque"]
    source: dict[str, object] = {
        "mode": "vendor",
        "nested": nested_value,
    }

    plan = _plan(transport_extensions=source)
    source["mode"] = "changed"
    source["later"] = True

    # Membership and existing bindings are detached, while intentionally opaque
    # nested runtime values remain by identity rather than being copied or parsed.
    assert plan.transport_extensions == {
        "mode": "vendor",
        "nested": nested_value,
    }
    assert plan.transport_extensions["nested"] is nested_value
    assert "later" not in plan.transport_extensions
    assert not hasattr(plan.transport_extensions, "__setitem__")


def test_transport_request_plan_defaults_to_empty_immutable_extensions() -> None:
    """Verify omitted transport extensions use one safe read-only empty mapping."""
    first = _plan()
    second = _plan()

    # Empty membership is safely shared without state leakage and cannot become
    # a hidden mutable provider configuration channel after plan construction.
    assert first.transport_extensions == {}
    assert first.transport_extensions is second.transport_extensions
    assert not hasattr(first.transport_extensions, "__setitem__")


def test_transport_request_plan_has_frozen_exact_field_surface() -> None:
    """Verify only request planning facts appear on the immutable value."""
    plan = _plan()

    # Payload and encoded body belong to later stages; credentials, resolved
    # handlers, response metadata, and execution state stay outside this plan.
    assert tuple(field.name for field in fields(TransportRequestPlan)) == (
        "endpoint",
        "path",
        "method",
        "headers",
        "query",
        "authorization",
        "body_signing_requirement",
        "transport_extensions",
    )
    assert not hasattr(plan, "payload")
    assert not hasattr(plan, "body")
    assert not hasattr(plan, "handler")
    assert not hasattr(plan, "response")
    _assert_raises(
        FrozenInstanceError,
        lambda: plan.__setattr__("method", "DELETE"),
        "cannot assign to field",
    )


def test_transport_request_plan_requires_uri_and_string_routing_values() -> None:
    """Verify endpoint is nominal while path and method remain exact strings."""
    plan = _plan()

    # Raw endpoint text loses the URI absolute/relative fact, while numeric path
    # or method values cannot be preserved as protocol routing text.
    _assert_raises(
        TypeError,
        lambda: TransportRequestPlan(
            cast(UriValue, "https://models.example.test"),
            plan.path,
            plan.method,
            plan.headers,
            plan.query,
            plan.authorization,
            plan.body_signing_requirement,
        ),
        "endpoint must be a UriValue",
    )
    for field_name, path, method in (
        ("path", cast(str, 1), plan.method),
        ("method", plan.path, cast(str, 1)),
    ):
        _assert_raises(
            TypeError,
            lambda path=path, method=method: TransportRequestPlan(
                plan.endpoint,
                path,
                method,
                plan.headers,
                plan.query,
                plan.authorization,
                plan.body_signing_requirement,
            ),
            f"{field_name} must be a string",
        )


def test_transport_request_plan_requires_ordered_collection_values() -> None:
    """Verify raw sequences cannot replace Headers or QueryParameters."""
    plan = _plan()

    # Both nominal collections preserve repeated values and order; accepting raw
    # tuples would bypass their element and lookup semantics.
    _assert_raises(
        TypeError,
        lambda: TransportRequestPlan(
            plan.endpoint,
            plan.path,
            plan.method,
            cast(Headers, ()),
            plan.query,
            plan.authorization,
            plan.body_signing_requirement,
        ),
        "headers must be Headers",
    )
    _assert_raises(
        TypeError,
        lambda: TransportRequestPlan(
            plan.endpoint,
            plan.path,
            plan.method,
            plan.headers,
            cast(QueryParameters, ()),
            plan.authorization,
            plan.body_signing_requirement,
        ),
        "query must be QueryParameters",
    )


def test_transport_request_plan_requires_valid_authorization_boundary() -> None:
    """Verify authorization needs both structural shape and nominal kind."""
    plan = _plan()

    # Missing kind cannot satisfy the protocol, and a same-named raw string does
    # not provide the OpenIdentifier used for compatible handler selection.
    _assert_raises(
        TypeError,
        lambda: TransportRequestPlan(
            plan.endpoint,
            plan.path,
            plan.method,
            plan.headers,
            plan.query,
            cast(Authorization, _MissingAuthorizationKind("none")),
            plan.body_signing_requirement,
        ),
        "authorization must implement Authorization",
    )
    _assert_raises(
        TypeError,
        lambda: TransportRequestPlan(
            plan.endpoint,
            plan.path,
            plan.method,
            plan.headers,
            plan.query,
            cast(Authorization, _MalformedAuthorization("authorization.none")),
            plan.body_signing_requirement,
        ),
        "authorization kind must be an OpenIdentifier",
    )


def test_transport_request_plan_requires_body_signing_requirement() -> None:
    """Verify a mapping or mode string cannot replace the complete signing plan."""
    plan = _plan()

    # The nominal value owns required/mode/algorithm/buffer coherence; this plan
    # never reconstructs or guesses those facts from a partial dynamic value.
    _assert_raises(
        TypeError,
        lambda: TransportRequestPlan(
            plan.endpoint,
            plan.path,
            plan.method,
            plan.headers,
            plan.query,
            plan.authorization,
            cast(BodySigningRequirement, {"required": False}),
        ),
        "body_signing_requirement must be a BodySigningRequirement",
    )


def test_transport_request_plan_requires_string_keyed_extension_mapping() -> None:
    """Verify extension membership is mapping-shaped and string-addressable."""
    plan = _plan()

    # A sequence is not named extension membership, and non-string keys cannot
    # form portable transport-extension names across language bindings.
    _assert_raises(
        TypeError,
        lambda: TransportRequestPlan(
            plan.endpoint,
            plan.path,
            plan.method,
            plan.headers,
            plan.query,
            plan.authorization,
            plan.body_signing_requirement,
            cast(Mapping[str, object], ()),
        ),
        "transport_extensions must be a mapping",
    )
    _assert_raises(
        TypeError,
        lambda: TransportRequestPlan(
            plan.endpoint,
            plan.path,
            plan.method,
            plan.headers,
            plan.query,
            plan.authorization,
            plan.body_signing_requirement,
            cast(Mapping[str, object], {1: "invalid"}),
        ),
        "transport_extensions keys must be strings",
    )
