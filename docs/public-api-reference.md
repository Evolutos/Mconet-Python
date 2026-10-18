# Public API reference

This reference lists every public symbol in `api/public-api.json`.
Signatures include the default values recorded for that symbol.

## Ownership

- `ModelClientConfiguration.components` are application-owned. `ModelClient.close`
  does not close them.
- Components created by `make_default` and the transport created by
  `make_openai_compatible` are SDK-owned. `close` releases those builtin
  components and does not cancel an interaction that has already started.
- `InteractionOptions.components` apply to one interaction and are not written
  back onto the client configuration.
- `include_raw_response` defaults to false. A snapshot keeps the response body
  and metadata only when the caller opts in. A body past the resolved response
  limit is omitted instead of copied. `Authorization`, `Cookie`, and header
  names containing `secret` are not copied into the snapshot.
- Monitor merge defaults to `append`: client monitors, then interaction
  monitors. `prepend` reverses that order. `replace` keeps only the
  interaction monitors, and an empty replace disables the client monitors.

## Symbols

### `mconet.auth.basic.API_KEY_HEADER_AUTHORIZATION_KIND`

- Kind: `value`
- Type: `OpenIdentifier`

### `mconet.auth.basic.ApiKeyHeaderAuthorization`

- Kind: `class`
- Signature: `(header_name: 'str', prefix: 'str', credential_source: 'CredentialSource', kind: 'OpenIdentifier' = OpenIdentifier(value='authorization.api_key_header')) -> 'None'`
- `credential_source` (property)
- `header_name` (property)
- `kind` (property)
- `prefix` (property)

### `mconet.auth.basic.ApiKeyHeaderAuthorizationHandler`

- Kind: `class`
- Signature: `(*args: 'object', **kwargs: 'object') -> 'Self'`
- `apply` (method): `(self, authorization: 'Authorization', context: 'AuthorizationContext', request: 'MutableTransportRequest') -> 'None'`
- `descriptor` (property)
- `supports` (method): `(self, authorization: 'Authorization', body_signing_requirement: 'BodySigningRequirement') -> 'frozenset[BodySigningMode]'`

### `mconet.auth.basic.BEARER_AUTHORIZATION_KIND`

- Kind: `value`
- Type: `OpenIdentifier`

### `mconet.auth.basic.BearerAuthorization`

- Kind: `class`
- Signature: `(credential_source: 'CredentialSource', kind: 'OpenIdentifier' = OpenIdentifier(value='authorization.bearer')) -> 'None'`
- `credential_source` (property)
- `kind` (property)

### `mconet.auth.basic.BearerAuthorizationHandler`

- Kind: `class`
- Signature: `(*args: 'object', **kwargs: 'object') -> 'Self'`
- `apply` (method): `(self, authorization: 'Authorization', context: 'AuthorizationContext', request: 'MutableTransportRequest') -> 'None'`
- `descriptor` (property)
- `supports` (method): `(self, authorization: 'Authorization', body_signing_requirement: 'BodySigningRequirement') -> 'frozenset[BodySigningMode]'`

### `mconet.auth.basic.DynamicCredentialSource`

- Kind: `class`
- Signature: `(provider: 'CredentialProvider') -> 'None'`
- `resolve` (method): `(self, context: 'AuthorizationContext') -> 'CredentialValue'`

### `mconet.auth.basic.FixedCredentialSource`

- Kind: `class`
- Signature: `(secret: 'SecretValue') -> 'None'`
- `resolve` (method): `(self, context: 'AuthorizationContext') -> 'CredentialValue'`

### `mconet.auth.basic.NO_AUTHORIZATION_KIND`

- Kind: `value`
- Type: `OpenIdentifier`

### `mconet.auth.basic.NoAuthorization`

- Kind: `class`
- Signature: `()`
- `kind` (property)

### `mconet.auth.basic.NoAuthorizationHandler`

- Kind: `class`
- Signature: `()`
- `apply` (method): `(self, authorization: 'Authorization', context: 'AuthorizationContext', request: 'MutableTransportRequest') -> 'None'`
- `descriptor` (property)
- `supports` (method): `(self, authorization: 'Authorization', body_signing_requirement: 'BodySigningRequirement') -> 'frozenset[BodySigningMode]'`

### `mconet.auth.basic.reject_unsupported_body_signing`

- Kind: `function`
- Signature: `(body_signing_mode: 'str') -> 'None'`

### `mconet.auth.basic.validate_authorization_header_name`

- Kind: `function`
- Signature: `(name: 'str') -> 'None'`

### `mconet.auth.basic.validate_authorization_header_value`

- Kind: `function`
- Signature: `(value: 'str') -> 'None'`

### `mconet.client.ConversationRequestBuilder`

- Kind: `class`
- Signature: `(target: 'ModelTarget', task: 'ConversationTaskRequest') -> 'None'`
- `build` (method): `(self) -> 'ModelRequest'`
- `with_extensions` (method): `(self, extensions: 'Extensions') -> 'Self'`
- `with_metadata` (method): `(self, metadata: 'Extensions') -> 'Self'`
- `with_service_access` (method): `(self, service_access: 'ServiceAccess | None') -> 'Self'`

### `mconet.client.ModelClient`

- Kind: `class`
- Signature: `(configuration: 'ModelClientConfiguration') -> 'None'`
- `close` (method): `(self) -> 'None'`
- `configuration` (property)
- `interact` (method): `(self, request: 'ModelRequest', options: 'InteractionOptions') -> 'ModelOutput'`
- `interact_text` (method): `(self, target: 'ModelTarget', text: 'str', options: 'InteractionOptions | None' = None, service_access: 'ServiceAccess | None' = None) -> 'ModelOutput'`
- `make_default` (method): `() -> 'ModelClient'`
- `make_openai_compatible` (method): `(target: 'ModelTarget', service_access: 'ServiceAccess', *, max_response_body_bytes: 'int' = 16777216) -> 'ModelClient'`

### `mconet.client.make_default`

- Kind: `function`
- Signature: `() -> mconet.client.model_client.ModelClient`

### `mconet.client.make_openai_compatible`

- Kind: `function`
- Signature: `(target: mconet.core.domain.model_target.ModelTarget, service_access: mconet.core.domain.service_access.ServiceAccess, *, max_response_body_bytes: int = 16777216) -> mconet.client.model_client.ModelClient`

### `mconet.client.model_request_from_text`

- Kind: `function`
- Signature: `(target: 'ModelTarget', text: 'str', service_access: 'ServiceAccess | None' = None) -> 'ModelRequest'`

### `mconet.codec.json.JSON_ERROR_PAYLOAD_DECODER_DESCRIPTOR`

- Kind: `value`
- Type: `ComponentDescriptor`

### `mconet.codec.json.JSON_ERROR_PAYLOAD_DECODER_TYPE_CONTRACT`

- Kind: `value`
- Type: `ComponentTypeContract`

### `mconet.codec.json.JSON_PAYLOAD_ENCODER_CAPABILITY`

- Kind: `value`
- Type: `OpenIdentifier`

### `mconet.codec.json.JSON_PAYLOAD_ENCODER_DESCRIPTOR`

- Kind: `value`
- Type: `ComponentDescriptor`

### `mconet.codec.json.JSON_PAYLOAD_ENCODER_TYPE_CONTRACT`

- Kind: `value`
- Type: `ComponentTypeContract`

### `mconet.codec.json.JSON_SUCCESS_PAYLOAD_DECODER_DESCRIPTOR`

- Kind: `value`
- Type: `ComponentDescriptor`

### `mconet.codec.json.JSON_SUCCESS_PAYLOAD_DECODER_TYPE_CONTRACT`

- Kind: `value`
- Type: `ComponentTypeContract`

### `mconet.codec.json.JsonErrorPayloadDecoder`

- Kind: `class`
- Signature: `(max_body_bytes: 'int') -> 'None'`
- `decode` (method): `(self, raw_data: 'Bytes') -> 'ErasedRuntimeValue'`
- `descriptor` (property)

### `mconet.codec.json.JsonPayload`

- Kind: `class`
- Signature: `(type_id: 'OpenIdentifier', value: 'JsonValue', schema_id: 'str | None' = None) -> None`
- `from_erased` (method): `(erased: 'ErasedRuntimeValue') -> 'JsonPayload'`
- `value_as` (method): `(self, expected_type: 'type[_ValueT]') -> '_ValueT'`

### `mconet.codec.json.JsonPayloadEncoder`

- Kind: `class`
- Signature: `()`
- `descriptor` (property)
- `encode` (method): `(self, payload: 'ErasedRuntimeValue') -> 'TransportBody'`

### `mconet.codec.json.JsonSuccessPayloadDecoder`

- Kind: `class`
- Signature: `(max_body_bytes: 'int') -> 'None'`
- `decode` (method): `(self, raw_data: 'Bytes') -> 'ErasedRuntimeValue'`
- `descriptor` (property)

### `mconet.codec.json.collect_bounded_bytes`

- Kind: `function`
- Signature: `(chunks: 'Iterable[bytes]', max_byte_length: 'int') -> 'Bytes'`

### `mconet.codec.json.encode_utf8`

- Kind: `function`
- Signature: `(text: 'str') -> 'Bytes'`

### `mconet.codec.json.is_json_media_type`

- Kind: `function`
- Signature: `(value: 'object') -> 'bool'`

