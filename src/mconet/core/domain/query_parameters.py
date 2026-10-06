"""Immutable ordered collection of protocol-neutral query parameters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mconet.core.domain.query_parameter import QueryParameter


@dataclass(frozen=True, slots=True)
class QueryParameters:
    """Preserve every query parameter in exact caller order.

    Repeated names remain separate entries and name spelling is not normalized.
    Encoding and query-string assembly remain transport responsibilities.
    """

    values: tuple[QueryParameter, ...] = ()
    """Ordered parameters, including every repeated name occurrence."""

    def __post_init__(self) -> None:
        """Require immutable storage containing only QueryParameter values."""
        values = cast(object, self.values)
        # Tuple storage prevents later reordering or insertion; validating every
        # element keeps the collection safe for a transport to encode directly.
        if not isinstance(values, tuple):
            raise TypeError("QueryParameters values must be a tuple.")
        for parameter in cast(tuple[object, ...], values):
            if not isinstance(parameter, QueryParameter):
                raise TypeError(
                    "QueryParameters values must contain QueryParameter values."
                )
