# Mconet Python SDK

Protocol-driven Python SDK for one model interaction at a time. Core does not bind itself to a vendor. A call names a service, a protocol, and a model. An adapter for that protocol plans the exchange and reads the decoded response. A separate codec turns the payload into bytes. The built-in adapter speaks OpenAI-compatible chat. Another model is reached by supplying that model's adapter to the same pipeline.

The public entry is [`mconet.client`](src/mconet/client). Domain values stay open so a new protocol can reuse them. Components are instances the caller passes in. There is no global component registry, and a call does not change the components of a later call.

The client is asynchronous. One `ModelClient` can run many interactions. Each interaction keeps its own options and runtime state.

## Requirements

- Python `3.11`, `3.12`, `3.13`, or `3.14`
- `asyncio`

This repository installs with pip. The distribution name is `mconet-sdk`. The import name is `mconet`.

## Install

The package is consumed from this repository.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

```python
from mconet.client import make_openai_compatible
```

An application that depends on a built artifact uses the distribution name:

```toml
dependencies = ["mconet-sdk==0.1.0.dev0"]
```

[`samples/text-unary`](samples/text-unary) is that packaging consumer. Its module does not place a call. The runnable calls are in [`examples/`](examples).

## Modules

| Module | Role |
| --- | --- |
| `mconet.client` | Public client: factories, the text helper, and the call surface |
| `mconet.core.domain` | Requests, messages, artifacts, errors, and result projections |
| `mconet.core.spi` | Replaceable component contracts |
| `mconet.core.runtime` | One interaction pipeline |
| `mconet.auth.basic` | No authorization, header API key, and Bearer |
| `mconet.codec.json` | JSON encode and decode |
| `mconet.integration.openai_compatible` | Chat-completions adapter and message mapping |
| `mconet.transport.http_system` | System HTTP and HTTPS transport |
| `mconet.testing` | Stubs, a fake clock, and contract suites for tests |

The symbol index is [`docs/public-api-reference.md`](docs/public-api-reference.md).

## Capabilities

One pipeline accepts every call:

```text
ModelRequest
→ validate the task, messages, and mode
→ select the adapter from protocol_id, task type, and mode
→ prepare a plan with no I/O and no credential read
→ encode, then authorize, then send
→ decode the response
→ ModelOutput
```

`interact_server_stream` uses the same preparation and stops at events. It does not assemble a `ModelOutput`.

`ModelTarget` keeps the three identities apart. `service_id` names the service, `protocol_id` selects the adapter together with the task type and the interaction mode, and `model` is the model that adapter sends. A model name does not select a protocol, and the SDK does not guess one from an endpoint or from `model.name`.

`ModelTarget` and `ServiceAccess` are structural protocols. An application supplies any object with those attributes. It does not subclass an SDK base.

A new protocol reuses those open identifiers, then supplies a `TaskProtocolAdapter`. Codecs, transport, and authorization are separate instances on the same call.

### What this package sends

The architecture baseline calls the first release R1 Text Unary. That shared gate is one text conversation, sent once:

| Dimension | R1 Text Unary |
| --- | --- |
| Task | `conversation.generate` |
| Text | `message.system`, `message.user`, and `message.assistant` text |
| Mode | `unary` |
| Wire format | JSON |
| Transport | HTTP and HTTPS |
| Authorization | None, one named API-key header, or Bearer |
| Built-in integration | OpenAI-compatible chat completions. `protocol_id` is `openai.chat-completions` |
| Configuration | Client defaults, plus one override on a single call |
| Output | Assistant text, finish reason, token usage, and model metadata on one `ModelOutput` |

`interact` sends one unary `ModelRequest`. `interact_text` sends one unary user text message and does not carry tools, sampling controls, or a system message. There is no `MconetClient(model=..., api_key=...)` constructor and no `output.text` shortcut. The caller supplies a `ModelTarget` and a `ServiceAccess`, and reads assistant text from `ConversationTaskResult.text`.

