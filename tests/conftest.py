"""Locate contract-suite failures to a component and fixture case."""

from __future__ import annotations

from collections.abc import Generator
from typing import Protocol, cast

from mconet.testing import annotate_contract_failure, contract_case_for_node


class _HookResult(Protocol):
    """Structural result object yielded by a pytest hook wrapper."""

    def get_result(self) -> object:
        """Return the report produced by the wrapped hook."""


def pytest_runtest_makereport(
    item: object, call: object
) -> Generator[None, object, None]:
    """Add the suite location before pytest renders a call failure."""
    when = getattr(call, "when", None)
    excinfo = getattr(call, "excinfo", None)
    node_id = getattr(item, "nodeid", None)
    if when == "call" and excinfo is not None and isinstance(node_id, str):
        case = contract_case_for_node(node_id)
        error = getattr(excinfo, "value", None)
        # Annotate before yielding so the rendered traceback includes the note.
        if case is not None and isinstance(error, BaseException):
            annotate_contract_failure(error, case)
            # Pytest writes JUnit properties from the teardown report, which
            # copies this list when that report is built. The call report's
            # own copy is not the one stored in the artifact.
            _record_location(item, case.component, case.fixture)

    outcome = cast(_HookResult, (yield))
    outcome.get_result()


def _record_location(item: object, component: str, fixture: str) -> None:
    """Store the location where the teardown report will copy it."""
    raw_properties = getattr(item, "user_properties", None)
    if not isinstance(raw_properties, list):
        return
    properties = cast(list[object], raw_properties)
    for name, value in (("component", component), ("fixture", fixture)):
        entry = (name, value)
        if entry not in properties:
            properties.append(entry)


# Pytest discovers this marker attribute. Setting it directly avoids importing
# pytest into the type-checked tree, which has no third-party stubs.
setattr(  # noqa: B010 - pytest hook marker is not a declared function attribute
    pytest_runtest_makereport,
    "pytest_impl",
    {
        "wrapper": False,
        "hookwrapper": True,
        "optionalhook": False,
        "tryfirst": False,
        "trylast": False,
        "specname": None,
    },
)
