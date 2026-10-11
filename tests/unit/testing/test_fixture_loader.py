"""Collection, isolation, and safety tests for FixtureLoader."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

from mconet.core.domain import JsonValue, OpenIdentifier
from mconet.testing import FixtureLoader

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_COMMITTED_FIXTURES = _PROJECT_ROOT / "spec" / "fixtures" / "r1-text-unary"


def _write_json(path: Path, value: JsonValue) -> None:
    """Write one deterministic UTF-8 JSON document for an isolated test case."""
    # Stable formatting keeps temporary fixtures readable when a failed test
    # reports its path while exercising the production file boundary.
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _collection(
    root: Path,
    *,
    resources: tuple[str, ...] = ("cases/basic.json",),
) -> Path:
    """Create one valid indexed fixture collection under an isolated root."""
    root.mkdir()
    for resource in resources:
        resource_path = root.joinpath(*resource.split("/"))
        resource_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(resource_path, {"resource": resource, "values": [1, True, None]})

    # The manifest mirrors the language-neutral checked-in collection contract;
    # callers may overwrite it to isolate one invalid boundary at a time.
    _write_json(
        root / "index.json",
        {
            "collection": "fixtures",
            "format_version": 1,
            "profile": "test.fixture-profile",
            "purpose": "FixtureLoader contract tests.",
            "resources": list(resources),
        },
    )
    return root


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Require one loader action to fail at the intended stable boundary."""
    try:
        action()
    except exception_type as error:
        # A stable fragment separates manifest, path, decode, and lookup errors
        # without coupling tests to platform-specific absolute paths.
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_fixture_loader_reads_the_committed_cross_language_collection() -> None:
    """Load the shared profile and exact resources used by conformance tests."""
    loader = FixtureLoader(_COMMITTED_FIXTURES)

    # The profile and sorted manifest order come from the same checked-in index
    # consumed by every language implementation, not Python-only discovery.
    assert loader.profile == OpenIdentifier("r1.text-unary")
    assert loader.resources == (
        "artifact.json",
        "configuration-overrides.json",
        "configuration-precedence.json",
        "conversation-request.json",
        "conversation-result.json",
        "foundation-values.json",
        "json-codec.json",
        "message-document.json",
        "model-target.json",
        "openai-chat-error.json",
        "openai-chat-request.json",
        "openai-chat-response.json",
        "service-access.json",
    )

    foundation = loader.load("foundation-values.json")
    assert isinstance(foundation, dict)
    assert foundation["schemaId"] == "schema.foundation_values"
    assert "open_identifier" in cast(dict[str, object], foundation["types"])


def test_fixture_loader_snapshots_sources_and_isolates_loaded_values(
    tmp_path: Path,
) -> None:
    """Keep one coherent collection despite file and result mutations."""
    root = _collection(tmp_path / "fixtures")
    loader = FixtureLoader(root)
    resource_path = root / "cases" / "basic.json"

    # Files are snapshotted during construction. Mutating both the source file
    # and the first loaded tree cannot change a later independent load result.
    _write_json(resource_path, {"changed": True})
    first = loader.load("cases/basic.json")
    assert isinstance(first, dict)
    first["resource"] = "mutated"

    assert loader.load("cases/basic.json") == {
        "resource": "cases/basic.json",
        "values": [1, True, None],
    }


def test_fixture_loader_accepts_any_valid_json_resource_root(tmp_path: Path) -> None:
    """Preserve scalar and array fixtures without imposing an object envelope."""
    root = _collection(
        tmp_path / "fixtures",
        resources=("array.json", "scalar.json"),
    )
    _write_json(root / "array.json", ["first", {"second": 2}])
    _write_json(root / "scalar.json", "text")

    loader = FixtureLoader(root)

    # Fixture structure belongs to its schema or consuming contract; the loader
    # validates generic JSON and does not add a Python-specific object root rule.
    assert loader.load("array.json") == ["first", {"second": 2}]
    assert loader.load("scalar.json") == "text"


def test_fixture_loader_rejects_invalid_index_contracts(tmp_path: Path) -> None:
    """Reject missing, unexpected, mistyped, and unsupported index metadata."""
    root = _collection(tmp_path / "fixtures")
    index_path = root / "index.json"
    valid_index: dict[str, JsonValue] = {
        "collection": "fixtures",
        "format_version": 1,
        "profile": "test.fixture-profile",
        "purpose": "FixtureLoader contract tests.",
        "resources": ["cases/basic.json"],
    }
    invalid_indexes: tuple[
        tuple[dict[str, JsonValue], type[BaseException], str], ...
    ] = (
        (
            {key: value for key, value in valid_index.items() if key != "profile"},
            ValueError,
            "missing=['profile']",
        ),
        (
            {**valid_index, "extra": True},
            ValueError,
            "unexpected=['extra']",
        ),
        ({**valid_index, "collection": "schemas"}, ValueError, "must be 'fixtures'"),
        ({**valid_index, "format_version": True}, ValueError, "must be 1"),
        ({**valid_index, "profile": 1}, TypeError, "profile must be a string"),
        ({**valid_index, "profile": "Invalid"}, ValueError, "lowercase"),
        ({**valid_index, "purpose": "  "}, ValueError, "non-empty string"),
        ({**valid_index, "resources": {}}, TypeError, "must be a list"),
    )

    for index, exception_type, message in invalid_indexes:
        # Recreate only the index between attempts; the valid declared resource
        # remains present so each failure belongs to metadata validation alone.
        _write_json(index_path, index)
        _assert_raises(exception_type, lambda: FixtureLoader(root), message)