This package's frozen scope, [`spec/r1-scope.json`](spec/r1-scope.json), also sends two things outside that unary gate. The architecture assigns text `server_stream` to R1.1, and that version includes an assembled final output, a framer, an accumulator, and a consumption mode. Tool-call and tool-result elements are outside the R1 message gate.

| Extra in this package | What the call actually returns |
| --- | --- |
| `server_stream` | Text fragments and a finish reason on `ServerStreamEvent`. There is no assembled `ModelOutput` |
| `message.tool_call` and `message.tool_result` | The model can ask for a function, and the caller can send the result back. The SDK does not run the function |

`client_stream`, `duplex`, and `long_running` have no public entry. Another content kind, including `content.artifact`, and a non-empty artifact catalog fail before a credential is read. The stable code is `unsupported_message_content`. `ArtifactKind.id` stays an open identifier, so application data can store `artifact.image`, `artifact.audio`, `artifact.video`, and `artifact.file`. This package does not send them.

Any other model that can carry this text conversation uses the same client. Pass its `TaskProtocolAdapter`, or a resolver that returns one. `supports` matches `protocol_id`, task type, and mode. The plan must still be parameter-free `application/json` over HTTP. `make_openai_compatible` is the built-in composition for chat completions, not a closed set of models.

Default byte limits, used when a call does not override them:

| Limit | Bytes |
| --- | --- |
| `max_response_body_bytes` | 16,777,216 |
| `max_streaming_error_body_bytes` | 1,048,576 |
| `max_frame_bytes` | 2,097,152 |

The default transport is the standard-library `http.client`, run on a worker thread. It does not follow redirects. A 3xx status is a service error, so an API key is not replayed onto another address. `make_default` builds that transport with an empty proxy environment, so it does not read process proxy variables. `make_openai_compatible` uses the binding transport, whose omitted proxy environment is read from the process at send time. No third-party HTTP client is required.

## Quick start

`ModelTarget` and `ServiceAccess` are protocols. The dataclasses below are application types.

```python
import asyncio
import os
from dataclasses import dataclass, field
from types import MappingProxyType

from mconet.auth.basic import BearerAuthorization, FixedCredentialSource
from mconet.client import make_openai_compatible
from mconet.core.domain import (
    Authorization,
    ConversationTaskResult,
    Extensions,
    Headers,
    ModelDescriptor,
    ModelOutput,
    ModelTarget,
    NamedModel,
    OpenIdentifier,
    QueryParameters,
    SecretValue,
    ServiceAccess,
    UriValue,
)


def _empty_extensions() -> Extensions:
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class ChatTarget:
    service_id: OpenIdentifier
    protocol_id: OpenIdentifier
    model: ModelDescriptor
    deployment_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


@dataclass(frozen=True, slots=True)
class ChatAccess:
    endpoint: UriValue | None
    authorization: Authorization | None
    headers: Headers = field(default_factory=Headers)
    query: QueryParameters = field(default_factory=QueryParameters)
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


async def main() -> None:
    api_key = os.environ.get("VENDOR_API_KEY", "")
    if not api_key:
        raise RuntimeError("VENDOR_API_KEY must be set.")

    target: ModelTarget = ChatTarget(
        OpenIdentifier("provider.example"),
        OpenIdentifier("openai.chat-completions"),
        NamedModel("vendor-model"),
    )
    access: ServiceAccess = ChatAccess(
        UriValue("https://provider.example.test", True),
        BearerAuthorization(FixedCredentialSource(SecretValue(api_key))),
    )
    client = make_openai_compatible(target, access)
    try:
        output = await client.interact_text(target, "Hello")
        print(conversation_text(output))
    finally:
        await client.close()


def conversation_text(output: ModelOutput) -> str:
    result = output.result
    if not isinstance(result, ConversationTaskResult):
        raise TypeError("Expected a conversation.generate result.")
    return result.text


asyncio.run(main())
```

`make_openai_compatible` stores the target and service access as client defaults and installs a resolver. That resolver's binding supplies the chat adapter, the JSON codecs, one system HTTP transport, and the three authorization handlers. The service-access authorization selects one handler. The chat request path is `/v1/chat/completions`, appended to the endpoint after one trailing slash is removed. Put the origin in `endpoint`, for example `https://provider.example.test`, which is sent to `https://provider.example.test/v1/chat/completions`. An endpoint that already ends in `/v1` is sent to `/v1/v1/chat/completions`.

