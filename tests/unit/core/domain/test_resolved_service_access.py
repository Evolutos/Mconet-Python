"""Completeness and immutability tests for resolved service access values."""

from collections.abc import Callable, Mapping
from dataclasses import FrozenInstanceError, dataclass, fields
from inspect import Parameter, signature
from typing import cast

from mconet.core.domain import (
    Authorization,
    Extensions,
    HeaderField,
    Headers,
    JsonValue,
    OpenIdentifier,
    QueryParameter,
    QueryParameters,
    ResolvedServiceAccess,
    UriValue,
)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match resolved-access diagnostics so nested fixture failures cannot
        # accidentally satisfy a negative field-boundary test.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Application authorization satisfying the open structural contract."""

    kind: OpenIdentifier
    """Handler-selection discriminator retained without credential inspection."""


@dataclass(frozen=True, slots=True)
class _MissingKind:
    """Object intentionally lacking the required authorization discriminator."""

    label: str
    """Unrelated field proving structural authorization recognition is complete."""


@dataclass(frozen=True, slots=True)
class _MalformedAuthorization:
    """Structurally matching authorization with a non-nominal kind value."""

    kind: object
    """Invalid dynamic discriminator used by the nominal-boundary test."""


def _access(*, extensions: Extensions | None = None) -> ResolvedServiceAccess:
    """Build one complete resolved access value with repeated ordered context."""
    # Supply every constructor field explicitly so the fixture exercises the
    # complete post-resolution shape rather than relying on hidden defaults.
    extension_values: Extensions = {} if extensions is None else extensions
    return ResolvedServiceAccess(
        endpoint=UriValue("https://models.example.test/v1", True),
        authorization=_Authorization(OpenIdentifier("authorization.vendor")),
        headers=Headers(
            (
                HeaderField("X-Feature", "one"),
                HeaderField("x-feature", "two"),
            )
        ),
        query=QueryParameters(
            (
                QueryParameter("region", "east"),
                QueryParameter("region", "west"),
            )
        ),
        api_version="2026-10-01",
        project_id="project-a",
        tenant_id="tenant-a",
        extensions=extension_values,
    )


def test_resolved_service_access_requires_every_field_explicitly() -> None:
    """Verify resolution cannot leave any access dimension implicit."""
    parameters = signature(ResolvedServiceAccess).parameters
    expected_fields = (
        "endpoint",
        "authorization",
        "headers",
        "query",
        "api_version",
        "project_id",
        "tenant_id",
        "extensions",
    )

    # Optional values use explicit None rather than constructor omission, while
    # collection and extension fields must always exist as completed snapshots.
    assert tuple(parameters) == expected_fields
    assert (
        tuple(field.name for field in fields(ResolvedServiceAccess)) == expected_fields
    )
    for field_name in expected_fields:
        assert parameters[field_name].default is Parameter.empty


def test_resolved_service_access_preserves_complete_access_context() -> None:
    """Verify endpoint, authorization, ordered context, and provider fields remain exact."""
    marker: list[JsonValue] = ["portable"]
    access = _access(extensions={"futureOption": marker})

    # URI and opaque authorization remain intact; repeated Header and Query
    # entries preserve their order instead of being merged into ordinary maps.
    assert access.endpoint == UriValue("https://models.example.test/v1", True)
    assert access.authorization.kind == OpenIdentifier("authorization.vendor")
    assert access.headers.values == (
        HeaderField("X-Feature", "one"),
        HeaderField("x-feature", "two"),
    )
    assert access.query.values == (
        QueryParameter("region", "east"),
        QueryParameter("region", "west"),
    )
    assert access.api_version == "2026-10-01"
    assert access.project_id == "project-a"
    assert access.tenant_id == "tenant-a"
    assert access.extensions["futureOption"] is marker


def test_resolved_service_access_retains_established_value_identity() -> None:
    """Verify completed access values are reused rather than reconstructed."""
    endpoint = UriValue("https://models.example.test", True)
    authorization = _Authorization(OpenIdentifier("authorization.none"))
    headers = Headers()
    query = QueryParameters()

    access = ResolvedServiceAccess(
        endpoint=endpoint,
        authorization=authorization,
        headers=headers,
        query=query,
        api_version=None,
        project_id=None,
        tenant_id=None,
        extensions={},
    )

    # These established immutable or opaque values already own their invariants;
    # rebuilding them could discard application authorization state or ordering.
    assert access.endpoint is endpoint
    assert access.authorization is authorization
    assert access.headers is headers
    assert access.query is query


def test_resolved_service_access_allows_explicit_absent_optional_context() -> None:
    """Verify optional endpoint and provider context use explicit None values."""
    authorization = _Authorization(OpenIdentifier("authorization.none"))
    access = ResolvedServiceAccess(
        endpoint=None,
        authorization=authorization,
        headers=Headers(),
        query=QueryParameters(),
        api_version=None,
        project_id=None,
        tenant_id=None,
        extensions={},
    )

    # Authorization is still concrete even when all genuinely optional access
    # context is absent, so execution never interprets None as authorization policy.
    assert access.endpoint is None
    assert access.authorization is authorization
    assert access.api_version is None
    assert access.project_id is None
    assert access.tenant_id is None
    assert access.extensions == {}


