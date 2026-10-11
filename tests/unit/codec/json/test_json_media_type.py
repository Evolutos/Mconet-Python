"""Acceptance tests for JSON media-type matching."""

from mconet.codec.json import is_json_media_type
from mconet.core.domain import MediaType


def test_is_json_media_type_accepts_json_suffixes_parameters_and_case() -> None:
    """Verify application/json, +json, parameters, and case all match."""
    accepted = (
        "application/json",
        "APPLICATION/JSON",
        "application/json;charset=utf-8",
        "application/json; charset=UTF-8",
        "text/json",
        "application/problem+json",
        "application/vnd.api+json;charset=utf-8",
        "Application/Problem+JSON",
        MediaType("Application", "Problem+JSON", (("charset", "utf-8"),)),
    )

    # Parameters and type tokens do not change the JSON decision. A structured
    # media type uses the same subtype rule as parsed text.
    for value in accepted:
        assert is_json_media_type(value) is True


def test_is_json_media_type_rejects_unrelated_and_malformed_values() -> None:
    """Verify non-JSON types and unparsable values are negative matches."""
    rejected = (
        None,
        1,
        "",
        "application/json;",
        "text/plain",
        "application/json-patch",
        "application/+json",
        "application/json+xml",
        "application/json, text/plain",
        MediaType("text", "plain"),
    )

    # Malformed text is a negative match rather than a parser exception, and
    # the function does not select a decoder from the result.
    for value in rejected:
        assert is_json_media_type(value) is False