`interact` and `interact_text` send `stream` false and return one assembled `ModelOutput`. `interact_server_stream` sends `stream` true and returns events. It does not return that assembled output.

## Calls

### Unary text

`interact_text` sends one user message. The prompt is not trimmed.

```python
output = await client.interact_text(target, "What is a protocol identifier?")
```

A system message, or any later turn, is a conversation document built with `MessageDocumentBuilder`, `ConversationTaskBuilder`, and `ConversationRequestBuilder`. `model_request_from_text` builds the one-message envelope without sending it. Task validation stays in `ConversationTaskBuilder`. Envelope validation stays in `ModelRequestBuilder`.

```python
from mconet.client import model_request_from_text
from mconet.core.spi import InteractionOptions

request = model_request_from_text(target, "Hello")
output = await client.interact(request, InteractionOptions())
```

A conversation result carries assistant text, a finish reason, and usage when the service reports them.

```python
str(output.status.id)  # "completed" when generation finished with finish_reason "stop"
output.stop_reason  # provider finish reason, such as "stop"
output.usage  # TokenUsage(input_tokens, output_tokens, total_tokens, extensions)
```

For this protocol, `status.id` is `completed` for `stop`, `incomplete` for `length`, `filtered` for `content_filter`, `requires_action` for `tool_calls` and `function_call`, and `unknown` for any other finish reason. `ConversationTaskResult.text` concatenates assistant text in document order. Other roles stay in the message document.

### Server stream

`server_stream` is part of this package's scope file. It is not the architecture baseline's unary-only gate, and it is not a `StreamedOutput` with `finalOutput()`.

```python
from mconet.client import model_request_from_text
from mconet.core.spi import InteractionOptions

request = model_request_from_text(target, "Hello")
stream = await client.interact_server_stream(request, InteractionOptions())
try:
    async for event in stream:
        if event.done:
            break
        print(event.text, end="")
finally:
    await stream.aclose()
```

Use a client from `make_openai_compatible`. Its resolver returns the chat adapter, and a server-stream plan asks the service for an event stream. Each event carries the new text fragment for one choice. Earlier fragments are not repeated. `tool_calls` on an event, when present, is the calls assembled so far for that choice, not one argument fragment. `done` marks the terminal event and carries no model token. An event has no token usage.

This stream is not a `ModelOutput`, and it has no `finalOutput()`. Finish reason, response id, and model name stay on the events that reported them. The iterator can be read once. A second iteration fails with `stream_events_consumed`. `aclose` releases the exchange and does not cancel some other interaction on the same client. `include_raw_response` is not applied. `make_default` does not install the chat resolver, so `interact_server_stream` on that client needs an adapter whose plan can map the event stream.

### Tools

Tool elements are part of this package's scope file. The architecture baseline leaves them out of R1 Text Unary. The SDK still does not execute a tool.

A tool declaration is a name, an optional description, and a JSON Schema object. Put it on `GenerationParameters`, then on a `GenerationParametersNode` beside the conversation input, and send that task through `interact`. Creating the parameter object does not send a request. The chat adapter writes `tools` and, when set, `tool_choice`. The SDK does not call the function, parse the arguments, repair them, or run an agent loop.

```python
from mconet.core.domain import FunctionTool, GenerationParameters

parameters = GenerationParameters(
    tools=(
        FunctionTool(
            "get_weather",
            "Weather for a city.",
            {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        ),
    ),
    tool_choice="auto",
)
```

`tool_choice` may be `auto`, `none`, `required`, or the name of one declared function. `None` omits the field.

`interact_text` does not declare tools. When the assistant asks for one, `status.id` is `requires_action`. The result document places a `ToolCallElement` immediately after the assistant entry. `arguments` is the model's raw text. Run the function, then send the conversation again with a `ToolResultElement` that cites `call_id`. The adapter sends that element as its own tool message. It is not folded into the assistant message.

