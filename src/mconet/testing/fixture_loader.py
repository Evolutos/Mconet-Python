"""Validated loading of one language-neutral Golden Fixture collection."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import NoReturn, cast

from mconet.core.domain import (
    JsonValue,
    OpenIdentifier,
    validate_json_value_numbers,
    validate_open_identifier,
)

_INDEX_FIELDS = frozenset(
    ("collection", "format_version", "profile", "purpose", "resources")
)
_FORMAT_VERSION = 1


class FixtureLoader:
    """Load isolated JSON values from one indexed Golden Fixture collection.

    The caller supplies the collection directory containing ``index.json``.
    Construction validates and snapshots the complete collection, so later file
    changes cannot alter one conformance run. The index must use format version
    1, declare the ``fixtures`` collection, provide one portable open profile,
    and list sorted unique relative resource paths.

    Resource paths use POSIX separators on every platform and cannot escape the
    collection through absolute paths, parent traversal, non-canonical segments,
    or symlinks. Every declared file must contain strict UTF-8 JSON with unique
    object keys and portable numbers. Each :meth:`load` returns a deep copy, so
    one test framework consumer cannot mutate another consumer's fixture value.

    The loader performs no schema validation, canonical comparison, fixture
    interpretation, repository discovery, network access, or global registry
    mutation. Those remain separate test-kit responsibilities.
    """

    __slots__ = ("_documents", "_profile", "_resources")

    _documents: Mapping[str, JsonValue]
    _profile: OpenIdentifier
    _resources: tuple[str, ...]

    def __init__(self, root: Path) -> None:
        """Validate and snapshot one explicitly located fixture collection.

        Args:
            root: Directory containing the collection ``index.json`` and every
                resource declared by that index.

        Raises:
            TypeError: If ``root`` is not a :class:`pathlib.Path`.
            ValueError: If the directory, index, a resource path, or a JSON
                document violates the portable fixture collection contract.
        """
        candidate = cast(object, root)
        if not isinstance(candidate, Path):
            raise TypeError("root must be a Path.")

        # Resolve the explicit root once. A canonical directory boundary makes
        # every later containment check independent of the process working dir.
        try:
            collection_root = candidate.resolve(strict=True)
        except OSError as error:
            raise ValueError(
                f"Fixture collection root does not exist: {root}."
            ) from error
        if not collection_root.is_dir():
            raise ValueError(f"Fixture collection root must be a directory: {root}.")

        index_path = collection_root / "index.json"
        index_value = _load_json(index_path)
        if not isinstance(index_value, dict):
            raise ValueError("Fixture index root must be a JSON object.")
        index = cast(dict[str, JsonValue], index_value)
        _validate_index_fields(index)

        # The collection name and numeric version select one exact portable
        # interpretation; bool is excluded despite being an int subclass.
        if index["collection"] != "fixtures":
            raise ValueError("Fixture index collection must be 'fixtures'.")
        format_version = index["format_version"]
        if type(format_version) is not int or format_version != _FORMAT_VERSION:
            raise ValueError("Fixture index format_version must be 1.")

        raw_profile = index["profile"]
        if not isinstance(raw_profile, str):
            raise TypeError("Fixture index profile must be a string.")
        profile = validate_open_identifier(OpenIdentifier(raw_profile))

        purpose = index["purpose"]
        if not isinstance(purpose, str) or not purpose.strip():
            raise ValueError("Fixture index purpose must be a non-empty string.")

        resources = _validate_resources(index["resources"])
        documents: dict[str, JsonValue] = {}
        for resource in resources:
            # Resolve symlinks before containment validation. A lexically safe
            # entry must still be rejected if its target leaves the collection.
            resource_path = collection_root.joinpath(*PurePosixPath(resource).parts)
            try:
                resolved_resource = resource_path.resolve(strict=True)
            except OSError as error:
                raise ValueError(
                    f"Fixture resource does not exist: {resource}."
                ) from error
            try:
                resolved_resource.relative_to(collection_root)
            except ValueError as error:
                raise ValueError(
                    f"Fixture resource must remain inside the collection: {resource}."
                ) from error
            if not resolved_resource.is_file():
                raise ValueError(f"Fixture resource must be a file: {resource}.")

            # Eager loading proves the indexed collection is complete before any
            # individual conformance case runs and freezes one coherent snapshot.
            documents[resource] = _load_json(resolved_resource)

        object.__setattr__(self, "_profile", profile)
        object.__setattr__(self, "_resources", resources)
        object.__setattr__(self, "_documents", MappingProxyType(documents))

    @property
    def profile(self) -> OpenIdentifier:
        """Return the validated profile declared by the fixture index."""
        # OpenIdentifier is immutable, so returning the exact retained value does
        # not expose mutable loader or manifest state.
        return self._profile

    @property
    def resources(self) -> tuple[str, ...]:
        """Return declared resource names in canonical index order."""
        # The constructor requires sorted uniqueness and stores a tuple; callers
        # can enumerate the shared collection without receiving a mutable list.
        return self._resources

    def load(self, resource: str) -> JsonValue:
        """Return an independent decoded copy of one declared fixture resource.

        Args:
            resource: Exact POSIX relative path present in :attr:`resources`.

        Returns:
            A deep mutable copy of the resource's decoded JSON value.

        Raises:
            TypeError: If ``resource`` is not a string.
            KeyError: If the exact resource is not declared by the index.
        """
        candidate = cast(object, resource)
        if not isinstance(candidate, str):
            raise TypeError("resource must be a string.")

        # Membership is checked against the validated index snapshot instead of
        # accepting an arbitrary filesystem path at load time.
        try:
            document = self._documents[candidate]
        except KeyError:
            raise KeyError(f"Unknown fixture resource: {candidate}.") from None

        # Each caller owns its result tree while the canonical collection
        # snapshot remains isolated from mutations and later loads.
        return deepcopy(document)


def _validate_index_fields(index: Mapping[str, JsonValue]) -> None:
    """Require the exact version-one fixture index field set."""
    actual = frozenset(index)
    if actual == _INDEX_FIELDS:
        return

    # Stable sorted diagnostics make missing and future unsupported fields
    # produce the same result in every test run.
    missing = sorted(_INDEX_FIELDS - actual)
    unexpected = sorted(actual - _INDEX_FIELDS)
    raise ValueError(
        f"Invalid fixture index fields: missing={missing}, unexpected={unexpected}."
    )


def _validate_resources(value: JsonValue) -> tuple[str, ...]:
    """Return a sorted unique tuple of canonical POSIX resource paths."""
    if not isinstance(value, list):
        raise TypeError("Fixture index resources must be a list.")

    resources: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise TypeError("Fixture resources must be non-empty strings.")

        # PurePosixPath fixes one cross-language separator model. Comparing the
        # round trip rejects backslashes, duplicate separators, and dot segments
        # before any platform-specific Path joins occur.
        portable_path = PurePosixPath(item)
        if (
            "\\" in item
            or portable_path.is_absolute()
            or not portable_path.parts
            or ".." in portable_path.parts
            or portable_path.as_posix() != item
        ):
            raise ValueError(
                f"Fixture resource path must be canonical and relative: {item}."
            )
        resources.append(item)

    if resources != sorted(set(resources)):
        raise ValueError("Fixture resources must be sorted and unique.")
    return tuple(resources)


def _load_json(path: Path) -> JsonValue:
    """Decode one strict UTF-8 JSON file with portable value semantics."""
    try:
        text = path.read_text(encoding="utf-8")
        document = cast(
            JsonValue,
            json.loads(
                text,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_nonstandard_constant,
            ),
        )
        validate_json_value_numbers(document)
        _validate_unicode_scalars(document)
    except (OSError, UnicodeError, ValueError) as error:
        # Include only the resource path and parser diagnostic; fixture contents
        # can be large or sensitive test vectors and are never echoed.
        raise ValueError(
            f"Cannot load valid fixture JSON from {path}: {error}"
        ) from error
    return document


def _unique_object(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    """Build one JSON object while rejecting duplicate member names."""
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        # Duplicate-key handling differs between decoders. Rejecting duplicates
        # prevents language runtimes from selecting different effective values.
        if key in result:
            raise ValueError(f"JSON object contains duplicate key: {key}.")
        result[key] = value
    return result


def _validate_unicode_scalars(value: JsonValue) -> None:
    """Reject unpaired UTF-16 surrogate code points in JSON strings and keys."""
    pending: list[JsonValue] = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            for key, child in current.items():
                # Object names and values share the same Unicode scalar rule so
                # no platform can accept a key that another cannot represent.
                _require_unicode_scalars(key)
                pending.append(child)
            continue
        if isinstance(current, list):
            pending.extend(current)
            continue
        if isinstance(current, str):
            _require_unicode_scalars(current)


def _require_unicode_scalars(value: str) -> None:
    """Require one decoded string to contain only Unicode scalar values."""
    # Python preserves lone surrogate escapes as string code points, while some
    # JSON runtimes reject or replace them. Excluding them fixes cross-language
    # fixture meaning without normalizing valid Unicode or combining sequences.
    if any("\ud800" <= character <= "\udfff" for character in value):
        raise ValueError("Fixture JSON strings must contain Unicode scalar values.")


def _reject_nonstandard_constant(token: str) -> NoReturn:
    """Reject NaN and infinity tokens accepted by Python's JSON extension."""
    # RFC JSON has no non-finite number tokens; failing during decode avoids a
    # Python-only fixture interpretation before shared numeric validation.
    raise ValueError(f"JSON contains non-standard numeric token: {token}.")