def test_fixture_loader_rejects_nonportable_resource_lists(tmp_path: Path) -> None:
    """Reject traversal, platform separators, non-canonical order, and duplicates."""
    root = _collection(tmp_path / "fixtures")
    index_path = root / "index.json"
    invalid_lists: tuple[tuple[list[JsonValue], type[BaseException], str], ...] = (
        (["../outside.json"], ValueError, "canonical and relative"),
        (["/absolute.json"], ValueError, "canonical and relative"),
        (["cases\\basic.json"], ValueError, "canonical and relative"),
        (["."], ValueError, "canonical and relative"),
        (["cases//basic.json"], ValueError, "canonical and relative"),
        (["cases/./basic.json"], ValueError, "canonical and relative"),
        (["z.json", "a.json"], ValueError, "sorted and unique"),
        (["cases/basic.json", "cases/basic.json"], ValueError, "sorted and unique"),
        ([1], TypeError, "non-empty strings"),
    )

    for resources, exception_type, message in invalid_lists:
        _write_json(
            index_path,
            {
                "collection": "fixtures",
                "format_version": 1,
                "profile": "test.fixture-profile",
                "purpose": "FixtureLoader contract tests.",
                "resources": resources,
            },
        )
        _assert_raises(exception_type, lambda: FixtureLoader(root), message)


def test_fixture_loader_rejects_missing_directory_and_resources(tmp_path: Path) -> None:
    """Require an explicit existing directory and every indexed regular file."""
    missing_root = tmp_path / "missing"
    _assert_raises(
        ValueError,
        lambda: FixtureLoader(missing_root),
        "root does not exist",
    )
    _assert_raises(
        TypeError,
        lambda: FixtureLoader(cast(Path, str(missing_root))),
        "root must be a Path",
    )

    file_root = tmp_path / "file-root"
    file_root.write_text("not a directory", encoding="utf-8")
    _assert_raises(
        ValueError,
        lambda: FixtureLoader(file_root),
        "root must be a directory",
    )

    root = _collection(tmp_path / "fixtures")
    (root / "cases" / "basic.json").unlink()
    _assert_raises(
        ValueError,
        lambda: FixtureLoader(root),
        "resource does not exist",
    )


def test_fixture_loader_rejects_malformed_and_ambiguous_json(tmp_path: Path) -> None:
    """Reject syntax errors, duplicate keys, and non-portable numeric values."""
    invalid_documents = (
        ("{", "Expecting property name"),
        ('{"same": 1, "same": 2}', "duplicate key: same"),
        ('{"number": NaN}', "non-standard numeric token: NaN"),
        ('{"number": 9007199254740992}', "safe range"),
        ('{"text": "\\ud800"}', "Unicode scalar values"),
    )

    for index, (document, message) in enumerate(invalid_documents):
        root = _collection(tmp_path / f"fixtures-{index}")
        (root / "cases" / "basic.json").write_text(document, encoding="utf-8")

        # Construction validates every declared resource eagerly, preventing a
        # partially valid collection from producing language-specific results.
        _assert_raises(
            ValueError,
            lambda root=root: FixtureLoader(root),
            message,
        )


def test_fixture_loader_loads_only_exact_declared_resource_names(
    tmp_path: Path,
) -> None:
    """Prevent filesystem probing and dynamic path interpretation during load."""
    root = _collection(tmp_path / "fixtures")
    _write_json(root / "unlisted.json", {"visible": False})
    loader = FixtureLoader(root)

    invalid_calls: tuple[tuple[Callable[[], object], type[BaseException], str], ...] = (
        (
            lambda: loader.load("unlisted.json"),
            KeyError,
            "Unknown fixture resource: unlisted.json",
        ),
        (
            lambda: loader.load("cases/../unlisted.json"),
            KeyError,
            "Unknown fixture resource: cases/../unlisted.json",
        ),
        (
            lambda: loader.load(cast(str, Path("cases/basic.json"))),
            TypeError,
            "resource must be a string",
        ),
    )

    for action, exception_type, message in invalid_calls:
        # Load performs exact index membership only; it never reinterprets the
        # caller value as a path or discovers an unlisted file from disk.
        _assert_raises(exception_type, action, message)
