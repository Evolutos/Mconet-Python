"""Immutable absolute and relative URI references."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast

_ABSOLUTE_SCHEME_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
_INVALID_PERCENT_PATTERN = re.compile(r"%(?![0-9A-Fa-f]{2})")
_URI_CHARACTER_PATTERN = re.compile(r"[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]*")


@dataclass(frozen=True, slots=True)
class UriValue:
    """Preserve URI reference text and its declared reference form.

    The value object does not normalize case, escapes, path segments, or query
    ordering. URI syntax and consistency between the text and ``is_absolute``
    are owned by the dedicated validator.
    """

    value: str
    """The exact URI reference text supplied by the producer."""

    is_absolute: bool
    """Whether the value is declared to contain an absolute URI scheme."""

    def __post_init__(self) -> None:
        """Require exact primitive storage without parsing or normalization."""
        value = cast(object, self.value)
        absolute = cast(object, self.is_absolute)
        if not isinstance(value, str):
            raise TypeError("UriValue value must be a string.")
        if type(absolute) is not bool:
            raise TypeError("UriValue is_absolute must be a boolean.")

    def __str__(self) -> str:
        """Return the preserved URI reference text."""
        return self.value


def validate_uri(uri: UriValue) -> UriValue:
    """Validate an RFC 3986 URI reference without normalizing its text.

    Absolute values require a valid scheme. Relative values must not contain a
    scheme and cannot use a colon in their first path segment. Empty relative
    references are valid. The validator accepts only the ASCII URI character
    repertoire and requires every percent sign to begin a two-digit hex escape.

    Args:
        uri: The immutable URI reference to validate.

    Returns:
        The same value object after successful validation.

    Raises:
        TypeError: If ``uri`` is not a :class:`UriValue`.
        ValueError: If syntax, encoding, or reference form is invalid.
    """
    candidate = cast(object, uri)
    # Preserve the nominal absolute/relative declaration instead of inferring a
    # new value from arbitrary text supplied to the validator.
    if not isinstance(candidate, UriValue):
        raise TypeError("uri must be a UriValue.")

    value = candidate.value
    # Validate the shared character, escape, and fragment constraints before
    # branching into absolute and relative reference rules.
    if _URI_CHARACTER_PATTERN.fullmatch(value) is None:
        raise ValueError("UriValue contains a character outside RFC 3986.")
    if _INVALID_PERCENT_PATTERN.search(value) is not None:
        raise ValueError("UriValue contains an invalid percent escape.")
    if value.count("#") > 1:
        raise ValueError("UriValue contains multiple fragment delimiters.")

    scheme_match = _ABSOLUTE_SCHEME_PATTERN.match(value)
    has_scheme = scheme_match is not None
    # The declared reference form is part of the value contract and must agree
    # with the syntax; validation never silently flips is_absolute.
    if candidate.is_absolute:
        if not has_scheme:
            raise ValueError("Absolute UriValue must contain a valid scheme.")
    elif has_scheme:
        raise ValueError("Relative UriValue must not contain a scheme.")
    elif ":" in re.split(r"[/#?]", value, maxsplit=1)[0]:
        # RFC 3986 uses path-noscheme for this position so a relative reference
        # cannot be confused with an invalid or future absolute scheme.
        raise ValueError("Relative UriValue first path segment must not contain ':'.")

    # Authority syntax begins after the scheme for absolute values and at the
    # start of the original text for relative references.
    reference = value[scheme_match.end() :] if scheme_match is not None else value
    _validate_authority(reference)
    return candidate


def _validate_authority(reference: str) -> None:
    """Validate bracket and port structure when a reference has authority."""
    # Bracketed IP literals are meaningful only in an authority introduced by
    # //; accepting them in a path would make reference parsing ambiguous.
    if not reference.startswith("//"):
        if "[" in reference or "]" in reference:
            raise ValueError("UriValue IP literal must appear inside authority.")
        return

    authority = re.split(r"[/#?]", reference[2:], maxsplit=1)[0]
    suffix = reference[2 + len(authority) :]
    if "[" in suffix or "]" in suffix:
        raise ValueError("UriValue IP literal must appear inside authority.")

    host_port = authority.rsplit("@", maxsplit=1)[-1]
    # User information can contain delimiters, so bracket validation applies to
    # the host/port suffix while still rejecting stray brackets elsewhere.
    if ("[" in authority or "]" in authority) and not (
        "[" in host_port or "]" in host_port
    ):
        raise ValueError("UriValue contains an invalid IP literal authority.")
    if "[" in host_port or "]" in host_port:
        if re.fullmatch(r"\[[^\[\]]+\](?::[0-9]*)?", host_port) is None:
            raise ValueError("UriValue contains an invalid IP literal authority.")
        return

    # Multiple colons denote an IPv6 literal, which RFC 3986 requires to use
    # square brackets before an optional port can be parsed.
    if host_port.count(":") > 1:
        raise ValueError("UriValue IPv6 host must use square brackets.")
    if ":" in host_port:
        port = host_port.rpartition(":")[2]
        if port and not port.isdigit():
            raise ValueError("UriValue authority port must contain only digits.")