### `mconet.core.domain.Artifact`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `descriptor` (property)
- `extensions` (property)
- `id` (property)
- `kind` (property)
- `media_type` (property)
- `metadata` (property)
- `source` (property)

### `mconet.core.domain.ArtifactCatalog`

- Kind: `class`
- Signature: `(artifacts: 'tuple[Artifact, ...]' = ()) -> None`

### `mconet.core.domain.ArtifactDescriptor`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `kind` (property)

### `mconet.core.domain.ArtifactKind`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `extensions` (property)
- `id` (property)
- `semantic` (property)

### `mconet.core.domain.ArtifactMetadata`

- Kind: `value`
- Type: `GenericAlias`

### `mconet.core.domain.ArtifactReference`

- Kind: `class`
- Signature: `(artifact_id: 'str', relation: 'OpenIdentifier | None' = None, metadata: 'Extensions' = <factory>) -> None`

### `mconet.core.domain.ArtifactSource`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `kind` (property)

### `mconet.core.domain.Authorization`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `kind` (property)

### `mconet.core.domain.AuthorizedSecretConsumer`

- Kind: `class`
- Signature: `(*args: 'object', **kwargs: 'object') -> 'Self'`

### `mconet.core.domain.Bytes`

- Kind: `value`
- Type: `NewType`

### `mconet.core.domain.CancellationSignal`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `is_cancelled` (property)
- `reason` (property)
- `subscribe` (method): `(self, callback: 'Callable[[str | None], None]') -> 'Callable[[], None]'`

### `mconet.core.domain.CompatibilityPolicy`

- Kind: `class`
- Signature: `(mode: 'OpenIdentifier') -> None`

### `mconet.core.domain.ConversationInputNode`

- Kind: `class`
- Signature: `(id: 'str', messages: 'MessageDocument', relations: 'tuple[TaskRelation, ...]' = (), metadata: 'Extensions' = <factory>, extensions: 'Extensions' = <factory>) -> None`
- `children` (property)
- `kind` (property)

### `mconet.core.domain.ConversationTaskBuilder`

- Kind: `class`
- Signature: `(document: 'TaskDocument') -> 'None'`
- `build` (method): `(self) -> 'ConversationTaskRequest'`
- `with_artifacts` (method): `(self, artifacts: 'ArtifactCatalog') -> 'Self'`
- `with_extensions` (method): `(self, extensions: 'Extensions') -> 'Self'`
- `with_metadata` (method): `(self, metadata: 'Extensions') -> 'Self'`

### `mconet.core.domain.ConversationTaskRequest`

- Kind: `class`
- Signature: `(document: 'TaskDocument', artifacts: 'ArtifactCatalog' = <factory>, metadata: 'Extensions' = <factory>, extensions: 'Extensions' = <factory>) -> None`
- `descriptor` (property)

### `mconet.core.domain.ConversationTaskResult`

- Kind: `class`
- Signature: `(messages: 'MessageDocument', artifacts: 'ArtifactCatalog' = <factory>, metadata: 'Extensions' = <factory>, extensions: 'Extensions' = <factory>) -> None`
- `descriptor` (property)
- `document` (property)
- `text` (property)

### `mconet.core.domain.Diagnostic`

- Kind: `class`
- Signature: `(code: 'str', severity: "Literal['info', 'warning', 'error']", phase: 'InteractionPhase', message: 'str', path: 'str | None' = None, service_id: 'OpenIdentifier | None' = None, details: 'JsonValue | None' = None) -> None`

### `mconet.core.domain.Duration`

- Kind: `class`
- Signature: `(total_nanoseconds: 'int') -> None`

### `mconet.core.domain.ErrorCategory`

- Kind: `class`
- Signature: `(id: 'OpenIdentifier') -> None`

### `mconet.core.domain.Extensions`

- Kind: `value`
- Type: `GenericAlias`

### `mconet.core.domain.GenerationParameters`

- Kind: `class`
- Signature: `(temperature: 'float | None' = None, top_p: 'float | None' = None, max_output_tokens: 'int | None' = None, stop: 'tuple[str, ...]' = (), seed: 'int | None' = None) -> None`

### `mconet.core.domain.GenerationParametersNode`

- Kind: `class`
- Signature: `(id: 'str', parameters: 'GenerationParameters', relations: 'tuple[TaskRelation, ...]' = (), metadata: 'Extensions' = <factory>, extensions: 'Extensions' = <factory>) -> None`
- `children` (property)
- `kind` (property)

### `mconet.core.domain.HeaderField`

- Kind: `class`
- Signature: `(name: 'str', value: 'str') -> None`

### `mconet.core.domain.Headers`

- Kind: `class`
- Signature: `(values: 'tuple[HeaderField, ...]' = ()) -> None`
- `get_all` (method): `(self, name: 'str') -> 'tuple[str, ...]'`

### `mconet.core.domain.InlineArtifactSource`

- Kind: `class`
- Signature: `(bytes: 'Bytes') -> None`
- `kind` (property)

### `mconet.core.domain.InteractionMode`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `id` (property)

### `mconet.core.domain.InteractionPhase`

- Kind: `class`
- Signature: `(id: 'OpenIdentifier') -> None`

### `mconet.core.domain.InteractionResourceLimits`

- Kind: `class`
- Signature: `(max_response_body_bytes: 'int | None' = None, max_streaming_error_body_bytes: 'int | None' = None, max_frame_bytes: 'int | None' = None) -> None`

### `mconet.core.domain.JsonPrimitive`

- Kind: `value`
- Type: `UnionType`

### `mconet.core.domain.JsonValue`

- Kind: `value`
- Type: `UnionType`

### `mconet.core.domain.LocalFileArtifactSource`

- Kind: `class`
- Signature: `(path: 'Path | None' = None, file_handle: 'BinaryIO | None' = None) -> None`
- `kind` (property)

### `mconet.core.domain.MediaType`

- Kind: `class`
- Signature: `(type: 'str', subtype: 'str', parameters: 'tuple[tuple[str, str], ...]' = ()) -> None`

### `mconet.core.domain.MessageContent`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `extensions` (property)
- `id` (property)
- `kind` (property)
- `metadata` (property)

### `mconet.core.domain.MessageContentKind`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `id` (property)

### `mconet.core.domain.MessageDocument`

- Kind: `class`
- Signature: `(version: 'str', purpose: "Literal['input', 'output', 'context', 'custom']", root: 'MessageGroup', metadata: 'Extensions' = <factory>, extensions: 'Extensions' = <factory>) -> None`

### `mconet.core.domain.MessageDocumentBuilder`

- Kind: `class`
- Signature: `(version: 'str', purpose: "Literal['input', 'output', 'context', 'custom']", root: 'MessageGroup') -> 'None'`
- `build` (method): `(self) -> 'MessageDocument'`
- `with_extensions` (method): `(self, extensions: 'Extensions') -> 'Self'`
- `with_metadata` (method): `(self, metadata: 'Extensions') -> 'Self'`

### `mconet.core.domain.MessageElement`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `attributes` (property)
- `extensions` (property)
- `id` (property)
- `kind` (property)
- `metadata` (property)
- `name` (property)
- `relations` (property)
- `sub_elements` (property)
- `value` (property)

### `mconet.core.domain.MessageElementKind`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `category` (property)
- `composition` (property)
- `id` (property)

### `mconet.core.domain.MessageElementValue`

- Kind: `value`
- Type: `UnionType`

### `mconet.core.domain.MessageEntry`

- Kind: `class`
- Signature: `(id: 'str', role: 'MessageRole', content: 'tuple[MessageContent, ...]', relations: 'tuple[MessageRelation, ...]' = (), metadata: 'Extensions' = <factory>, extensions: 'Extensions' = <factory>) -> None`
- `attributes` (property)
- `kind` (property)
- `name` (property)
- `sub_elements` (property)
- `value` (property)

### `mconet.core.domain.MessageEntryBuilder`

- Kind: `class`
- Signature: `(entry_id: 'str', role: 'MessageRole') -> 'None'`
- `add_content` (method): `(self, content: 'MessageContent') -> 'Self'`
- `add_relation` (method): `(self, relation: 'MessageRelation') -> 'Self'`
- `build` (method): `(self) -> 'MessageEntry'`
- `with_extensions` (method): `(self, extensions: 'Extensions') -> 'Self'`
- `with_metadata` (method): `(self, metadata: 'Extensions') -> 'Self'`

### `mconet.core.domain.MessageGroup`

- Kind: `class`
- Signature: `(id: 'str', kind: 'MessageElementKind', sub_elements: 'tuple[MessageElement, ...]', name: 'str | None' = None, attributes: 'Extensions' = <factory>, value: 'MessageElementValue | None' = None, relations: 'tuple[MessageRelation, ...]' = (), metadata: 'Extensions' = <factory>, extensions: 'Extensions' = <factory>) -> None`

### `mconet.core.domain.MessageRelation`

- Kind: `class`
- Signature: `(source: 'str', target: 'str', type: 'OpenIdentifier', metadata: 'Extensions' = <factory>) -> None`

### `mconet.core.domain.MessageRole`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `extensions` (property)
- `id` (property)
- `raw_value` (property)
- `semantic` (property)

### `mconet.core.domain.ModelDescriptor`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `description` (property)
- `display_name` (property)
- `extensions` (property)
- `family` (property)
- `metadata` (property)
- `name` (property)
- `version` (property)

