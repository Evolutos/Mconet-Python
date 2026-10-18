# Error troubleshooting

Search this page by category, phase, or code. A `ModelInteractionError`
carries all three. The message describes the failure without request
contents, secrets, or component identifiers.

## Categories

- `invalid_request`
- `invalid_component_configuration`
- `unsupported_feature`
- `authentication`
- `permission`
- `rate_limit`
- `content_filter`
- `context_length`
- `timeout`
- `cancelled`
- `network`
- `serialization`
- `deserialization`
- `protocol`
- `model_service`
- `unknown`

## Phases

- `normalization`
- `validation`
- `component_resolution`
- `model_integration_resolution`
- `protocol_planning`
- `capability_resolution`
- `component_type_validation`
- `artifact_resolution`
- `protocol_adaptation`
- `encoding`
- `authentication`
- `transport`
- `stream_framing`
- `stream_mapping`
- `duplex_session`
- `long_running_operation`
- `decoding`
- `response_parsing`
- `monitoring`

## Codes

- `unsupported_model_integration`: no usable integration was found.
- `ambiguous_model_integration`: the type table or responsibility chain is
  ambiguous.
- `invalid_model_descriptor`: the model descriptor is not usable.
- `invalid_integration_binding`: the binding cannot be installed.
- `unsupported_task`: the task type is outside the selected integration.
- `unsupported_interaction_mode`: the interaction mode is not supported.
- `unsupported_capability`: a required capability was not satisfied.
- `ambiguous_capability_provider`: more than one capability provider matched.
- `invalid_component_type_contract`: adjacent component ports do not connect.
- `component_type_mismatch`: an erased value does not match its contract.
- `component_not_found`: a required role has no component.
- `ambiguous_component_selection`: the highest layer has more than one match.
- `unsupported_artifact_source`: the artifact source is not supported.
- `artifact_reference_not_found`: the artifact reference is missing.
- `duplicate_artifact_id`: an artifact id was repeated.
- `artifact_access_failed`: the artifact could not be read.
- `artifact_transfer_failed`: the artifact could not be transferred.
- `unsupported_body_signing`: no compatible body-signing mode is available.
- `body_not_replayable`: the body cannot be replayed within its limit.
- `body_already_consumed`: a single-use body was opened again.
- `response_body_too_large`: the response body exceeds its limit.
- `stream_frame_too_large`: a stream frame exceeds its limit.
- `incomplete_stream_frame`: the server stream ended inside an event.
- `stream_events_consumed`: the stream was already consumed.
- `invalid_tool_call`: a tool call does not follow an assistant message.
  The category is `invalid_request` and the phase is `protocol_adaptation`.
  Document validation reports the same rule as a `ValueError` before the
  request reaches protocol adaptation.
- `client_closed`: `interact` was called after `ModelClient.close`. The
  category is `invalid_request` and the phase is `validation`.
- `invalid_monitoring_merge_mode`: the monitor merge mode is not `append`,
  `prepend`, or `replace`. The category is `invalid_request` and the phase
  is `monitoring`.

## What to check

- `client_closed` means the client no longer accepts requests. Create another
  client. Closing does not cancel work that already entered the runtime.
- `invalid_component_type_contract` means an injected adapter, encoder, or
  decoder pair does not share a type id, or both sides declared a schema or
  media type that differs.
- `component_not_found` means the interaction, client, binding, and SDK
  defaults all left a required role empty.
- `invalid_monitoring_merge_mode` means the governing monitor options named a
  mode other than `append`, `prepend`, or `replace`.
