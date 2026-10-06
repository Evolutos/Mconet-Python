"""Task-neutral domain contracts and immutable values for Mconet."""

from mconet.core.domain.artifact import Artifact
from mconet.core.domain.artifact_catalog import ArtifactCatalog
from mconet.core.domain.artifact_catalog_scope import (
    validate_empty_artifact_catalog_scope,
)
from mconet.core.domain.artifact_catalog_validation import validate_artifact_catalog
from mconet.core.domain.artifact_descriptor import ArtifactDescriptor
from mconet.core.domain.artifact_kind import ArtifactKind
from mconet.core.domain.artifact_metadata import ArtifactMetadata
from mconet.core.domain.artifact_reference import ArtifactReference
from mconet.core.domain.artifact_reference_resolution import (
    resolve_artifact_reference,
)
from mconet.core.domain.artifact_source import ArtifactSource
from mconet.core.domain.artifact_validation import validate_artifact
from mconet.core.domain.authorization import Authorization
from mconet.core.domain.bytes_value import Bytes
from mconet.core.domain.cancellation_signal import CancellationSignal
from mconet.core.domain.compatibility_policy import (
    CompatibilityPolicy,
    default_compatibility_policy,
)
from mconet.core.domain.diagnostic import Diagnostic
from mconet.core.domain.duration import Duration, validate_duration
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.extensions import Extensions
from mconet.core.domain.header_field import HeaderField
from mconet.core.domain.headers import Headers
from mconet.core.domain.inline_artifact_source import InlineArtifactSource
from mconet.core.domain.interaction_mode import InteractionMode
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.interaction_resource_limits import InteractionResourceLimits
from mconet.core.domain.json_primitive import JsonPrimitive
from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.local_file_artifact_source import LocalFileArtifactSource
from mconet.core.domain.media_type import MediaType, parse_media_type
from mconet.core.domain.message_content import MessageContent
from mconet.core.domain.message_content_kind import MessageContentKind
from mconet.core.domain.message_content_scope import (
    validate_text_message_content_scope,
)
from mconet.core.domain.message_document import MessageDocument
from mconet.core.domain.message_document_builder import MessageDocumentBuilder
from mconet.core.domain.message_document_validation import validate_message_document
from mconet.core.domain.message_element import MessageElement
from mconet.core.domain.message_element_kind import MessageElementKind
from mconet.core.domain.message_element_value import MessageElementValue
from mconet.core.domain.message_entry import MessageEntry
from mconet.core.domain.message_entry_builder import MessageEntryBuilder
from mconet.core.domain.message_entry_validation import validate_message_entry
from mconet.core.domain.message_group import MessageGroup
from mconet.core.domain.message_group_validation import validate_message_group
from mconet.core.domain.message_relation import MessageRelation
from mconet.core.domain.message_role import MessageRole
from mconet.core.domain.message_role_validation import validate_message_role
from mconet.core.domain.model_descriptor import ModelDescriptor
from mconet.core.domain.model_descriptor_validation import validate_model_descriptor
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.model_target import ModelTarget
from mconet.core.domain.model_target_validation import validate_model_target
from mconet.core.domain.monitoring_merge_mode import MonitoringMergeMode
from mconet.core.domain.named_model import NamedModel
from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier
from mconet.core.domain.optional_field import OptionalField, serialize_optional_fields
from mconet.core.domain.query_parameter import QueryParameter
from mconet.core.domain.query_parameters import QueryParameters
from mconet.core.domain.recovery_hint import RecoveryHint
from mconet.core.domain.resolved_interaction_resource_limits import (
    ResolvedInteractionResourceLimits,
)
from mconet.core.domain.resource_limits_resolution import resolve_resource_limits
from mconet.core.domain.resource_limits_validation import validate_resource_limits
from mconet.core.domain.schema_version import SchemaVersion
from mconet.core.domain.secret_value import AuthorizedSecretConsumer, SecretValue
from mconet.core.domain.service_access import ServiceAccess
from mconet.core.domain.service_access_validation import validate_service_access
from mconet.core.domain.task_descriptor import TaskDescriptor
from mconet.core.domain.task_descriptor_validation import validate_task_descriptor
from mconet.core.domain.task_group_node import TaskGroupNode
from mconet.core.domain.task_node import TaskNode
from mconet.core.domain.task_node_kind import TaskNodeKind
from mconet.core.domain.task_relation import TaskRelation
from mconet.core.domain.text_message_content import TextMessageContent
from mconet.core.domain.text_message_content_validation import (
    validate_text_message_content,
)
from mconet.core.domain.timestamp import Timestamp, parse_timestamp, serialize_timestamp
from mconet.core.domain.unknown_fields import (
    preserve_unknown_fields,
    restore_preserved_fields,
)
from mconet.core.domain.uri import UriValue, validate_uri
from mconet.core.domain.uri_artifact_source import UriArtifactSource

__all__ = (
    "Artifact",
    "ArtifactCatalog",
    "ArtifactDescriptor",
    "ArtifactKind",
    "ArtifactMetadata",
    "ArtifactReference",
    "ArtifactSource",
    "Authorization",
    "AuthorizedSecretConsumer",
    "Bytes",
    "CancellationSignal",
    "CompatibilityPolicy",
    "Diagnostic",
    "Duration",
    "ErrorCategory",
    "Extensions",
    "HeaderField",
    "Headers",
    "InlineArtifactSource",
    "InteractionMode",
    "InteractionPhase",
    "InteractionResourceLimits",
    "JsonPrimitive",
    "JsonValue",
    "LocalFileArtifactSource",
    "MediaType",
    "MessageContent",
    "MessageContentKind",
    "MessageDocument",
    "MessageDocumentBuilder",
    "MessageElement",
    "MessageElementKind",
    "MessageElementValue",
    "MessageEntry",
    "MessageEntryBuilder",
    "MessageGroup",
    "MessageRelation",
    "MessageRole",
    "ModelDescriptor",
    "ModelInteractionError",
    "ModelTarget",
    "MonitoringMergeMode",
    "NamedModel",
    "OpenIdentifier",
    "OptionalField",
    "QueryParameter",
    "QueryParameters",
    "RecoveryHint",
    "ResolvedInteractionResourceLimits",
    "SchemaVersion",
    "SecretValue",
    "ServiceAccess",
    "TaskDescriptor",
    "TaskGroupNode",
    "TaskNode",
    "TaskNodeKind",
    "TaskRelation",
    "TextMessageContent",
    "Timestamp",
    "UriArtifactSource",
    "UriValue",
    "default_compatibility_policy",
    "parse_media_type",
    "parse_timestamp",
    "preserve_unknown_fields",
    "resolve_artifact_reference",
    "resolve_resource_limits",
    "restore_preserved_fields",
    "serialize_optional_fields",
    "serialize_timestamp",
    "validate_artifact",
    "validate_artifact_catalog",
    "validate_duration",
    "validate_empty_artifact_catalog_scope",
    "validate_json_value_numbers",
    "validate_message_document",
    "validate_message_entry",
    "validate_message_group",
    "validate_message_role",
    "validate_model_descriptor",
    "validate_model_target",
    "validate_open_identifier",
    "validate_resource_limits",
    "validate_service_access",
    "validate_task_descriptor",
    "validate_text_message_content",
    "validate_text_message_content_scope",
    "validate_uri",
)