### `mconet.core.domain.ModelInteractionError`

- Kind: `class`
- Signature: `(category: 'ErrorCategory', phase: 'InteractionPhase', code: 'str', message: 'str', status_code: 'int | None' = None, service_error_code: 'str | None' = None, request_id: 'str | None' = None, recovery: 'RecoveryHint | None' = None, cause: 'BaseException | None' = None) -> None`

### `mconet.core.domain.ModelOutput`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `diagnostics` (property)
- `extensions` (property)
- `id` (property)
- `protocol_state` (property)
- `resolved_model` (property)
- `result` (property)
- `status` (property)
- `stop_reason` (property)
- `target` (property)
- `usage` (property)

### `mconet.core.domain.ModelRequest`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `extensions` (property)
- `metadata` (property)
- `service_access` (property)
- `target` (property)
- `task` (property)

### `mconet.core.domain.ModelRequestBuilder`

- Kind: `class`
- Signature: `(target: 'ModelTarget', task: 'ModelTaskRequest') -> 'None'`
- `build` (method): `(self) -> 'ModelRequest'`
- `with_extensions` (method): `(self, extensions: 'Extensions') -> 'Self'`
- `with_metadata` (method): `(self, metadata: 'Extensions') -> 'Self'`
- `with_service_access` (method): `(self, service_access: 'ServiceAccess | None') -> 'Self'`

### `mconet.core.domain.ModelTarget`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `deployment_id` (property)
- `extensions` (property)
- `model` (property)
- `protocol_id` (property)
- `service_id` (property)

### `mconet.core.domain.ModelTaskRequest`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `artifacts` (property)
- `descriptor` (property)
- `document` (property)
- `extensions` (property)
- `metadata` (property)

### `mconet.core.domain.ModelTaskResult`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `artifacts` (property)
- `descriptor` (property)
- `document` (property)
- `extensions` (property)
- `metadata` (property)

### `mconet.core.domain.MonitoringMergeMode`

- Kind: `class`
- Signature: `(mode: 'OpenIdentifier') -> None`

### `mconet.core.domain.NamedModel`

- Kind: `class`
- Signature: `(name: 'str', display_name: 'str | None' = None, family: 'OpenIdentifier | None' = None, version: 'str | None' = None, description: 'str | None' = None, metadata: 'Extensions' = <factory>, extensions: 'Extensions' = <factory>) -> None`

### `mconet.core.domain.OpenIdentifier`

- Kind: `class`
- Signature: `(value: 'str') -> None`

### `mconet.core.domain.OptionalField`

- Kind: `class`
- Signature: `(is_present: 'bool', value: 'JsonValue' = None) -> None`

### `mconet.core.domain.OutputStatus`

- Kind: `class`
- Signature: `(id: 'OpenIdentifier') -> None`

### `mconet.core.domain.ParsedTaskResponse`

- Kind: `class`
- Signature: `(result: 'ModelTaskResult', status: 'OutputStatus', resolved_model: 'ModelDescriptor | None' = None, stop_reason: 'str | None' = None, usage: 'TokenUsage | None' = None, protocol_state: 'tuple[ProtocolState, ...]' = (), extensions: 'Extensions' = <factory>) -> None`

### `mconet.core.domain.ProtocolState`

- Kind: `class`
- Signature: `(service_id: 'OpenIdentifier', protocol_id: 'OpenIdentifier', state_type: 'OpenIdentifier', state_value: 'JsonValue') -> None`

### `mconet.core.domain.QueryParameter`

- Kind: `class`
- Signature: `(name: 'str', value: 'str') -> None`

### `mconet.core.domain.QueryParameters`

- Kind: `class`
- Signature: `(values: 'tuple[QueryParameter, ...]' = ()) -> None`

### `mconet.core.domain.RecoveryHint`

- Kind: `class`
- Signature: `(transient: 'bool', retry_after: 'Duration | None' = None, request_may_have_been_processed: 'bool | None' = None) -> None`

### `mconet.core.domain.ResolvedInteractionResourceLimits`

- Kind: `class`
- Signature: `(max_response_body_bytes: 'int', max_streaming_error_body_bytes: 'int', max_frame_bytes: 'int') -> None`

### `mconet.core.domain.ResolvedServiceAccess`

- Kind: `class`
- Signature: `(endpoint: 'UriValue | None', authorization: 'Authorization', headers: 'Headers', query: 'QueryParameters', api_version: 'str | None', project_id: 'str | None', tenant_id: 'str | None', extensions: 'Extensions') -> None`

### `mconet.core.domain.SchemaVersion`

- Kind: `class`
- Signature: `(value: 'str') -> None`

### `mconet.core.domain.SecretValue`

- Kind: `class`
- Signature: `(value: 'str | Bytes') -> 'None'`
- `reveal` (method): `(self, consumer: 'AuthorizedSecretConsumer') -> 'str | Bytes'`

### `mconet.core.domain.ServerStream`

- Kind: `class`
- Signature: `(events: 'AsyncIterator[ServerStreamEvent]', close: 'Callable[[], None]') -> 'None'`
- `aclose` (method): `(self) -> 'None'`

### `mconet.core.domain.ServerStreamEvent`

- Kind: `class`
- Signature: `(index: 'int', text: 'str', finish_reason: 'str | None' = None, response_id: 'str | None' = None, model: 'str | None' = None, done: 'bool' = False) -> None`
- `finished` (method): `() -> 'ServerStreamEvent'`

### `mconet.core.domain.ServiceAccess`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `api_version` (property)
- `authorization` (property)
- `endpoint` (property)
- `extensions` (property)
- `headers` (property)
- `project_id` (property)
- `query` (property)
- `tenant_id` (property)

### `mconet.core.domain.TaskDescriptor`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `extensions` (property)
- `input_schema_id` (property)
- `metadata` (property)
- `output_schema_id` (property)
- `type` (property)
- `version` (property)

### `mconet.core.domain.TaskDocument`

- Kind: `class`
- Signature: `(version: 'str', root: 'TaskGroupNode', metadata: 'Extensions' = <factory>, extensions: 'Extensions' = <factory>) -> None`

### `mconet.core.domain.TaskGroupNode`

- Kind: `class`
- Signature: `(id: 'str', kind: 'TaskNodeKind', children: 'tuple[TaskNode, ...]', relations: 'tuple[TaskRelation, ...]' = (), metadata: 'Extensions' = <factory>, extensions: 'Extensions' = <factory>) -> None`

### `mconet.core.domain.TaskNode`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `children` (property)
- `extensions` (property)
- `id` (property)
- `kind` (property)
- `metadata` (property)
- `relations` (property)

### `mconet.core.domain.TaskNodeKind`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `composition` (property)
- `id` (property)

### `mconet.core.domain.TaskRelation`

- Kind: `class`
- Signature: `(source: 'str', target: 'str', type: 'OpenIdentifier', metadata: 'Extensions' = <factory>) -> None`

### `mconet.core.domain.TextMessageContent`

- Kind: `class`
- Signature: `(id: 'str', text: 'str', metadata: 'Extensions' = <factory>, extensions: 'Extensions' = <factory>) -> None`
- `kind` (property)

### `mconet.core.domain.Timestamp`

- Kind: `class`
- Signature: `(epoch_seconds: 'int', nanosecond: 'int' = 0) -> None`

### `mconet.core.domain.TokenUsage`

- Kind: `class`
- Signature: `(input_tokens: 'int | None' = None, output_tokens: 'int | None' = None, total_tokens: 'int | None' = None, extensions: 'Extensions' = <factory>) -> None`

### `mconet.core.domain.UriArtifactSource`

- Kind: `class`
- Signature: `(uri: 'UriValue', authorization: 'Authorization | None' = None) -> None`
- `kind` (property)

### `mconet.core.domain.UriValue`

- Kind: `class`
- Signature: `(value: 'str', is_absolute: 'bool') -> None`

### `mconet.core.domain.default_compatibility_policy`

- Kind: `function`
- Signature: `() -> 'CompatibilityPolicy'`

### `mconet.core.domain.parse_media_type`

- Kind: `function`
- Signature: `(value: 'str') -> 'MediaType'`

### `mconet.core.domain.parse_timestamp`

- Kind: `function`
- Signature: `(value: 'str') -> 'Timestamp'`

### `mconet.core.domain.preserve_unknown_fields`

- Kind: `function`
- Signature: `(fields: 'Mapping[str, JsonValue]', known_field_names: 'Collection[str]') -> 'Extensions'`

### `mconet.core.domain.resolve_artifact_reference`

- Kind: `function`
- Signature: `(reference: 'ArtifactReference', catalog: 'ArtifactCatalog') -> 'Artifact'`

### `mconet.core.domain.resolve_resource_limits`

- Kind: `function`
- Signature: `(sdk_defaults: 'ResolvedInteractionResourceLimits', *, client_limits: 'InteractionResourceLimits | None' = None, interaction_limits: 'InteractionResourceLimits | None' = None) -> 'ResolvedInteractionResourceLimits'`

### `mconet.core.domain.restore_preserved_fields`

- Kind: `function`
- Signature: `(known_fields: 'Mapping[str, JsonValue]', preserved_fields: 'Extensions') -> 'Extensions'`

### `mconet.core.domain.serialize_optional_fields`

- Kind: `function`
- Signature: `(fields: 'Mapping[str, OptionalField]') -> 'Extensions'`

