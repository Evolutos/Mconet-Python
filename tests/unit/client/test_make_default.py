"""A zero-injection client uses JSON, system HTTP, and basic authorization."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, cast

from mconet.auth.basic import NoAuthorization
from mconet.client import make_default
from mconet.client.text_request import model_request_from_text
from mconet.core.domain import (
    ArtifactCatalog,
    Authorization,
    Extensions,
    HeaderField,
    Headers,
    MediaType,
    ModelDescriptor,
    ModelInteractionError,
    ModelRequest,
    ModelTarget,
    ModelTaskResult,
    NamedModel,
    OpenIdentifier,
    OutputStatus,
    ParsedTaskResponse,
    QueryParameters,
    ServiceAccess,
    TaskDescriptor,
    TaskDocument,
    TaskGroupNode,
    TaskNodeKind,
    UriValue,
)
from mconet.core.domain.resolved_service_access import ResolvedServiceAccess
from mconet.core.spi import (
    BodySigningRequirement,
    ComponentDescriptor,
    ComponentTypeContract,
    ComponentTypePort,
    DecoderSelection,
    EncoderSelection,
    ErasedRuntimeValue,
    InteractionOptions,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
    RuntimeComponents,
    TaskProtocolAdapter,
    TransportRequestPlan,
    TransportSelection,
)
from mconet.testing import MockHttpResponseScript, MockHttpServer


def _empty_extensions() -> Extensions:
    """Return one immutable empty extension mapping."""
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class _Target:
    """Structural target accepted by the text request helper."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _Access:
    """Explicit endpoint and no-authorization decision."""

    endpoint: UriValue | None
    authorization: Authorization | None
    headers: Headers = field(default_factory=Headers)
    query: QueryParameters = field(default_factory=QueryParameters)
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


class _TaskKind:
    """Container kind for one parsed result."""

    def __init__(self) -> None:
        """Store the kind identity and composition."""
        self.id = OpenIdentifier("task.root")
        self.composition: Literal["container"] = "container"


class _TaskDescriptor:
    """Descriptor for one structural parsed result."""

    def __init__(self) -> None:
        """Store the descriptor fields used by output validation."""
        self.type = OpenIdentifier("vendor.result")
        self.version = "1.0"
        self.input_schema_id = "schema.vendor.input"
        self.output_schema_id = "schema.vendor.output"
        self.metadata: Extensions = MappingProxyType({})
        self.extensions: Extensions = MappingProxyType({})


class _Result:
    """Structural result retained by the assembled output."""

    def __init__(self) -> None:
        """Store one empty task document."""
        kind: TaskNodeKind = _TaskKind()
        descriptor: TaskDescriptor = _TaskDescriptor()
        self.descriptor = descriptor
        self.document = TaskDocument("1.0", TaskGroupNode("root", kind, ()))
        self.artifacts = ArtifactCatalog()
        self.metadata: Extensions = MappingProxyType({"taskLabel": "vendor.result"})
        self.extensions: Extensions = MappingProxyType({})


class _Adapter:
    """Adapter that plans JSON and parses the decoded success value."""

    def __init__(self) -> None:
        """Store one reusable parsed result and the decoded JSON value."""
        json_type = OpenIdentifier("json.value")
        media = MediaType("application", "json")
        self.descriptor = ComponentDescriptor(
            "adapter",
            "1.0.0",
            "application",
            ComponentTypeContract(
                inputs=(
                    ComponentTypePort("response", json_type, None, media),
                    ComponentTypePort("error", json_type, None, media),
                ),
                outputs=(ComponentTypePort("payload", json_type, None, media),),
            ),
        )
        self.decoded: object | None = None
        self._result = _Result()

    def supports(self, target: object, task: object, mode: object) -> bool:
        """Accept every request presented to this adapter."""
        del target, task, mode
        return True

    def prepare_plan(
        self,
        request: ModelRequest,
        access: ResolvedServiceAccess,
        mode: object,
    ) -> ProtocolExecutionPlan:
        """Plan one JSON POST to the resolved endpoint."""
        del request, mode
        endpoint = access.endpoint
        if endpoint is None:
            raise AssertionError("Expected a resolved endpoint.")
        json_type = MediaType("application", "json")
        return ProtocolExecutionPlan(
            TransportRequestPlan(
                endpoint,
                "",
                "POST",
                Headers(),
                QueryParameters(),
                access.authorization,
                BodySigningRequirement(),
            ),
            EncoderSelection(json_type),
            DecoderSelection(json_type),
            DecoderSelection(json_type),
            TransportSelection(OpenIdentifier("http")),
        )

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Return an empty JSON object for the builtin encoder."""
        del request
        return ProtocolRequestPlan(
            ErasedRuntimeValue(OpenIdentifier("json.value"), {}),
            plan,
        )

    def parse_response(self, response: ErasedRuntimeValue) -> ParsedTaskResponse:
        """Retain the decoded value and return the structural result."""
        self.decoded = response.value
        return ParsedTaskResponse(
            cast(ModelTaskResult, self._result),
            OutputStatus(OpenIdentifier("completed")),
        )

    def parse_error(self, error: object, metadata: object) -> None:
        """Refuse error parsing on this success path."""
        del error, metadata
        return None


def test_make_default_uses_builtin_json_http_and_authorization() -> None:
    """Verify zero injection still encodes, authorizes, sends, and decodes."""
    adapter = _Adapter()
    client = make_default()
    assert client.configuration.components is None
    script = MockHttpResponseScript(
        status_code=200,
        headers=Headers((HeaderField("Content-Type", "application/json"),)),
        body=b'{"ok":true}',
    )
    target: ModelTarget = _Target(
        OpenIdentifier("service.vendor"),
        OpenIdentifier("protocol.vendor"),
        NamedModel("vendor-model"),
    )
    with MockHttpServer((script,)) as server:
        access: ServiceAccess = _Access(server.uri, NoAuthorization())
        request = model_request_from_text(target, "Hello", access)
        output = asyncio.run(
            client.interact(
                request,
                InteractionOptions(
                    components=RuntimeComponents(
                        task_protocol_adapter=cast(TaskProtocolAdapter, adapter),
                    )
                ),
            )
        )
        recorded = server.requests

    assert output.target is request.target
    assert adapter.decoded == {"ok": True}
    assert len(recorded) == 1
    assert recorded[0].body == b"{}"
    assert "application/json" in recorded[0].headers.get_all("Content-Type")
    assert client.configuration.components is None

    asyncio.run(client.close())
    asyncio.run(client.close())
    try:
        asyncio.run(client.interact(request, InteractionOptions()))
    except ModelInteractionError as error:
        assert error.code == "client_closed"
    else:
        raise AssertionError("Expected a closed client to reject the request.")
