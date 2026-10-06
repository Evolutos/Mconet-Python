"""Conformance checks for language-neutral configuration precedence rules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from mconet.core.domain import JsonValue

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_PATH = (
    _PROJECT_ROOT
    / "spec"
    / "fixtures"
    / "r1-text-unary"
    / "configuration-precedence.json"
)
_INDEX_PATH = _FIXTURE_PATH.parent / "index.json"
_EXPECTED_FIELDS = {
    "cancellationSignal": ("interaction",),
    "compatibilityPolicy": (
        "interaction",
        "client",
        "sdk_safe_default",
    ),
    "monitoring.mergeMode": (
        "interaction",
        "sdk_safe_default",
    ),
    "resourceLimits.maxFrameBytes": (
        "interaction",
        "client",
        "sdk_safe_default",
    ),
    "resourceLimits.maxResponseBodyBytes": (
        "interaction",
        "client",
        "sdk_safe_default",
    ),
    "resourceLimits.maxStreamingErrorBodyBytes": (
        "interaction",
        "client",
        "sdk_safe_default",
    ),
    "serviceAccess": (
        "interaction",
        "request",
        "client",
        "integration",
    ),
    "target": ("request", "client"),
}
_EXPECTED_MONITOR_ORDERS = {
    "append": ("client", "interaction"),
    "prepend": ("interaction", "client"),
    "replace": ("interaction",),
}
_SOURCE_VOCABULARY = frozenset(
    {
        "client",
        "integration",
        "interaction",
        "request",
        "sdk_safe_default",
    }
)


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON document and require an object root."""
    # Fixture contracts use named fields at the root so future version changes
    # can be detected without relying on array position or implicit file context.
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object fixture in {path}.")
    return document


def _require_object(
    value: JsonValue | None,
    field_name: str,
) -> dict[str, JsonValue]:
    """Return one required object-valued fixture field with a clear diagnostic."""
    # Reject missing and scalar values at the same boundary so individual tests
    # can reason about the exact nested contract without unsafe assumptions.
    if not isinstance(value, dict):
        raise AssertionError(f"{field_name} must be a JSON object.")
    return value


def _require_source_order(
    value: JsonValue | None,
    field_name: str,
) -> tuple[str, ...]:
    """Return a nonempty, duplicate-free source order for one fixture field."""
    # Every position is semantically significant: index zero is the winning
    # source when all listed values are present, and later entries are fallbacks.
    if not isinstance(value, list) or not value:
        raise AssertionError(f"{field_name} must have a nonempty source list.")
    if any(not isinstance(source, str) or not source for source in value):
        raise AssertionError(f"{field_name} source names must be nonempty strings.")

    sources = tuple(cast(str, source) for source in value)
    if len(sources) != len(set(sources)):
        raise AssertionError(f"{field_name} source order must not contain duplicates.")
    return sources


def test_configuration_precedence_fixture_is_registered() -> None:
    """Verify the language-neutral fixture is discoverable from its collection."""
    index = _load_object(_INDEX_PATH)
    resources = index.get("resources")

    # Registration is part of the module contract; an otherwise valid orphaned
    # file would be invisible to cross-language conformance runners.
    assert isinstance(resources, list)
    assert "configuration-precedence.json" in resources


def test_configuration_precedence_fixture_has_stable_envelope() -> None:
    """Verify version, direction, semantics, and safe defaults are explicit."""
    fixture = _load_object(_FIXTURE_PATH)

    # Exact root fields prevent prose-only or implementation-specific additions
    # from silently changing the portable precedence contract.
    assert frozenset(fixture) == frozenset(
        {
            "fieldSourceOrder",
            "format_version",
            "monitorSourceOrderByMode",
            "precedenceDirection",
            "safeDefaults",
            "selectionSemantics",
        }
    )
    assert fixture["format_version"] == 1
    assert fixture["precedenceDirection"] == "highest_to_lowest"
    assert fixture["selectionSemantics"] == {
        "missingValue": "continue_to_next_source",
        "presentValue": "select_and_stop",
        "resourceLimits": "resolve_each_field_independently",
    }
    assert fixture["safeDefaults"] == {
        "compatibilityPolicy": "compatible",
        "monitoring.mergeMode": "append",
    }


def test_configuration_field_source_orders_are_complete() -> None:
    """Verify every resolved data field has its architecture-defined fallback order."""
    fixture = _load_object(_FIXTURE_PATH)
    field_orders = _require_object(
        fixture.get("fieldSourceOrder"),
        "fieldSourceOrder",
    )

    # The exact key set covers every resolved configuration dimension and each
    # independent byte limit; adding or dropping a field requires fixture review.
    assert frozenset(field_orders) == frozenset(_EXPECTED_FIELDS)
    for field_name, expected_order in _EXPECTED_FIELDS.items():
        actual_order = _require_source_order(field_orders.get(field_name), field_name)
        assert actual_order == expected_order
        assert set(actual_order) <= _SOURCE_VOCABULARY


def test_monitor_source_orders_follow_each_merge_mode() -> None:
    """Verify append, prepend, and replace produce deterministic monitor order."""
    fixture = _load_object(_FIXTURE_PATH)
    monitor_orders = _require_object(
        fixture.get("monitorSourceOrderByMode"),
        "monitorSourceOrderByMode",
    )

    # Merge modes order Client defaults and single-interaction monitors without
    # treating an empty explicit list as a missing selection value.
    assert frozenset(monitor_orders) == frozenset(_EXPECTED_MONITOR_ORDERS)
    for mode, expected_order in _EXPECTED_MONITOR_ORDERS.items():
        actual_order = _require_source_order(monitor_orders.get(mode), mode)
        assert actual_order == expected_order
        assert set(actual_order) <= _SOURCE_VOCABULARY