### `mconet.core.domain.serialize_timestamp`

- Kind: `function`
- Signature: `(timestamp: 'Timestamp', precision: "Literal['seconds', 'milliseconds', 'microseconds', 'nanoseconds']" = 'nanoseconds') -> 'str'`

### `mconet.core.domain.validate_artifact`

- Kind: `function`
- Signature: `(artifact: 'Artifact') -> 'Artifact'`

### `mconet.core.domain.validate_artifact_catalog`

- Kind: `function`
- Signature: `(catalog: 'ArtifactCatalog') -> 'ArtifactCatalog'`

### `mconet.core.domain.validate_conversation_input_node`

- Kind: `function`
- Signature: `(node: 'ConversationInputNode') -> 'ConversationInputNode'`

### `mconet.core.domain.validate_conversation_task_node_scope`

- Kind: `function`
- Signature: `(request: 'ConversationTaskRequest') -> 'ConversationTaskRequest'`

### `mconet.core.domain.validate_conversation_task_request`

- Kind: `function`
- Signature: `(request: 'ConversationTaskRequest') -> 'ConversationTaskRequest'`

### `mconet.core.domain.validate_conversation_task_type`

- Kind: `function`
- Signature: `(task: 'ModelTaskRequest') -> 'ModelTaskRequest'`

### `mconet.core.domain.validate_duration`

- Kind: `function`
- Signature: `(value: 'int', unit: "Literal['seconds', 'milliseconds', 'microseconds', 'nanoseconds']" = 'nanoseconds') -> 'Duration'`

### `mconet.core.domain.validate_empty_artifact_catalog_scope`

- Kind: `function`
- Signature: `(catalog: 'ArtifactCatalog') -> 'ArtifactCatalog'`

### `mconet.core.domain.validate_generation_parameters`

- Kind: `function`
- Signature: `(parameters: 'GenerationParameters') -> 'GenerationParameters'`

### `mconet.core.domain.validate_generation_parameters_node`

- Kind: `function`
- Signature: `(node: 'GenerationParametersNode') -> 'GenerationParametersNode'`

### `mconet.core.domain.validate_json_value_numbers`

- Kind: `function`
- Signature: `(value: 'JsonValue') -> 'JsonValue'`

### `mconet.core.domain.validate_message_document`

- Kind: `function`
- Signature: `(document: 'MessageDocument') -> 'MessageDocument'`

### `mconet.core.domain.validate_message_entry`

- Kind: `function`
- Signature: `(entry: 'MessageEntry') -> 'MessageEntry'`

### `mconet.core.domain.validate_message_group`

- Kind: `function`
- Signature: `(group: 'MessageGroup') -> 'MessageGroup'`

### `mconet.core.domain.validate_message_role`

- Kind: `function`
- Signature: `(role: 'MessageRole') -> 'MessageRole'`

### `mconet.core.domain.validate_model_descriptor`

- Kind: `function`
- Signature: `(descriptor: 'ModelDescriptor') -> 'ModelDescriptor'`

### `mconet.core.domain.validate_model_request`

- Kind: `function`
- Signature: `(request: 'ModelRequest') -> 'ModelRequest'`

### `mconet.core.domain.validate_model_target`

- Kind: `function`
- Signature: `(target: 'ModelTarget') -> 'ModelTarget'`

### `mconet.core.domain.validate_open_identifier`

- Kind: `function`
- Signature: `(identifier: 'OpenIdentifier') -> 'OpenIdentifier'`

### `mconet.core.domain.validate_parsed_task_response`

- Kind: `function`
- Signature: `(response: 'ParsedTaskResponse') -> 'ParsedTaskResponse'`

### `mconet.core.domain.validate_resource_limits`

- Kind: `function`
- Signature: `(limits: 'InteractionResourceLimits | ResolvedInteractionResourceLimits') -> 'InteractionResourceLimits | ResolvedInteractionResourceLimits'`

### `mconet.core.domain.validate_server_stream_interaction_mode`

- Kind: `function`
- Signature: `(request: 'ModelRequest', mode: 'InteractionMode') -> 'InteractionMode'`

### `mconet.core.domain.validate_service_access`

- Kind: `function`
- Signature: `(access: 'ServiceAccess') -> 'ServiceAccess'`

### `mconet.core.domain.validate_task_descriptor`

- Kind: `function`
- Signature: `(descriptor: 'TaskDescriptor') -> 'TaskDescriptor'`

### `mconet.core.domain.validate_task_document`

- Kind: `function`
- Signature: `(document: 'TaskDocument') -> 'TaskDocument'`

### `mconet.core.domain.validate_task_node`

- Kind: `function`
- Signature: `(node: 'TaskNode') -> 'TaskNode'`

### `mconet.core.domain.validate_text_message_content`

- Kind: `function`
- Signature: `(content: 'TextMessageContent', *, maximum_code_points: 'int | None' = None) -> 'TextMessageContent'`

### `mconet.core.domain.validate_text_message_content_scope`

- Kind: `function`
- Signature: `(document: 'MessageDocument') -> 'MessageDocument'`

### `mconet.core.domain.validate_unary_interaction_mode`

- Kind: `function`
- Signature: `(request: 'ModelRequest', mode: 'InteractionMode') -> 'InteractionMode'`

### `mconet.core.domain.validate_uri`

- Kind: `function`
- Signature: `(uri: 'UriValue') -> 'UriValue'`

### `mconet.core.spi.AuthorizationContext`

- Kind: `class`
- Signature: `(interaction_id: 'str', target: 'ModelTarget', endpoint: 'UriValue', transport_kind: 'OpenIdentifier', timestamp: 'Timestamp', body_signing_mode: 'BodySigningMode', cancellation: 'CancellationSignal | None' = None, extensions: 'Extensions' = <factory>) -> None`

### `mconet.core.spi.AuthorizationHandler`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `apply` (method): `(self, authorization: 'Authorization', context: 'AuthorizationContext', request: 'MutableTransportRequest') -> 'None'`
- `descriptor` (property)
- `supports` (method): `(self, authorization: 'Authorization', body_signing_requirement: 'BodySigningRequirement') -> 'frozenset[BodySigningMode]'`

### `mconet.core.spi.AuthorizationHandlerResolver`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `descriptor` (property)
- `resolve` (method): `(self, authorization: 'Authorization', body_signing_requirement: 'BodySigningRequirement', handlers: 'tuple[AuthorizationHandler, ...]') -> 'ResolvedAuthorizationHandler'`

### `mconet.core.spi.BodySigningMode`

- Kind: `value`
- Type: `_LiteralGenericAlias`

### `mconet.core.spi.BodySigningRequirement`

- Kind: `class`
- Signature: `(required: 'bool' = False, acceptable_modes: 'tuple[BodySigningMode, ...]' = ('none',), digest_algorithms: 'frozenset[OpenIdentifier]' = frozenset(), max_buffer_bytes: 'int | None' = None) -> None`

### `mconet.core.spi.CapabilityContext`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `execution_plan` (property)
- `extensions` (property)
- `interaction_mode` (property)
- `selected_components` (property)
- `target` (property)
- `task` (property)

### `mconet.core.spi.CapabilityRequirement`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `capability_id` (property)
- `constraints` (property)
- `extensions` (property)
- `required` (property)
- `source_path` (property)

### `mconet.core.spi.CapabilityResolution`

- Kind: `class`
- Signature: `(satisfied: 'tuple[SatisfiedCapability, ...]' = (), optional_unsupported: 'tuple[CapabilityRequirement, ...]' = (), diagnostics: 'tuple[Diagnostic, ...]' = ()) -> None`

### `mconet.core.spi.CloseableRuntimeComponent`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `close` (method): `(self) -> 'None'`
- `descriptor` (property)

### `mconet.core.spi.ComponentDescriptor`

- Kind: `class`
- Signature: `(name: 'str', version: 'str', source: "Literal['builtin', 'plugin', 'application']", type_contract: 'ComponentTypeContract | None' = None, capabilities: 'frozenset[OpenIdentifier]' = frozenset()) -> None`

### `mconet.core.spi.ComponentOwnership`

- Kind: `class`
- Signature: `(id: 'OpenIdentifier') -> None`

### `mconet.core.spi.ComponentRole`

- Kind: `class`
- Signature: `(id: 'OpenIdentifier') -> None`

### `mconet.core.spi.ComponentSelectionResolution`

- Kind: `class`
- Signature: `(components: 'tuple[SelectedComponent, ...]' = ()) -> None`

### `mconet.core.spi.ComponentTypeContract`

- Kind: `class`
- Signature: `(inputs: 'tuple[ComponentTypePort, ...]' = (), outputs: 'tuple[ComponentTypePort, ...]' = ()) -> None`

### `mconet.core.spi.ComponentTypePort`

- Kind: `class`
- Signature: `(name: 'str', type_id: 'OpenIdentifier', schema_id: 'str | None' = None, media_type: 'MediaType | None' = None) -> None`

### `mconet.core.spi.CredentialSource`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `resolve` (method): `(self, context: 'AuthorizationContext') -> 'CredentialValue'`

### `mconet.core.spi.CredentialValue`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `kind` (property)
- `reveal` (method): `(self, consumer: 'AuthorizedSecretConsumer') -> 'object'`

### `mconet.core.spi.DecoderSelection`

