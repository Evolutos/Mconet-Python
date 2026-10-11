"""Tests for mapping OpenAI-compatible failure bodies to normalized errors."""

from mconet.core.domain import (
    HeaderField,
    Headers,
    JsonValue,
    ModelInteractionError,
    OpenIdentifier,
    RecoveryHint,
    validate_duration,
)
from mconet.core.spi import (
    ErasedRuntimeValue,
    TransportOutcome,
    TransportResponseMetadata,
)
from mconet.integration.openai_compatible._errors import (
    SERVICE_AUTHENTICATION_FAILED_CODE,
    SERVICE_CONTENT_FILTERED_CODE,
    SERVICE_ERROR_CODE,
    SERVICE_PERMISSION_DENIED_CODE,
    SERVICE_RATE_LIMITED_CODE,
    service_error,
)
from mconet.integration.openai_compatible._openai_chat_completion_error_dto import (
    OpenAIChatCompletionErrorDTO,
)
from mconet.integration.openai_compatible._openai_chat_completion_error_response_dto import (
    OpenAIChatCompletionErrorResponseDTO,
)
from mconet.integration.openai_compatible.openai_chat_completions_adapter import (
    OpenAIChatCompletionsAdapter,
)

_SECRET_MESSAGE = "Incorrect API key provided: sk-fixture-value."


def _metadata(
    status: int | None, *headers: tuple[str, str], request_id: str | None = "req-1"
) -> TransportResponseMetadata:
    """Create failed-response transport facts."""
    return TransportResponseMetadata(
        outcome=TransportOutcome(OpenIdentifier("service_error")),
        headers=Headers(tuple(HeaderField(name, value) for name, value in headers)),
        status_code=status,
        request_id=request_id,
    )


def _body(
    code: str | int | None = None, error_type: str | None = None
) -> OpenAIChatCompletionErrorResponseDTO:
    """Create one failure body whose message must never be copied."""
    return OpenAIChatCompletionErrorResponseDTO(
        OpenAIChatCompletionErrorDTO(_SECRET_MESSAGE, error_type, code)
    )


def _assert_error(
    error: ModelInteractionError,
    category: str,
    code: str,
    message: str,
    recovery: RecoveryHint,
) -> None:
    """Require the normalized fields shared by every mapped failure."""
    assert error.category.id.value == category
    assert error.phase.id.value == "response_parsing"
    assert error.code == code
    assert error.message == message
    assert error.recovery == recovery
    assert _SECRET_MESSAGE not in str(error)
    assert error.cause is None


def test_401_maps_to_authentication() -> None:
    """Verify rejected credentials are not transient and carry diagnostics."""
    error = service_error(_body("invalid_api_key"), _metadata(401))

    _assert_error(
        error,
        "authentication",
        SERVICE_AUTHENTICATION_FAILED_CODE,
        "The model service rejected the request credentials.",
        RecoveryHint(False, None, False),
    )
    assert error.status_code == 401
    assert error.service_error_code == "invalid_api_key"
    assert error.request_id == "req-1"


def test_403_maps_to_permission() -> None:
    """Verify denied permission is not transient."""
    error = service_error(_body(), _metadata(403))

    _assert_error(
        error,
        "permission",
        SERVICE_PERMISSION_DENIED_CODE,
        "The model service denied permission for the request.",
        RecoveryHint(False, None, False),
    )
    assert error.service_error_code is None


def test_429_maps_to_a_transient_rate_limit_with_retry_after() -> None:
    """Verify the delta-seconds Retry-After delay is carried."""
    error = service_error(
        _body("rate_limit_exceeded"), _metadata(429, ("retry-after", " 20 "))
    )

    _assert_error(
        error,
        "rate_limit",
        SERVICE_RATE_LIMITED_CODE,
        "The model service rate limit or quota was exceeded.",
        RecoveryHint(True, validate_duration(20, "seconds"), False),
    )


def test_unusable_retry_after_values_are_ignored() -> None:
    """Verify dates, repeats, signs, and non-ASCII digits give no delay."""
    for headers in (
        (("Retry-After", "Wed, 21 Oct 2026 07:28:00 GMT"),),
        (("Retry-After", "1"), ("Retry-After", "2")),
        (("Retry-After", "-1"),),
        (("Retry-After", "1.5"),),
        (("Retry-After", "\u0661\u0662"),),
        (("Retry-After", ""),),
        (("Retry-After", "9" * 30),),
        (),
    ):
        error = service_error(_body(), _metadata(429, *headers))

        assert error.recovery == RecoveryHint(True, None, False)


def test_exhausted_quota_is_not_transient() -> None:
    """Verify insufficient_quota in code or type is not retryable."""
    for body in (_body("insufficient_quota"), _body(None, "insufficient_quota")):
        error = service_error(body, _metadata(429, ("Retry-After", "5")))

        assert error.category.id.value == "rate_limit"
        assert error.recovery == RecoveryHint(False, None, False)


def test_content_filter_code_maps_to_content_filter() -> None:
    """Verify the content_filter service code selects the category."""
    error = service_error(_body("content_filter"), _metadata(400))

    _assert_error(
        error,
        "content_filter",
        SERVICE_CONTENT_FILTERED_CODE,
        "The model service blocked the request or response content.",
        RecoveryHint(False),
    )
    assert error.status_code == 400
    assert error.service_error_code == "content_filter"


def test_status_takes_precedence_over_the_content_filter_code() -> None:
    """Verify the documented precedence order."""
    assert service_error(_body("content_filter"), _metadata(401)).code == (
        SERVICE_AUTHENTICATION_FAILED_CODE
    )
    assert service_error(_body("content_filter"), _metadata(429)).code == (
        SERVICE_RATE_LIMITED_CODE
    )


def test_other_failures_map_to_model_service() -> None:
    """Verify 5xx is transient and other statuses are not."""
    server = service_error(_body(500), _metadata(503, ("Retry-After", "3")))
    client = service_error(_body("context_length_exceeded"), _metadata(400))
    unknown = service_error(_body(), _metadata(None, request_id=None))

    _assert_error(
        server,
        "model_service",
        SERVICE_ERROR_CODE,
        "The model service returned an error.",
        RecoveryHint(True, validate_duration(3, "seconds")),
    )
    assert server.service_error_code == "500"
    assert client.recovery == RecoveryHint(False)
    assert client.service_error_code == "context_length_exceeded"
    assert unknown.recovery == RecoveryHint(False)
    assert unknown.status_code is None
    assert unknown.request_id is None


def test_parse_error_maps_a_recognized_body() -> None:
    """Verify the adapter decodes the body and applies the mapping."""
    body: JsonValue = {
        "error": {"message": _SECRET_MESSAGE, "type": "invalid_request_error"}
    }

    error = OpenAIChatCompletionsAdapter().parse_error(
        ErasedRuntimeValue(OpenIdentifier("json.value"), body), _metadata(401)
    )

    assert isinstance(error, ModelInteractionError)
    assert error.code == SERVICE_AUTHENTICATION_FAILED_CODE


def test_parse_error_returns_none_for_an_unrecognized_body() -> None:
    """Verify foreign error shapes are left to the runtime fallback."""
    adapter = OpenAIChatCompletionsAdapter()
    bodies: tuple[JsonValue, ...] = (
        {"message": "Bad gateway"},
        {"error": "boom"},
        {"error": {"code": 502}},
        ["error"],
        None,
    )

    for body in bodies:
        payload = ErasedRuntimeValue(OpenIdentifier("json.value"), body)

        assert adapter.parse_error(payload, _metadata(502)) is None