def test_resolved_service_access_snapshots_extensions_and_freezes_fields() -> None:
    """Verify caller mutation cannot change resolved top-level membership."""
    nested: list[JsonValue] = ["one"]
    source: dict[str, object] = {"mode": "vendor", "nested": nested}
    access = _access(extensions=cast(Extensions, source))

    source["mode"] = "changed"
    source["later"] = True

    # Top-level membership is detached and read-only, while nested JSON data
    # keeps identity under the established shallow Extensions snapshot contract.
    assert access.extensions == {"mode": "vendor", "nested": nested}
    assert access.extensions["nested"] is nested
    assert "later" not in access.extensions
    assert not hasattr(access.extensions, "__setitem__")
    _assert_raises(
        FrozenInstanceError,
        lambda: access.__setattr__("project_id", "changed"),
        "cannot assign to field",
    )


def test_resolved_service_access_requires_endpoint_authorization_and_context_types() -> (
    None
):
    """Verify nominal access values cannot be replaced by raw dynamic data."""
    access = _access()
    cases: tuple[tuple[str, Callable[[], object]], ...] = (
        (
            "endpoint must be a UriValue or None",
            lambda: ResolvedServiceAccess(
                cast(UriValue, "https://models.example.test"),
                access.authorization,
                access.headers,
                access.query,
                access.api_version,
                access.project_id,
                access.tenant_id,
                access.extensions,
            ),
        ),
        (
            "authorization must implement Authorization",
            lambda: ResolvedServiceAccess(
                access.endpoint,
                cast(Authorization, _MissingKind("none")),
                access.headers,
                access.query,
                access.api_version,
                access.project_id,
                access.tenant_id,
                access.extensions,
            ),
        ),
        (
            "authorization kind must be an OpenIdentifier",
            lambda: ResolvedServiceAccess(
                access.endpoint,
                cast(Authorization, _MalformedAuthorization("authorization.none")),
                access.headers,
                access.query,
                access.api_version,
                access.project_id,
                access.tenant_id,
                access.extensions,
            ),
        ),
        (
            "headers must be Headers",
            lambda: ResolvedServiceAccess(
                access.endpoint,
                access.authorization,
                cast(Headers, ()),
                access.query,
                access.api_version,
                access.project_id,
                access.tenant_id,
                access.extensions,
            ),
        ),
        (
            "query must be QueryParameters",
            lambda: ResolvedServiceAccess(
                access.endpoint,
                access.authorization,
                access.headers,
                cast(QueryParameters, ()),
                access.api_version,
                access.project_id,
                access.tenant_id,
                access.extensions,
            ),
        ),
    )

    # Exercise every nominal boundary independently so diagnostics identify the
    # malformed access dimension rather than failing later during execution.
    for message, action in cases:
        _assert_raises(TypeError, action, message)


def test_resolved_service_access_requires_optional_text_context_types() -> None:
    """Verify provider context accepts only exact strings or explicit absence."""
    access = _access()

    # Validate each field independently because providers may set any subset and
    # no field should inherit permissive coercion from another context value.
    for field_name, api_version, project_id, tenant_id in (
        ("api_version", cast(str, 1), access.project_id, access.tenant_id),
        ("project_id", access.api_version, cast(str, 1), access.tenant_id),
        ("tenant_id", access.api_version, access.project_id, cast(str, 1)),
    ):
        _assert_raises(
            TypeError,
            lambda api_version=api_version, project_id=project_id, tenant_id=tenant_id: (
                ResolvedServiceAccess(
                    access.endpoint,
                    access.authorization,
                    access.headers,
                    access.query,
                    api_version,
                    project_id,
                    tenant_id,
                    access.extensions,
                )
            ),
            f"{field_name} must be a string or None",
        )


def test_resolved_service_access_requires_named_extension_mapping() -> None:
    """Verify extensions use mapping storage with string member names."""
    access = _access()

    # Sequences cannot provide named JSON members, and non-string keys cannot
    # cross the portable Extensions boundary used by every platform.
    _assert_raises(
        TypeError,
        lambda: ResolvedServiceAccess(
            access.endpoint,
            access.authorization,
            access.headers,
            access.query,
            access.api_version,
            access.project_id,
            access.tenant_id,
            cast(Extensions, ()),
        ),
        "extensions must be a mapping",
    )
    _assert_raises(
        TypeError,
        lambda: ResolvedServiceAccess(
            access.endpoint,
            access.authorization,
            access.headers,
            access.query,
            access.api_version,
            access.project_id,
            access.tenant_id,
            cast(Extensions, cast(Mapping[object, object], {1: "invalid"})),
        ),
        "extensions keys must be strings",
    )