- Kind: `class`
- Signature: `(media_type: 'MediaType | None' = None, schema_id: 'str | None' = None) -> None`

### `mconet.core.spi.EncoderSelection`

- Kind: `class`
- Signature: `(media_type: 'MediaType | None' = None, schema_id: 'str | None' = None) -> None`

### `mconet.core.spi.ErasedRuntimeValue`

- Kind: `class`
- Signature: `(type_id: 'OpenIdentifier', value: 'object', schema_id: 'str | None' = None) -> None`
- `value_as` (method): `(self, expected_type: 'type[_ValueT]') -> '_ValueT'`

### `mconet.core.spi.InteractionCapability`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `attributes` (property)
- `extensions` (property)
- `id` (property)
- `version` (property)

### `mconet.core.spi.InteractionExecutionComponents`

- Kind: `class`
- Signature: `(integration_plan: 'ModelIntegrationPlan', component_selection: 'ComponentSelectionResolution', resource_limits: 'ResolvedInteractionResourceLimits', task_protocol_adapter: 'TaskProtocolAdapter', service_access_resolver: 'ServiceAccessResolver', payload_encoder: 'PayloadEncoder', success_payload_decoder: 'PayloadDecoder', error_payload_decoder: 'PayloadDecoder', transport: 'Transport', authorization_handler_resolver: 'AuthorizationHandlerResolver', authorization_handlers: 'tuple[AuthorizationHandler, ...]', capability_resolution: 'CapabilityResolution') -> None`

### `mconet.core.spi.InteractionMonitor`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `descriptor` (property)
- `observed_events` (property)
- `on_event` (method): `(self, event: 'MonitoringEvent') -> 'None'`

### `mconet.core.spi.InteractionOptions`

- Kind: `class`
- Signature: `(components: 'RuntimeComponents | None' = None, service_access_override: 'ServiceAccess | None' = None, compatibility_policy: 'CompatibilityPolicy | None' = None, resource_limits: 'InteractionResourceLimits | None' = None, monitoring_options: 'MonitoringOptions | None' = None, cancellation_signal: 'CancellationSignal | None' = None, include_raw_response: 'bool' = False) -> None`

### `mconet.core.spi.MessageMappingResult`

- Kind: `class`
- Signature: `(document: 'MessageDocument', artifacts: 'ArtifactCatalog') -> None`

### `mconet.core.spi.MessageRequestMapper`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `descriptor` (property)
- `map_request` (method): `(self, document: 'MessageDocument') -> 'ErasedRuntimeValue'`

### `mconet.core.spi.MessageResponseMapper`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `descriptor` (property)
- `map_response` (method): `(self, fragment: 'ErasedRuntimeValue') -> 'MessageMappingResult'`

### `mconet.core.spi.ModelClientConfiguration`

- Kind: `class`
- Signature: `(default_target: 'ModelTarget | None' = None, default_service_access: 'ServiceAccess | None' = None, default_compatibility_policy: 'CompatibilityPolicy | None' = None, default_resource_limits: 'InteractionResourceLimits | None' = None, components: 'RuntimeComponents | None' = None, monitoring_defaults: 'MonitoringOptions | None' = None) -> None`

### `mconet.core.spi.ModelIntegrationMatch`

- Kind: `class`
- Signature: `(target: 'ModelTargetMatch', task: 'TaskMatch') -> None`

### `mconet.core.spi.ModelIntegrationPlan`

- Kind: `class`
- Signature: `(source: "Literal['direct_adapter', 'resolved_binding']", binding_id: 'str | None', binding_version: 'str | None', match: 'ModelIntegrationMatch | None', task_protocol_adapter: 'RuntimeComponent', authorization_handlers: 'tuple[RuntimeComponent, ...]' = (), default_service_access: 'ServiceAccess | None' = None, payload_encoders: 'tuple[RuntimeComponent, ...]' = (), payload_decoders: 'tuple[RuntimeComponent, ...]' = (), transports: 'tuple[RuntimeComponent, ...]' = (), extensions: 'Mapping[str, object]' = <factory>) -> None`

### `mconet.core.spi.ModelIntegrationResolver`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `descriptor` (property)
- `resolve` (method): `(self, target: 'ModelTarget', task: 'TaskDescriptor', mode: 'InteractionMode', policy: 'CompatibilityPolicy') -> 'ModelIntegrationPlan'`

### `mconet.core.spi.ModelInteractor`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `interact` (method): `(self, request: 'ModelRequest', options: 'InteractionOptions') -> 'ModelOutput'`

### `mconet.core.spi.ModelTargetMatch`

- Kind: `class`
- Signature: `(matched: 'bool', score: 'int', diagnostics: 'tuple[Diagnostic, ...]' = ()) -> None`

### `mconet.core.spi.MonitoringEvent`

- Kind: `class`
- Signature: `(id: 'str', type: 'OpenIdentifier', interaction_id: 'str', trace_id: 'str | None', timestamp: 'Timestamp', payload: 'JsonValue', metadata: 'Extensions') -> None`

### `mconet.core.spi.MonitoringOptions`

- Kind: `class`
- Signature: `(monitors: 'tuple[InteractionMonitor, ...]' = (), merge_mode: 'MonitoringMergeMode' = MonitoringMergeMode(mode=OpenIdentifier(value='append')), capture_request_body: 'bool' = False, capture_response_body: 'bool' = False, max_captured_body_bytes: 'int | None' = None) -> None`

### `mconet.core.spi.MutableTransportRequest`

- Kind: `class`
- Signature: `(method: 'str', url: 'UriValue', headers: 'Headers', query: 'QueryParameters', body: 'TransportBody') -> 'None'`
- `body` (property)
- `freeze` (method): `(self) -> 'TransportRequest'`
- `headers` (property)
- `is_frozen` (property)
- `method` (property)
- `query` (property)
- `replace_body` (method): `(self, value: 'TransportBody') -> 'None'`
- `replace_headers` (method): `(self, value: 'Headers') -> 'None'`
- `replace_query` (method): `(self, value: 'QueryParameters') -> 'None'`
- `replace_url` (method): `(self, value: 'UriValue') -> 'None'`
- `url` (property)

### `mconet.core.spi.PayloadDecoder`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `decode` (method): `(self, raw_data: 'Bytes') -> 'ErasedRuntimeValue'`
- `descriptor` (property)

### `mconet.core.spi.PayloadEncoder`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `descriptor` (property)
- `encode` (method): `(self, payload: 'ErasedRuntimeValue') -> 'TransportBody'`

### `mconet.core.spi.PlannedComponentSelection`

- Kind: `class`
- Signature: `(role: 'ComponentRole', required: 'bool', required_capabilities: 'frozenset[OpenIdentifier]' = frozenset()) -> None`

### `mconet.core.spi.ProtocolExecutionPlan`

- Kind: `class`
- Signature: `(transport_plan: 'TransportRequestPlan', payload_encoder: 'EncoderSelection', success_decoder: 'DecoderSelection', error_decoder: 'DecoderSelection', transport: 'TransportSelection', mode_components: 'tuple[PlannedComponentSelection, ...]' = (), type_contract: 'ComponentTypeContract' = <factory>, extensions: 'Mapping[str, object]' = <factory>) -> None`

### `mconet.core.spi.ProtocolRequestPlan`

- Kind: `class`
- Signature: `(payload: 'ErasedRuntimeValue', execution_plan: 'ProtocolExecutionPlan') -> None`

### `mconet.core.spi.RawResponseSnapshot`

- Kind: `class`
- Signature: `(body: 'Bytes', metadata: 'TransportResponseMetadata', body_omitted: 'bool' = False) -> None`

### `mconet.core.spi.ResolvedAuthorizationHandler`

- Kind: `class`
- Signature: `(handler: 'AuthorizationHandler', body_signing_mode: 'BodySigningMode') -> None`

### `mconet.core.spi.RuntimeComponent`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `descriptor` (property)

### `mconet.core.spi.RuntimeComponents`

- Kind: `class`
- Signature: `(model_integration_resolver: 'ModelIntegrationResolver | None' = None, task_protocol_adapter: 'TaskProtocolAdapter | None' = None, service_access_resolver: 'ServiceAccessResolver | None' = None, payload_encoder: 'PayloadEncoder | None' = None, success_payload_decoder: 'PayloadDecoder | None' = None, error_payload_decoder: 'PayloadDecoder | None' = None, transport: 'Transport | None' = None, authorization_handler_resolver: 'AuthorizationHandlerResolver | None' = None, authorization_handlers: 'tuple[AuthorizationHandler, ...]' = ()) -> None`

### `mconet.core.spi.SatisfiedCapability`

- Kind: `class`
- Signature: `(requirement: 'CapabilityRequirement', capability: 'InteractionCapability', provider_id: 'str') -> None`

### `mconet.core.spi.SelectedComponent`

- Kind: `class`
- Signature: `(role: 'ComponentRole', component: 'RuntimeComponent', descriptor: 'ComponentDescriptor') -> None`

### `mconet.core.spi.ServiceAccessResolver`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `descriptor` (property)
- `resolve` (method): `(self, interaction_override: 'ServiceAccess | None', request_service_access: 'ServiceAccess | None', client_default_service_access: 'ServiceAccess | None', protocol_default_service_access: 'ServiceAccess | None') -> 'ResolvedServiceAccess'`

### `mconet.core.spi.TaskMatch`

