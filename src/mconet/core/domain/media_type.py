"""Immutable structured media type values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True, slots=True)
class MediaType:
    """Preserve a media type, subtype, and ordered parameter pairs.

    Syntax, case normalization, quoting, and duplicate-parameter rules belong
    to the parser. The immutable tuple retains the parsed parameter structure
    without exposing mutable mapping behavior.
    """

    type: str
    """The media type token."""

    subtype: str
    """The media subtype token."""

    parameters: tuple[tuple[str, str], ...] = ()
    """Ordered parameter name/value pairs."""

    def __post_init__(self) -> None:
        """Require immutable primitive storage without parsing syntax."""
        media_type = cast(object, self.type)
        subtype = cast(object, self.subtype)
        parameters = cast(object, self.parameters)
        if not isinstance(media_type, str):
            raise TypeError("MediaType type must be a string.")
        if not isinstance(subtype, str):
            raise TypeError("MediaType subtype must be a string.")
        if not isinstance(parameters, tuple):
            raise TypeError("MediaType parameters must be a tuple.")
        for parameter_value in cast(tuple[object, ...], parameters):
            if not isinstance(parameter_value, tuple):
                raise TypeError(
                    "MediaType parameters must contain string name/value pairs."
                )
            parameter = cast(tuple[object, ...], parameter_value)
            if len(parameter) != 2:
                raise TypeError(
                    "MediaType parameters must contain string name/value pairs."
                )
            name, value = parameter
            if not isinstance(name, str) or not isinstance(value, str):
                raise TypeError(
                    "MediaType parameters must contain string name/value pairs."
                )

    def __str__(self) -> str:
        """Return the unparameterized type/subtype form."""
        return f"{self.type}/{self.subtype}"
