"""Cross-platform golden fixture for the R1 JSON codec.

The committed document is the shared value and compact UTF-8 text. Encoding
must reproduce that text exactly, including object member order. Decoding the
same bytes must be semantically equal for both success and error outcomes.
"""

from pathlib import Path
from typing import cast

from mconet.codec.json import (
    JsonErrorPayloadDecoder,
    JsonPayloadEncoder,
    JsonSuccessPayloadDecoder,
)
from mconet.core.domain import Bytes, JsonValue, MediaType, OpenIdentifier
from mconet.core.spi import ErasedRuntimeValue
from mconet.testing import FixtureLoader, json_fixtures_equal

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_ROOT = _PROJECT_ROOT / "spec" / "fixtures" / "r1-text-unary"
_FIXTURE_RESOURCE = "json-codec.json"
_JSON_MEDIA_TYPE = MediaType("application", "json")
_MAXIMUM_CANONICAL_BYTES = 1024


def _cases(document: JsonValue) -> tuple[tuple[str, JsonValue, str], ...]:
    """Return the named value and canonical text pairs from the golden file."""
    if not isinstance(document, dict) or set(document) != {"cases"}:
        raise AssertionError("JSON golden fixture must contain only cases.")
    raw_cases = document["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        raise AssertionError("JSON golden fixture must contain cases.")

    cases: list[tuple[str, JsonValue, str]] = []
    seen: set[str] = set()
    for item in raw_cases:
        # Exact fields keep every platform on the same three facts: a stable
        # name, the JSON value, and the one canonical text for that value.
        if not isinstance(item, dict) or set(item) != {"canonical", "name", "value"}:
            raise AssertionError(
                "Each golden case must have name, value, and canonical."
            )
        name = item["name"]
        canonical = item["canonical"]
        if not isinstance(name, str) or not name or name in seen:
            raise AssertionError("Golden case names must be unique non-empty strings.")
        if not isinstance(canonical, str):
            raise AssertionError("Golden canonical text must be a string.")
        seen.add(name)
        cases.append((name, item["value"], canonical))
    return tuple(cases)


def test_json_codec_golden_fixture_is_deterministic_and_equivalent() -> None:
    """Verify encode and both decoders agree on the shared golden cases."""
    document = FixtureLoader(_FIXTURE_ROOT).load(_FIXTURE_RESOURCE)
    encoder = JsonPayloadEncoder()
    success_decoder = JsonSuccessPayloadDecoder(_MAXIMUM_CANONICAL_BYTES)
    error_decoder = JsonErrorPayloadDecoder(_MAXIMUM_CANONICAL_BYTES)

    for name, value, canonical in _cases(document):
        payload = ErasedRuntimeValue(OpenIdentifier("json.value"), value)
        first = encoder.encode(payload)
        second = encoder.encode(payload)
        expected = canonical.encode("utf-8")
        # Two encodes of one loaded value must be the same bytes, and those
        # bytes must be the committed canonical text rather than another
        # equally valid JSON spelling.
        assert bytes(first.bytes) == expected, name
        assert bytes(second.bytes) == expected, name
        assert first.media_type == _JSON_MEDIA_TYPE
        assert len(expected) <= _MAXIMUM_CANONICAL_BYTES

        raw_data = Bytes(expected)
        success = success_decoder.decode(raw_data)
        error = error_decoder.decode(raw_data)
        # Semantic equality ignores object key order. Both outcomes must still
        # carry the JSON value port and no invented schema.
        # The erased port types its value as object. These decoders return the
        # JSON value, which is what semantic comparison accepts.
        assert success.type_id == OpenIdentifier("json.value")
        assert error.type_id == OpenIdentifier("json.value")
        assert success.schema_id is None
        assert error.schema_id is None
        assert json_fixtures_equal(cast(JsonValue, success.value), value), name
        assert json_fixtures_equal(cast(JsonValue, error.value), value), name