- Kind: `class`
- Signature: `(matched: 'bool', score: 'int', diagnostics: 'tuple[Diagnostic, ...]' = ()) -> None`

### `mconet.core.spi.TaskProtocolAdapter`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `build_request` (method): `(self, request: 'ModelRequest', plan: 'ProtocolExecutionPlan') -> 'ProtocolRequestPlan'`
- `descriptor` (property)
- `parse_error` (method): `(self, error: 'ErasedRuntimeValue', metadata: 'TransportResponseMetadata') -> 'ModelInteractionError | None'`
- `parse_response` (method): `(self, response: 'ErasedRuntimeValue') -> 'ParsedTaskResponse'`
- `prepare_plan` (method): `(self, request: 'ModelRequest', access: 'ResolvedServiceAccess', mode: 'InteractionMode') -> 'ProtocolExecutionPlan'`
- `supports` (method): `(self, target: 'ModelTarget', task: 'TaskDescriptor', mode: 'InteractionMode') -> 'bool'`

### `mconet.core.spi.Transport`

- Kind: `class`
- Signature: `(*args, **kwargs)`
- `descriptor` (property)
- `send` (method): `(self, request: 'TransportRequest', context: 'TransportContext') -> 'TransportResponse'`

### `mconet.core.spi.TransportBody`

- Kind: `class`
- Signature: `(bytes: 'Bytes', media_type: 'MediaType') -> None`

### `mconet.core.spi.TransportContext`

- Kind: `class`
- Signature: `(interaction_id: 'str', resource_limits: 'ResolvedInteractionResourceLimits', deadline: 'Timestamp | None' = None, cancellation: 'CancellationSignal | None' = None, extensions: 'Extensions' = <factory>) -> None`

### `mconet.core.spi.TransportOutcome`

- Kind: `class`
- Signature: `(id: 'OpenIdentifier') -> None`

### `mconet.core.spi.TransportRequest`

- Kind: `class`
- Signature: `(method: 'str', url: 'UriValue', headers: 'Headers', query: 'QueryParameters', body: 'TransportBody') -> None`

### `mconet.core.spi.TransportRequestPlan`

- Kind: `class`
- Signature: `(endpoint: 'UriValue', path: 'str', method: 'str', headers: 'Headers', query: 'QueryParameters', authorization: 'Authorization', body_signing_requirement: 'BodySigningRequirement', transport_extensions: 'Mapping[str, object]' = <factory>) -> None`

### `mconet.core.spi.TransportResponse`

- Kind: `class`
- Signature: `(response_metadata: 'TransportResponseMetadata', body: 'Bytes') -> None`

### `mconet.core.spi.TransportResponseMetadata`

- Kind: `class`
- Signature: `(outcome: 'TransportOutcome', headers: 'Headers', status_code: 'int | None' = None, protocol_status_code: 'str | None' = None, trailers: 'Headers | None' = None, media_type: 'MediaType | None' = None, request_id: 'str | None' = None, extensions: 'Extensions' = <factory>) -> None`

### `mconet.core.spi.TransportSelection`

- Kind: `class`
- Signature: `(transport_kind: 'OpenIdentifier | None' = None, required_capabilities: 'frozenset[OpenIdentifier]' = frozenset()) -> None`

### `mconet.integration.openai_compatible.OPENAI_CHAT_COMPLETIONS_PROTOCOL_ID`

- Kind: `value`
- Type: `OpenIdentifier`

### `mconet.integration.openai_compatible.OpenAIChatCompletionsAdapter`

- Kind: `class`
- Signature: `(compatibility_policy: 'CompatibilityPolicy | None' = None) -> 'None'`
- `build_request` (method): `(self, request: 'ModelRequest', plan: 'ProtocolExecutionPlan') -> 'ProtocolRequestPlan'`
- `compatibility_policy` (property)
- `descriptor` (property)
- `parse_error` (method): `(self, error: 'ErasedRuntimeValue', metadata: 'TransportResponseMetadata') -> 'ModelInteractionError | None'`
- `parse_response` (method): `(self, response: 'ErasedRuntimeValue') -> 'ParsedTaskResponse'`
- `prepare_plan` (method): `(self, request: 'ModelRequest', access: 'ResolvedServiceAccess', mode: 'InteractionMode') -> 'ProtocolExecutionPlan'`
- `supports` (method): `(self, target: 'ModelTarget', task: 'TaskDescriptor', mode: 'InteractionMode') -> 'bool'`

### `mconet.testing.AdapterContractSuite`

- Kind: `class`
- Signature: `(adapter: 'TaskProtocolAdapter') -> 'None'`
- `assert_build_request` (method): `(self, request: 'ModelRequest', plan: 'ProtocolExecutionPlan', *, assertion: 'Callable[[ProtocolRequestPlan], None]') -> 'None'`
- `assert_parse_error` (method): `(self, error: 'ErasedRuntimeValue', metadata: 'TransportResponseMetadata', *, assertion: 'Callable[[ModelInteractionError | None], None]') -> 'None'`
- `assert_parse_response` (method): `(self, response: 'ErasedRuntimeValue', *, assertion: 'Callable[[ParsedTaskResponse], None]') -> 'None'`
- `assert_prepare_plan` (method): `(self, request: 'ModelRequest', access: 'ResolvedServiceAccess', mode: 'InteractionMode', *, assertion: 'Callable[[ProtocolExecutionPlan], None]') -> 'None'`
- `assert_supports` (method): `(self, target: 'ModelTarget', task: 'TaskDescriptor', mode: 'InteractionMode', *, expected: 'bool') -> 'None'`

### `mconet.testing.AuthorizationHandlerContractSuite`

- Kind: `class`
- Signature: `(handler: 'AuthorizationHandler') -> 'None'`
- `assert_apply` (method): `(self, authorization: 'Authorization', context: 'AuthorizationContext', request: 'MutableTransportRequest', *, assertion: 'Callable[[MutableTransportRequest], None]') -> 'None'`
- `assert_apply_failure` (method): `(self, authorization: 'Authorization', context: 'AuthorizationContext', request: 'MutableTransportRequest', *, assertion: 'Callable[[BaseException], None]') -> 'None'`
- `assert_supports` (method): `(self, authorization: 'Authorization', body_signing_requirement: 'BodySigningRequirement', *, assertion: 'Callable[[frozenset[BodySigningMode]], None]') -> 'None'`

### `mconet.testing.AuthorizationHandlerResolverContractSuite`

- Kind: `class`
- Signature: `(resolver: 'AuthorizationHandlerResolver') -> 'None'`
- `assert_ambiguous_match` (method): `(self, authorization: 'Authorization', body_signing_requirement: 'BodySigningRequirement', handlers: 'tuple[AuthorizationHandler, ...]', *, assertion: 'Callable[[BaseException], None]') -> 'None'`
- `assert_no_match` (method): `(self, authorization: 'Authorization', body_signing_requirement: 'BodySigningRequirement', handlers: 'tuple[AuthorizationHandler, ...]', *, assertion: 'Callable[[BaseException], None]') -> 'None'`
- `assert_unique_match` (method): `(self, authorization: 'Authorization', body_signing_requirement: 'BodySigningRequirement', handlers: 'tuple[AuthorizationHandler, ...]', *, assertion: 'Callable[[ResolvedAuthorizationHandler], None]') -> 'None'`

### `mconet.testing.ComponentCallRecorder`

- Kind: `class`
- Signature: `() -> 'None'`
- `calls` (property)
- `record` (method): `(self, call: 'str') -> 'None'`

### `mconet.testing.ContractCase`

- Kind: `class`
- Signature: `(component: 'str', fixture: 'str') -> None`

### `mconet.testing.ControllableCancellationSignal`

- Kind: `class`
- Signature: `() -> 'None'`
- `cancel` (method): `(self, reason: 'str | None' = None) -> 'None'`
- `is_cancelled` (property)
- `reason` (property)
- `subscribe` (method): `(self, callback: 'Callable[[str | None], None]') -> 'Callable[[], None]'`

### `mconet.testing.DeterministicIdGenerator`

- Kind: `class`
- Signature: `() -> 'None'`
- `next_id` (method): `(self) -> 'str'`

### `mconet.testing.ErrorPayloadDecoderContractSuite`

- Kind: `class`
- Signature: `(decoder: 'PayloadDecoder') -> 'None'`
- `assert_decode` (method): `(self, raw_data: 'Bytes', *, assertion: 'Callable[[ErasedRuntimeValue], None]') -> 'None'`
- `assert_decode_failure` (method): `(self, raw_data: 'Bytes', *, assertion: 'Callable[[BaseException], None]') -> 'None'`

### `mconet.testing.FakeClock`

- Kind: `class`
- Signature: `(initial: 'Timestamp') -> 'None'`
- `advance` (method): `(self, duration: 'Duration') -> 'None'`
- `now` (method): `(self) -> 'Timestamp'`

### `mconet.testing.FaultInjectionHarness`

- Kind: `class`
- Signature: `(actions: 'Mapping[str, Sequence[Callable[[], object]]]') -> 'None'`
- `calls` (property)
- `trigger` (method): `(self, point: 'str') -> 'object'`

### `mconet.testing.FixtureLoader`

- Kind: `class`
- Signature: `(root: 'Path') -> 'None'`
- `load` (method): `(self, resource: 'str') -> 'JsonValue'`
- `profile` (property)
- `resources` (property)