### Sampling controls

`interact_text` and `model_request_from_text` leave generation controls off the task. To send them, add a `GenerationParameters` value on a `task.configuration` leaf beside the conversation input. The chat adapter maps these fields onto the chat-completions body:

| Domain field | Wire field | Constraint on this protocol |
| --- | --- | --- |
| `temperature` | `temperature` | Non-negative, copied exactly. `strict` rejects a value above `2`. `compatible` and `permissive` send a larger value and leave acceptance to the service |
| `top_p` | `top_p` | `0` through `1` |
| `max_output_tokens` | `max_tokens` | Positive safe integer |
| `stop` | `stop` | Non-empty strings, in order, sent as an array. An empty tuple omits the field |
| `seed` | `seed` | Safe integer |

The default policy is `compatible` when the client and the call both omit one. `strict` and any unknown mode enforce the wire profile. `compatible` and `permissive` do not.

### Cancellation, limits, and overrides

Options apply to one call. They are not written back onto the client.

```python
from mconet.core.domain import InteractionResourceLimits
from mconet.core.spi import InteractionOptions

output = await client.interact(
    request,
    InteractionOptions(
        cancellation_signal=signal,
        resource_limits=InteractionResourceLimits(max_response_body_bytes=1_048_576),
        service_access_override=access,
    ),
)
```

`cancellation_signal` is a caller-owned `CancellationSignal` for that interaction. The HTTP attempt subscribes to it. Omitting the signal does not cancel the attempt, and `InteractionOptions` has no deadline. The unary and server-stream entries pass no timeout, so they do not compute one. `service_access_override` is the highest service-access layer for that call. Below it are the request, the client default, and the integration default. A field it supplies wins over the same field on a lower layer. Authorization is taken as one description. Headers, query, and extensions each use the highest non-empty collection and are not merged member by member. A call resource limit replaces the matching client limit for that field, then the SDK default.

Monitor merge defaults to `append`: client monitors, then interaction monitors. `prepend` reverses that order. `replace` keeps only the interaction monitors, and an empty replace disables the client monitors.

### Raw response

Set `include_raw_response=True` on a unary call to keep a sanitized copy of the response bytes and metadata on the returned object. A normal `ModelOutput` does not have `raw_response`. A body past the resolved response limit is omitted and `body_omitted` is set. The body is not copied as a prefix. Headers, trailers, and extension keys are dropped when the name is the header named by the authorization, when the name contains `authorization`, `cookie`, or `secret`, or when the name contains `apikey` after `-` and `_` are removed.

```python
output = await client.interact(
    request,
    InteractionOptions(include_raw_response=True),
)
snapshot = output.raw_response
```

## Authorization

Authorization is a description plus a credential source. The secret stays inside `SecretValue` until a handler calls `reveal` for that request. `str` and `repr` of a `SecretValue` are `[REDACTED]`. The value cannot be pickled.

| Kind | Type | What the description carries |
| --- | --- | --- |
| `authorization.none` | `NoAuthorization` | No credential |
| `authorization.bearer` | `BearerAuthorization` | `credential_source`. The handler writes header `Authorization`. The value is `Bearer`, one space, then the token |
| `authorization.api_key_header` | `ApiKeyHeaderAuthorization` | `header_name`, `prefix`, and `credential_source`. The prefix is concatenated in front of the key. An empty prefix sends the key alone |

```python
from mconet.auth.basic import ApiKeyHeaderAuthorization, DynamicCredentialSource
from mconet.core.domain import SecretValue

async def read_key(context):
    del context
    return SecretValue(await read_key_from_your_vault())

authorization = ApiKeyHeaderAuthorization(
    "x-api-key",
    "",
    DynamicCredentialSource(read_key),
)
```

`resolve` may return a fixed, rotating, or remotely loaded secret. The runtime calls it for each interaction that needs it. Refresh, caching, and persistence stay in the source. The source does not retry.

`make_openai_compatible` and `make_default` both install `NoAuthorizationHandler`, `BearerAuthorizationHandler`, and `ApiKeyHeaderAuthorizationHandler`.

