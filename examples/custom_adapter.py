"""Inject a task adapter by instance, without a registry or component id."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, cast

from mconet.auth.basic import NoAuthorization, NoAuthorizationHandler
from mconet.client import ModelClient
from mconet.client.text_request import model_request_from_text
from mconet.codec.json import (
    JsonErrorPayloadDecoder,
    JsonPayloadEncoder,
    JsonSuccessPayloadDecoder,
)
from mconet.core.domain import (
    ArtifactCatalog,
    Authorization,
    Bytes,
    Extensions,
    Headers,
    MediaType,
    ModelDescriptor,
    ModelOutput,
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
    ModelClientConfiguration,
    ProtocolExecutionPlan,
    ProtocolRequestPlan,
    RuntimeComponents,
    TransportContext,
    TransportOutcome,
    TransportRequest,
    TransportRequestPlan,
    TransportResponse,
    TransportResponseMetadata,
    TransportSelection,
)


def _empty_extensions() -> Extensions:
    """Return one immutable empty extension mapping."""
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class _ChatTarget:
    """Application target accepted by the custom adapter."""

    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class _ChatAccess:
    """Application access with no authorization."""

    endpoint: UriValue | None
    authorization: Authorization | None
    headers: Headers = field(default_factory=Headers)
    query: QueryParameters = field(default_factory=QueryParameters)
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


class _TaskKind:
    """Container kind for the parsed result."""

    def __init__(self) -> None:
        """Store the kind identity and composition."""
        self.id = OpenIdentifier("task.root")
        self.composition: Literal["container"] = "container"


class _TaskDescriptor:
    """Descriptor for the parsed result."""

    def __init__(self) -> None:
        """Store the descriptor fields used by output validation."""
        self.type = OpenIdentifier("vendor.result")
        self.version = "1.0"
        self.input_schema_id = "schema.example.input"
        self.output_schema_id = "schema.example.output"
        self.metadata: Extensions = MappingProxyType({})
        self.extensions: Extensions = MappingProxyType({})


class _Result:
    """Structural result returned by the custom adapter."""

    def __init__(self) -> None:
        """Store one empty task document."""
        kind: TaskNodeKind = _TaskKind()
        descriptor: TaskDescriptor = _TaskDescriptor()
        self.descriptor = descriptor
        self.document = TaskDocument("1.0", TaskGroupNode("root", kind, ()))
        self.artifacts = ArtifactCatalog()
        self.metadata: Extensions = MappingProxyType({"taskLabel": "vendor.result"})
        self.extensions: Extensions = MappingProxyType({})


class CustomTaskAdapter:
    """Application adapter selected by the instance passed to the client.

    The class has no registry key and no component id. The client receives
    this object directly.
    """

    def __init__(self) -> None:
        """Store the JSON port contract and one reusable result."""
        json_type = OpenIdentifier("json.value")
        media = MediaType("application", "json")
        self.descriptor = ComponentDescriptor(
            "custom-task-adapter",
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
        self._result = _Result()

    def supports(self, target: object, task: object, mode: object) -> bool:
        """Accept the example request without consulting a registry."""
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
            raise ValueError("The example access must include an endpoint.")
        media = MediaType("application", "json")
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
            EncoderSelection(media),
            DecoderSelection(media),
            DecoderSelection(media),
            TransportSelection(OpenIdentifier("http")),
        )

    def build_request(
        self,
        request: ModelRequest,
        plan: ProtocolExecutionPlan,
    ) -> ProtocolRequestPlan:
        """Return an empty JSON object for the public JSON encoder."""
        del request
        return ProtocolRequestPlan(
            ErasedRuntimeValue(OpenIdentifier("json.value"), {}),
            plan,
        )

    def parse_response(self, response: ErasedRuntimeValue) -> ParsedTaskResponse:
        """Return the structural result for any decoded JSON object."""
        del response
        return ParsedTaskResponse(
            cast(ModelTaskResult, self._result),
            OutputStatus(OpenIdentifier("completed")),
        )

    def parse_error(self, error: object, metadata: object) -> None:
        """Do not parse errors in this success example."""
        del error, metadata
        return None


class _LocalTransport:
    """Transport that returns one JSON object without using the network."""

    def __init__(self) -> None:
        """Store an empty transport contract."""
        self.descriptor = ComponentDescriptor(
            "local-transport",
            "1.0.0",
            "application",
            ComponentTypeContract(),
        )

    async def send(
        self,
        request: TransportRequest,
        context: TransportContext,
    ) -> TransportResponse:
        """Return a small JSON success body."""
        del request, context
        return TransportResponse(
            TransportResponseMetadata(
                TransportOutcome(OpenIdentifier("success")),
                Headers(),
                media_type=MediaType("application", "json"),
            ),
            Bytes(json.dumps({"ok": True}).encode("utf-8")),
        )


async def run_custom_adapter() -> ModelOutput:
    """Run one call through the adapter instance and no component registry.

    Returns:
        The assembled output. Its target is the request target.
    """
    adapter = CustomTaskAdapter()
    target: ModelTarget = _ChatTarget(
        OpenIdentifier("service.example"),
        OpenIdentifier("protocol.example"),
        NamedModel("example-model"),
    )
    access: ServiceAccess = _ChatAccess(
        UriValue("https://example.test/v1", True),
        NoAuthorization(),
    )
    client = ModelClient(
        ModelClientConfiguration(
            components=RuntimeComponents(
                task_protocol_adapter=adapter,
                payload_encoder=JsonPayloadEncoder(),
                success_payload_decoder=JsonSuccessPayloadDecoder(1024),
                error_payload_decoder=JsonErrorPayloadDecoder(1024),
                transport=_LocalTransport(),
                authorization_handlers=(NoAuthorizationHandler(),),
            )
        )
    )
    try:
        return await client.interact(
            model_request_from_text(target, "Hello", access),
            InteractionOptions(),
        )
    finally:
        await client.close()