### `mconet.testing.MockHttpAbort`

- Kind: `class`
- Signature: `(point: 'str') -> None`

### `mconet.testing.MockHttpRequest`

- Kind: `class`
- Signature: `(method: 'str', target: 'str', http_version: 'str', headers: 'Headers', body: 'Bytes') -> None`

### `mconet.testing.MockHttpResponseScript`

- Kind: `class`
- Signature: `(status_code: 'int', headers: 'Headers' = Headers(values=()), body: 'bytes' = b'', delay: 'Duration' = Duration(total_nanoseconds=0), abort: 'MockHttpAbort | None' = None, body_prefix_length: 'int | None' = None) -> None`

### `mconet.testing.MockHttpServer`

- Kind: `class`
- Signature: `(scripts: 'Sequence[MockHttpResponseScript]') -> 'None'`
- `close` (method): `(self) -> 'None'`
- `host` (property)
- `port` (property)
- `requests` (property)
- `uri` (property)

### `mconet.testing.MockTransport`

- Kind: `class`
- Signature: `(descriptor: 'ComponentDescriptor', response: 'TransportResponse', *, error: 'BaseException | None' = None, delay: 'Duration' = Duration(total_nanoseconds=0)) -> 'None'`
- `descriptor` (property)
- `send` (method): `(self, request: 'TransportRequest', context: 'TransportContext') -> 'TransportResponse'`

### `mconet.testing.ModelIntegrationResolverContractSuite`

- Kind: `class`
- Signature: `(resolver: 'ModelIntegrationResolver') -> 'None'`
- `assert_ambiguous` (method): `(self, target: 'ModelTarget', task: 'TaskDescriptor', mode: 'InteractionMode', policy: 'CompatibilityPolicy', *, assertion: 'Callable[[BaseException], None]') -> 'None'`
- `assert_direct` (method): `(self, target: 'ModelTarget', task: 'TaskDescriptor', mode: 'InteractionMode', policy: 'CompatibilityPolicy', *, assertion: 'Callable[[ModelIntegrationPlan], None]') -> 'None'`
- `assert_not_found` (method): `(self, target: 'ModelTarget', task: 'TaskDescriptor', mode: 'InteractionMode', policy: 'CompatibilityPolicy', *, assertion: 'Callable[[BaseException], None]') -> 'None'`
- `assert_resolved` (method): `(self, target: 'ModelTarget', task: 'TaskDescriptor', mode: 'InteractionMode', policy: 'CompatibilityPolicy', *, assertion: 'Callable[[ModelIntegrationPlan], None]') -> 'None'`

### `mconet.testing.MonitorContractSuite`

- Kind: `class`
- Signature: `(monitor: 'InteractionMonitor') -> 'None'`
- `assert_failure_isolated` (method): `(self, event: 'MonitoringEvent', *, secret: 'str', assertion: 'Callable[[BaseException], None]') -> 'None'`
- `assert_observe` (method): `(self, event: 'MonitoringEvent', *, secret: 'str', assertion: 'Callable[[MonitoringEvent], None]') -> 'None'`
- `assert_observed_events` (method): `(self, *, assertion: 'Callable[[frozenset[OpenIdentifier] | None], None]') -> 'None'`

### `mconet.testing.PayloadEncoderContractSuite`

- Kind: `class`
- Signature: `(encoder: 'PayloadEncoder') -> 'None'`
- `assert_encode` (method): `(self, payload: 'ErasedRuntimeValue', *, assertion: 'Callable[[TransportBody], None]') -> 'None'`
- `assert_encode_failure` (method): `(self, payload: 'ErasedRuntimeValue', *, assertion: 'Callable[[BaseException], None]') -> 'None'`

### `mconet.testing.RecordingTransport`

- Kind: `class`
- Signature: `(transport: 'Transport') -> 'None'`
- `calls` (property)
- `descriptor` (property)
- `send` (method): `(self, request: 'TransportRequest', context: 'TransportContext') -> 'TransportResponse'`

### `mconet.testing.SchemaLoader`

- Kind: `class`
- Signature: `(schemas: 'Mapping[OpenIdentifier, JsonValue]') -> 'None'`
- `load` (method): `(self, identifier: 'OpenIdentifier') -> 'dict[str, JsonValue]'`

### `mconet.testing.SchemaValidationIssue`

- Kind: `class`
- Signature: `(path: 'str', keyword: 'str', message: 'str') -> None`

### `mconet.testing.SchemaValidatorAdapter`

- Kind: `class`
- Signature: `(loader: 'SchemaLoader') -> 'None'`
- `validate` (method): `(self, schema_id: 'OpenIdentifier', instance: 'JsonValue') -> 'tuple[SchemaValidationIssue, ...]'`

### `mconet.testing.SecretContractSuite`

- Kind: `class`
- Signature: `()`
- `assert_exception_safe` (method): `(self, secret: 'str', error: 'BaseException') -> 'None'`
- `assert_log_safe` (method): `(self, secret: 'str', *entries: 'object') -> 'None'`
- `assert_serialization_safe` (method): `(self, secret: 'str', serialized: 'object') -> 'None'`
- `assert_snapshot_safe` (method): `(self, secret: 'str', snapshot: 'object') -> 'None'`

### `mconet.testing.SecretScanner`

- Kind: `class`
- Signature: `()`
- `assert_absent` (method): `(self, secret: 'str', *carriers: 'object') -> 'None'`

### `mconet.testing.ServiceAccessResolverContractSuite`

- Kind: `class`
- Signature: `(resolver: 'ServiceAccessResolver') -> 'None'`
- `assert_resolve` (method): `(self, interaction_override: 'ServiceAccess | None', request_service_access: 'ServiceAccess | None', client_default_service_access: 'ServiceAccess | None', protocol_default_service_access: 'ServiceAccess | None', *, assertion: 'Callable[[ResolvedServiceAccess], None]') -> 'None'`
- `assert_resolve_failure` (method): `(self, interaction_override: 'ServiceAccess | None', request_service_access: 'ServiceAccess | None', client_default_service_access: 'ServiceAccess | None', protocol_default_service_access: 'ServiceAccess | None', *, assertion: 'Callable[[BaseException], None]') -> 'None'`

### `mconet.testing.SnapshotComparator`

- Kind: `class`
- Signature: `()`
- `compare` (method): `(self, actual: 'JsonValue', expected: 'JsonValue') -> 'bool'`

### `mconet.testing.StubAuthorizationHandler`

- Kind: `class`
- Signature: `(descriptor: 'ComponentDescriptor', supported_modes: 'frozenset[BodySigningMode]', *, apply_error: 'BaseException | None' = None) -> 'None'`
- `apply` (method): `(self, authorization: 'Authorization', context: 'AuthorizationContext', request: 'MutableTransportRequest') -> 'None'`
- `descriptor` (property)
- `requests_after` (property)
- `requests_before` (property)
- `supports` (method): `(self, authorization: 'Authorization', body_signing_requirement: 'BodySigningRequirement') -> 'frozenset[BodySigningMode]'`

### `mconet.testing.StubAuthorizationHandlerResolver`

- Kind: `class`
- Signature: `(descriptor: 'ComponentDescriptor', result: 'ResolvedAuthorizationHandler', *, error: 'BaseException | None' = None) -> 'None'`
- `descriptor` (property)
- `resolve` (method): `(self, authorization: 'Authorization', body_signing_requirement: 'BodySigningRequirement', handlers: 'tuple[AuthorizationHandler, ...]') -> 'ResolvedAuthorizationHandler'`

### `mconet.testing.StubInteractionMonitor`

- Kind: `class`
- Signature: `(descriptor: 'ComponentDescriptor', observed_events: 'frozenset[OpenIdentifier] | None', *, error: 'BaseException | None' = None) -> 'None'`
- `descriptor` (property)
- `events` (property)
- `observed_events` (property)
- `on_event` (method): `(self, event: 'MonitoringEvent') -> 'None'`

### `mconet.testing.StubModelIntegrationResolver`

- Kind: `class`
- Signature: `(descriptor: 'ComponentDescriptor', result: 'ModelIntegrationPlan', *, error: 'BaseException | None' = None) -> 'None'`
- `descriptor` (property)
- `resolve` (method): `(self, target: 'ModelTarget', task: 'TaskDescriptor', mode: 'InteractionMode', policy: 'CompatibilityPolicy') -> 'ModelIntegrationPlan'`

### `mconet.testing.StubPayloadDecoder`

- Kind: `class`
- Signature: `(descriptor: 'ComponentDescriptor', result: 'ErasedRuntimeValue', *, error: 'BaseException | None' = None) -> 'None'`
- `decode` (method): `(self, raw_data: 'Bytes') -> 'ErasedRuntimeValue'`
- `descriptor` (property)
- `raw_data` (property)

### `mconet.testing.StubPayloadEncoder`

- Kind: `class`
- Signature: `(descriptor: 'ComponentDescriptor', result: 'TransportBody', *, error: 'BaseException | None' = None) -> 'None'`
- `descriptor` (property)
- `encode` (method): `(self, payload: 'ErasedRuntimeValue') -> 'TransportBody'`
- `payloads` (property)

### `mconet.testing.StubServiceAccessResolver`

