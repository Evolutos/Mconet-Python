"""Open string identifiers shared by extensible Mconet domain contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast

_MAX_OPEN_IDENTIFIER_LENGTH = 128
_OPEN_IDENTIFIER_PATTERN = re.compile(
    r"[a-z0-9](?:[a-z0-9_-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9_-]*[a-z0-9])?)*"
)


@dataclass(frozen=True, slots=True)
class OpenIdentifier:
    """Preserve an extensible identifier as an immutable, case-sensitive value.

    This value object deliberately does not restrict namespaces, length,
    whitespace, casing, or known values. Semantic validation belongs to the
    separate OpenIdentifier validator so future identifiers remain lossless.
    """

    value: str
    """The exact identifier text supplied by the producer."""

    def __post_init__(self) -> None:
        """Require the primitive string representation without normalizing it."""
        # Type membership is a value-object invariant; format and namespace
        # rules remain outside this type for the dedicated validator work item.
        value = cast(object, self.value)
        if not isinstance(value, str):
            raise TypeError("OpenIdentifier value must be a string.")

    def __str__(self) -> str:
        """Return the preserved identifier text for explicit string contexts."""
        return self.value


def validate_open_identifier(identifier: OpenIdentifier) -> OpenIdentifier:
    """Validate a portable open identifier and return it without normalization.

    Valid identifiers contain 1 to 128 lowercase ASCII characters. A value is
    composed of one or more dot-separated namespace segments. Each segment
    starts and ends with an ASCII letter or digit and may contain ``_`` or
    ``-`` internally. Unknown values remain valid because validation never
    compares the identifier with a closed set of names.

    Args:
        identifier: The immutable identifier to validate.

    Returns:
        The same identifier instance after successful validation.

    Raises:
        TypeError: If ``identifier`` is not an :class:`OpenIdentifier`.
        ValueError: If the preserved value violates a portable format rule.
    """
    candidate = cast(object, identifier)
    # Require the nominal value object so callers cannot bypass its immutable
    # storage contract with an arbitrary string-like value.
    if not isinstance(candidate, OpenIdentifier):
        raise TypeError("identifier must be an OpenIdentifier.")

    value = candidate.value
    # Report independent boundary failures before applying the compact grammar,
    # which keeps validation errors stable and actionable.
    if not value:
        raise ValueError("OpenIdentifier must not be empty.")
    if len(value) > _MAX_OPEN_IDENTIFIER_LENGTH:
        raise ValueError("OpenIdentifier must contain at most 128 characters.")
    if any(character.isspace() for character in value):
        raise ValueError("OpenIdentifier must not contain whitespace.")
    if any("A" <= character <= "Z" for character in value):
        raise ValueError("OpenIdentifier must use lowercase ASCII characters.")
    # A full match simultaneously enforces ASCII portability, non-empty
    # namespace segments, and unambiguous dot-separated boundaries.
    if _OPEN_IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise ValueError("OpenIdentifier has an invalid namespace format.")

    # Validation is non-normalizing so unknown future identifiers round-trip
    # byte-for-byte through older implementations.
    return candidate