## Errors

A failed interaction raises `ModelInteractionError` from `mconet.core.domain`. The SDK reports the failure and does not retry. A shape error while building a conversation is `TypeError` or `ValueError`. A conversation outside the supported text scope is `ModelInteractionError` before the request is sent.

| Field | Meaning |
| --- | --- |
| `category` | High-level class, such as `authentication`, `rate_limit`, `timeout`, or `cancellation` |
| `phase` | Pipeline stage, such as `validation`, `authentication`, or `transport` |
| `code` | Stable machine-readable code, such as `client_closed` or `unsupported_task` |
| `status_code` | HTTP-style status when the service sent one |
| `service_error_code` | Provider code, preserved as reported |
| `request_id` | Service correlation id when reported |
| `recovery` | Optional `transient`, `retry_after`, and `request_may_have_been_processed` |
| `cause` | Original failure when one was retained |

`retry_after` is a `Duration` whose `total_nanoseconds` is the wait. It does not start a retry. A cancelled call raises category `cancellation` and code `interaction_cancelled`. The category list in the troubleshooting guide still shows the architecture token `cancelled`.

```python
from mconet.core.domain import ModelInteractionError

try:
    await client.interact_text(target, "Hello")
except ModelInteractionError as error:
    if str(error.category.id) == "rate_limit":
        wait = error.recovery.retry_after if error.recovery is not None else None
        # The application decides whether to wait and call again.
        del wait
    raise
```

Category, phase, and code tables are in [`docs/error-troubleshooting.md`](docs/error-troubleshooting.md). `message` is a technical summary. It is not end-user copy.

After `close()`, a new `interact`, `interact_text`, or `interact_server_stream` raises `ModelInteractionError` with code `client_closed`. A second `close()` returns. `close` releases SDK-owned builtin components. It does not close application-owned components, and it does not cancel an interaction that has already entered the runtime.

## Customize, extend, and inject

A model that is not the built-in chat binding enters through the same client. Pass its `TaskProtocolAdapter` when the client is created, or on one call. Pass a JSON codec, a transport, or authorization handlers when that protocol needs a different implementation of those roles. Construction checks that each supplied component exposes the method its role requires. It does not call that method. Adjacent components must declare ports that connect. A port mismatch fails with `invalid_component_type_contract` or `component_type_mismatch` before the request is sent.

This release still requires `conversation.generate` with text. The prepared plan must be parameter-free `application/json` over HTTP, with type ports limited to `json.value` or `transport.bytes`. Another media type, a parameter on that JSON type, a non-HTTP transport kind, or an extra transport capability fails with `unsupported_protocol_plan` before I/O. `client_stream`, `duplex`, and `long_running` are not entries on this client. Audio, video, and images stay on the open `ArtifactKind.id` in application data. This call does not receive them.

There is no plugin registry and no component id lookup. Supply the object itself.

### Precedence

1. `InteractionOptions.components` on one `interact` or `interact_server_stream` call.
2. `components` on the `ModelClientConfiguration`, including the resolver installed by `make_openai_compatible`.
3. The integration plan selected for that target.
4. The SDK defaults created with the client.

A single-value role on a higher layer replaces that role. It does not merge with the lower layer, and an incompatible explicit value is not replaced by a default. `authorization_handlers` uses the highest non-empty list and drops the lists below it: the call, then the client, then the integration binding, then the SDK defaults. An empty tuple is absent, so it does not hide the next list. A call that passes one custom handler must include every handler that call still needs. The resolver keeps the one candidate whose `supports` matches the authorization. Zero matches is `unsupported_authorization`. More than one match is `ambiguous_authorization_handler`.

### Default implementations

`make_default` installs the transport, JSON codecs, and authorization handlers below, and injects no application components. It does not install an adapter or a resolver. `make_openai_compatible` starts from that client, stores the caller's target and service access, and installs the chat resolver. A role you pass in `components` replaces that column for the client. A role you pass on one call replaces it for that call.