- Kind: `class`
- Signature: `(descriptor: 'ComponentDescriptor', result: 'ResolvedServiceAccess', *, error: 'BaseException | None' = None) -> 'None'`
- `descriptor` (property)
- `resolve` (method): `(self, interaction_override: 'ServiceAccess | None', request_service_access: 'ServiceAccess | None', client_default_service_access: 'ServiceAccess | None', protocol_default_service_access: 'ServiceAccess | None') -> 'ResolvedServiceAccess'`

### `mconet.testing.StubTaskProtocolAdapter`

- Kind: `class`
- Signature: `(descriptor: 'ComponentDescriptor', *, supports_result: 'bool', prepare_plan_result: 'ProtocolExecutionPlan', build_request_result: 'ProtocolRequestPlan', parse_response_result: 'ParsedTaskResponse', parse_error_result: 'ModelInteractionError | None', supports_error: 'BaseException | None' = None, prepare_plan_error: 'BaseException | None' = None, build_request_error: 'BaseException | None' = None, parse_response_error: 'BaseException | None' = None, parse_error_error: 'BaseException | None' = None) -> 'None'`
- `build_request` (method): `(self, request: 'ModelRequest', plan: 'ProtocolExecutionPlan') -> 'ProtocolRequestPlan'`
- `descriptor` (property)
- `parse_error` (method): `(self, error: 'ErasedRuntimeValue', metadata: 'TransportResponseMetadata') -> 'ModelInteractionError | None'`
- `parse_response` (method): `(self, response: 'ErasedRuntimeValue') -> 'ParsedTaskResponse'`
- `prepare_plan` (method): `(self, request: 'ModelRequest', access: 'ResolvedServiceAccess', mode: 'InteractionMode') -> 'ProtocolExecutionPlan'`
- `supports` (method): `(self, target: 'ModelTarget', task: 'TaskDescriptor', mode: 'InteractionMode') -> 'bool'`

### `mconet.testing.SuccessPayloadDecoderContractSuite`

- Kind: `class`
- Signature: `(decoder: 'PayloadDecoder') -> 'None'`
- `assert_decode` (method): `(self, raw_data: 'Bytes', *, assertion: 'Callable[[ErasedRuntimeValue], None]') -> 'None'`
- `assert_decode_failure` (method): `(self, raw_data: 'Bytes', *, assertion: 'Callable[[BaseException], None]') -> 'None'`

### `mconet.testing.TransportContractSuite`

- Kind: `class`
- Signature: `(transport: 'Transport') -> 'None'`
- `assert_send` (method): `(self, request: 'TransportRequest', context: 'TransportContext', *, assertion: 'Callable[[TransportResponse], None]') -> 'None'`
- `assert_send_cancellation` (method): `(self, request: 'TransportRequest', context: 'TransportContext', *, cancel: 'Callable[[], None]', assertion: 'Callable[[asyncio.CancelledError], None]') -> 'None'`
- `assert_send_failure` (method): `(self, request: 'TransportRequest', context: 'TransportContext', *, assertion: 'Callable[[BaseException], None]') -> 'None'`

### `mconet.testing.annotate_contract_failure`

- Kind: `function`
- Signature: `(error: 'BaseException', case: 'ContractCase') -> 'None'`

### `mconet.testing.contract_case_for_node`

- Kind: `function`
- Signature: `(node_id: 'str') -> 'ContractCase | None'`

### `mconet.testing.contract_suite_components`

- Kind: `function`
- Signature: `() -> 'MappingProxyType[str, str]'`

### `mconet.testing.json_fixtures_equal`

- Kind: `function`
- Signature: `(actual: 'JsonValue', expected: 'JsonValue') -> 'bool'`

### `mconet.transport.http_system.DefaultSystemHttpTransport`

- Kind: `class`
- Signature: `(*, proxy_environment: 'Mapping[str, str] | None' = None, proxy_override: 'HttpProxyOverride | None' = None, tls_options: 'Mapping[str, object] | None' = None, now: 'Callable[[], Timestamp] | None' = None, network_client: 'object | None' = None) -> 'None'`
- `close` (method): `(self) -> 'None'`
- `descriptor` (property)
- `send` (method): `(self, request: 'TransportRequest', context: 'TransportContext') -> 'TransportResponse'`

### `mconet.transport.http_system.HttpBaseUrl`

- Kind: `class`
- Signature: `(scheme: 'str', host: 'str', path: 'str', href: 'str') -> None`

### `mconet.transport.http_system.HttpCancellationBridge`

- Kind: `class`
- Signature: `(signal: 'CancellationSignal | None') -> 'None'`
- `close` (method): `(self) -> 'None'`
- `is_cancelled` (property)
- `reason` (property)

### `mconet.transport.http_system.HttpHeaderField`

- Kind: `class`
- Signature: `(name: 'str', value: 'str') -> None`

### `mconet.transport.http_system.HttpProxyEndpoint`

- Kind: `class`
- Signature: `(scheme: 'str', host: 'str', username: 'str | None' = None, password: 'str | None' = None) -> None`

### `mconet.transport.http_system.HttpProxyOverride`

- Kind: `class`
- Signature: `(endpoint: 'HttpProxyEndpoint | None') -> None`

### `mconet.transport.http_system.HttpProxySelection`

- Kind: `class`
- Signature: `(source: 'HttpProxySource', endpoint: 'HttpProxyEndpoint | None') -> None`

### `mconet.transport.http_system.HttpStatusOutcome`

- Kind: `class`
- Signature: `(outcome: 'TransportOutcome', status_code: 'int') -> None`

### `mconet.transport.http_system.HttpTlsPolicy`

- Kind: `class`
- Signature: `() -> None`
- `verifies_certificates` (property)
- `verifies_hostname` (property)

### `mconet.transport.http_system.apply_default_http_headers`

- Kind: `function`
- Signature: `(headers: 'tuple[HttpHeaderField, ...]') -> 'tuple[HttpHeaderField, ...]'`

### `mconet.transport.http_system.apply_http_content_length`

- Kind: `function`
- Signature: `(headers: 'tuple[HttpHeaderField, ...]', body: 'bytes') -> 'tuple[HttpHeaderField, ...]'`

### `mconet.transport.http_system.apply_http_content_type`

- Kind: `function`
- Signature: `(headers: 'tuple[HttpHeaderField, ...]', media_type: 'MediaType') -> 'tuple[HttpHeaderField, ...]'`

### `mconet.transport.http_system.ensure_http_deadline`

- Kind: `function`
- Signature: `(deadline: 'Timestamp | None', now: 'Callable[[], Timestamp]') -> 'None'`

### `mconet.transport.http_system.ensure_secure_http_tls`

- Kind: `function`
- Signature: `(options: 'Mapping[str, object] | None' = None) -> 'HttpTlsPolicy'`

### `mconet.transport.http_system.extract_http_response_media_type`

- Kind: `function`
- Signature: `(headers: 'tuple[HttpHeaderField, ...]') -> 'MediaType | None'`

### `mconet.transport.http_system.headers_for_http_redirect`

- Kind: `function`
- Signature: `(current: 'HttpBaseUrl', target: 'HttpBaseUrl', headers: 'tuple[HttpHeaderField, ...]') -> 'tuple[HttpHeaderField, ...]'`

### `mconet.transport.http_system.map_http_body`

- Kind: `function`
- Signature: `(body: 'TransportBody') -> 'bytes'`

### `mconet.transport.http_system.map_http_headers`

- Kind: `function`
- Signature: `(headers: 'Headers') -> 'tuple[HttpHeaderField, ...]'`

### `mconet.transport.http_system.map_http_method`

- Kind: `function`
- Signature: `(method: 'str') -> 'str'`

### `mconet.transport.http_system.map_http_proxy_endpoint`

- Kind: `function`
- Signature: `(url: 'str') -> 'HttpProxyEndpoint'`

### `mconet.transport.http_system.map_http_query`

- Kind: `function`
- Signature: `(query: 'QueryParameters') -> 'str'`

### `mconet.transport.http_system.map_http_status`

- Kind: `function`
- Signature: `(status_code: 'int') -> 'HttpStatusOutcome'`

### `mconet.transport.http_system.map_http_url`

- Kind: `function`
- Signature: `(url: 'UriValue') -> 'HttpBaseUrl'`

### `mconet.transport.http_system.normalize_http_network_timeout`

- Kind: `function`
- Signature: `(error: 'BaseException') -> 'ModelInteractionError'`

### `mconet.transport.http_system.read_bounded_http_response_body`

- Kind: `function`
- Signature: `(chunks: 'Iterable[bytes]', max_byte_length: 'int') -> 'Bytes'`

### `mconet.transport.http_system.read_bounded_http_response_releasing_connection`

- Kind: `function`
- Signature: `(chunks: 'Iterable[bytes]', max_byte_length: 'int', release: 'Callable[[], None]') -> 'Bytes'`

### `mconet.transport.http_system.select_http_proxy`

- Kind: `function`
- Signature: `(target: 'HttpBaseUrl', environment: 'Mapping[str, str]', override: 'HttpProxyOverride | None' = None) -> 'HttpProxySelection'`

### `mconet.transport.http_system.summarize_http_response_headers`

- Kind: `function`
- Signature: `(headers: 'tuple[HttpHeaderField, ...]') -> 'tuple[HttpHeaderField, ...]'`

### `mconet.transport.http_system.system_http_tls_policy`

- Kind: `function`
- Signature: `() -> 'HttpTlsPolicy'`

