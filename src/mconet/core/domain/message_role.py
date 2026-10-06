"""Open structural contract for message participant roles."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.open_identifier import OpenIdentifier


@runtime_checkable
class MessageRole(Protocol):
    """Describe a standard or provider-defined message role without coercion.

    Implementations expose stable role identity separately from optional semantic
    guidance and the producer's original wire value. The open protocol allows a
    custom role to preserve future fields without inheriting an SDK base class or
    being reduced to a known-role enum. Syntax and semantic validation remain a
    separate operation so this contract only defines the complete read surface.
    """

    @property
    def id(self) -> OpenIdentifier:
        """Return the open identifier naming this role."""
        # Standard and unknown roles use the same nominal identifier boundary;
        # consumers must not infer support merely from structural conformance.
        ...

    @property
    def semantic(self) -> str | None:
        """Return optional producer guidance about the role's meaning."""
        # Semantic text supplements an unknown identifier without replacing it
        # or changing the role selected by protocol adapters.
        ...

    @property
    def raw_value(self) -> str | None:
        """Return the optional original external role spelling."""
        # Keeping raw text independent from the portable identifier permits an
        # adapter to round-trip provider casing or spelling without normalization.
        ...

    @property
    def extensions(self) -> Extensions:
        """Return unknown versioned role fields for forward compatibility."""
        # Extension data remains observable but uninterpreted at this boundary;
        # a later validator owns recursive portable-JSON checks.
        ...