| Role | `make_default` | `make_openai_compatible` |
| --- | --- | --- |
| `transport` | `DefaultSystemHttpTransport` with an empty proxy environment | The binding's `DefaultSystemHttpTransport`. An omitted proxy environment is read from the process at send time. `close` releases that instance |
| `task_protocol_adapter` | None. Pass an adapter or a resolver | None on the client. The resolver returns `OpenAIChatCompletionsAdapter` |
| `model_integration_resolver` | None | `DefaultModelIntegrationResolver` for `openai.chat-completions` in `unary` and `server_stream` |
| `payload_encoder` | `JsonPayloadEncoder` | The binding's `JsonPayloadEncoder` |
| `success_payload_decoder` | `JsonSuccessPayloadDecoder`, limit 16,777,216 bytes | The binding decoder, using `max_response_body_bytes` |
| `error_payload_decoder` | `JsonErrorPayloadDecoder`, limit 16,777,216 bytes | The binding decoder, using the same limit |
| `authorization_handlers` | `NoAuthorizationHandler`, `BearerAuthorizationHandler`, `ApiKeyHeaderAuthorizationHandler` | The same three handlers |
| `authorization_handler_resolver` | Runtime `DefaultAuthorizationHandlerResolver` | Same runtime resolver |
| `service_access_resolver` | Runtime `DefaultServiceAccessResolver` | Same runtime resolver |

JSON codecs come from `mconet.codec.json`. Authorization handlers come from `mconet.auth.basic`. The chat adapter comes from `mconet.integration.openai_compatible`. The two runtime resolvers come from `mconet.core.runtime`. The HTTP transport comes from `mconet.transport.http_system`.

The default interaction mode is `unary`. On `make_openai_compatible`, `interact_server_stream` selects `server_stream` and reads the response with the mapper the chat plan installs. The compatibility policy is `compatible` when the client and the call both omit one.

`DefaultAuthorizationHandlerResolver` keeps the one candidate whose `supports` matches the authorization. Zero matches is `unsupported_authorization`. More than one match is `ambiguous_authorization_handler`. `DefaultServiceAccessResolver` merges the call override, the request, the client default, and the integration default. The two runtime resolvers are used when the client does not pass `authorization_handler_resolver` or `service_access_resolver`.

A `task_protocol_adapter` skips integration resolution. A `model_integration_resolver` runs when no adapter is present. `make_default` requires one of the two before a call can be sent. `make_openai_compatible` installs the chat resolver, so the call's `protocol_id`, task type, and mode select the chat adapter. The model name is unread during that selection.

`ModelClientConfiguration` stores reusable defaults: `default_target`, `default_service_access`, `default_compatibility_policy`, and `default_resource_limits`. A request target and a call's `service_access_override` sit above those defaults.

### Replace the transport

A custom transport implements `Transport` from `mconet.core.spi`. `send` receives the authorized request and returns response bytes. The JSON encoder's contract is an input port of `json.value` as parameter-free `application/json`; it declares no output port because the result is the transport body. Each JSON decoder's contract is an output port of `json.value` and declares no input port. `close()` does not release an injected transport.

[`examples/company_http_transport.py`](examples/company_http_transport.py) injects a transport at client scope and again for one call. A per-call replacement uses the same object on the call:

```python
await client.interact(request, InteractionOptions(components=RuntimeComponents(transport=transport)))
```

### Replace the protocol adapter

`TaskProtocolAdapter` is how a model's protocol joins the pipeline. It matches `protocol_id`, the task type, and the mode, prepares a plan, builds an unencoded payload, and parses a decoded success or error. It does not read credentials, encode bytes, authorize, or send. This release has already limited the request to `conversation.generate` with text, and the plan to JSON over HTTP.

`prepare_plan` returns a `ProtocolExecutionPlan`: endpoint, path, method, headers, the authorization description, and the encoder, decoder, and transport requirements. A direct adapter that speaks JSON uses payload type id `json.value` with the default codecs. The worked example is [`examples/custom_adapter.py`](examples/custom_adapter.py).

