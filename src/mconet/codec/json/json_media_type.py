"""JSON media-type matching for the codec."""

from __future__ import annotations

from mconet.core.domain import MediaType, parse_media_type

_JSON_SUBTYPE = "json"
_JSON_STRUCTURED_SUFFIX = "+json"


def is_json_media_type(value: object) -> bool:
    """Return whether a media type is JSON or a JSON structured suffix.

    Parsing and case normalization use the shared media-type parser. Parameters
    such as charset do not change the decision. A suffix matches only when a
    non-empty subtype prefix precedes ``+json``, so ``+json`` alone is not
    accepted. The function does not read a body or select a decoder.

    Args:
        value: A media type string, a :class:`MediaType`, or any other value.

    Returns:
        Whether the value is a valid JSON or ``+json`` media type.
    """
    media_type = _media_type_from(value)
    if media_type is None:
        # An unparsable value is not JSON, including non-strings and malformed
        # types. Matching must not raise for untrusted response metadata.
        return False

    # Compare the subtype only. The type token and parameters do not decide
    # whether the representation is JSON.
    subtype = media_type.subtype.lower()
    if subtype == _JSON_SUBTYPE:
        return True
    return subtype.endswith(_JSON_STRUCTURED_SUFFIX) and len(subtype) > len(
        _JSON_STRUCTURED_SUFFIX
    )


def _media_type_from(value: object) -> MediaType | None:
    """Return a structured media type, or None when the value cannot be parsed.

    Args:
        value: Candidate media type text or structured value.

    Returns:
        The structured media type, or None when it is absent or malformed.
    """
    if isinstance(value, MediaType):
        # A structured value is already split into type, subtype, and
        # parameters. It does not need a second parse.
        return value
    if not isinstance(value, str):
        return None
    try:
        return parse_media_type(value)
    except (TypeError, ValueError):
        # Parser failures are negative matches. Their messages can quote the
        # input, so they stay inside this function.
        return None