To select among adapters yourself, pass `components.model_integration_resolver` instead of `task_protocol_adapter`. `resolve` returns one plan whose adapter handles that target. More than one match is `ambiguous_model_integration`. No match is `unsupported_model_integration`.

### Supply a credential source

`FixedCredentialSource` retains one `SecretValue`. `DynamicCredentialSource` calls an async provider on every `resolve`. The provider receives the `AuthorizationContext` and returns a `SecretValue`. Reject the awaitable on provider failure or cancellation. [`examples/dynamic_credential.py`](examples/dynamic_credential.py) reads a bearer credential again for each interaction.

### Other replaceable roles

Pass any of these on `RuntimeComponents` at the client or on one call:

| Field | Contract | Role |
| --- | --- | --- |
| `task_protocol_adapter` | `TaskProtocolAdapter` | Protocol match, plan, request, and response |
| `model_integration_resolver` | `ModelIntegrationResolver` | Choose one adapter from the target |
| `payload_encoder` | `PayloadEncoder` | Unencoded payload to bytes |
| `success_payload_decoder` | `PayloadDecoder` | Success bytes to a typed value |
| `error_payload_decoder` | `PayloadDecoder` | Error bytes to a typed value |
| `transport` | `Transport` | Send the authorized request |
| `authorization_handlers` | `tuple[AuthorizationHandler, ...]` | Candidates selected by authorization kind |
| `authorization_handler_resolver` | `AuthorizationHandlerResolver` | Pick exactly one handler |
| `service_access_resolver` | `ServiceAccessResolver` | Merge request and configured access |

[`examples/custom_codec.py`](examples/custom_codec.py) replaces the encoder and the two decoders independently. [`examples/per_call_override.py`](examples/per_call_override.py) replaces one component for a single call without changing the client.

Each component carries a `descriptor`: `name`, `version`, `capabilities`, `source` (`builtin`, `plugin`, or `application`), and an optional `type_contract`. Name and version are diagnostic. They are not lookup keys.

`source` `application` marks a caller-owned instance. `close()` stops new requests and releases SDK-owned builtin components. It does not call `close` on injected components.

The scope of this client is [`spec/r1-scope.json`](spec/r1-scope.json).

## Examples

| Example | What it shows |
| --- | --- |
| [`examples/simplest_call.py`](examples/simplest_call.py) | `make_openai_compatible` with one text prompt and no authorization |
| [`examples/dynamic_credential.py`](examples/dynamic_credential.py) | A bearer credential resolved again on every interaction |
| [`examples/per_call_override.py`](examples/per_call_override.py) | One component overridden for a single call |
| [`examples/custom_adapter.py`](examples/custom_adapter.py) | A direct `TaskProtocolAdapter` beside an in-memory transport |
| [`examples/custom_codec.py`](examples/custom_codec.py) | Encoder and success and error decoders replaced independently |
| [`examples/company_http_transport.py`](examples/company_http_transport.py) | A transport injected through `components` |
| [`samples/text-unary`](samples/text-unary) | Packaging consumer of `mconet-sdk`. The module itself does not place a call |

## Develop this repository

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

```bash
ruff format --check .
ruff check .
pyright
python scripts/check_import_boundaries.py
python scripts/check_api_compatibility.py
python scripts/check_experimental_api_policy.py
python scripts/check_package_names.py
python scripts/check_runtime_compatibility.py
python scripts/check_secrets.py
python scripts/check_version_policy.py
python scripts/check_spec_module.py
pytest tests/unit
pytest
python -m build
python scripts/build_all.py
```

CI runs the format, lint, type, boundary, and build checks on Python 3.11, then unit tests on 3.11 through 3.14, then contract, conformance, and the release-package check.

## Further reading

- [Public API reference](docs/public-api-reference.md)
- [Error troubleshooting](docs/error-troubleshooting.md)
- [Initial release scope](spec/r1-scope.json)
- [Initial OpenAI-compatible endpoint](spec/compatibility/r1-openai-endpoint.json)
- [Initial OpenAI-compatible protocol](spec/compatibility/r1-openai-protocol.json)

## License

Copyright © 2026 Mcont.
