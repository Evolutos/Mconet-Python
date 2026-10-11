"""Component and fixture identity for contract-suite failures."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from mconet.testing import (
    ContractCase,
    annotate_contract_failure,
    contract_case_for_node,
    contract_suite_components,
)


def test_contract_case_rejects_blank_or_multiline_labels() -> None:
    """Keep a failure note to one unambiguous component and fixture line."""
    for component, fixture in (
        ("", "case"),
        ("payload_encoder", ""),
        ("payload\nencoder", "case"),
        ("payload_encoder", "case\r2"),
    ):
        try:
            ContractCase(component, fixture)
        except TypeError as error:
            assert "must be a single-line" in str(error)
        else:
            raise AssertionError("Expected an unusable contract identity to fail.")

    try:
        ContractCase(cast(str, True), "case")
    except TypeError as error:
        assert "component" in str(error)
    else:
        raise AssertionError("Expected a non-string component to fail.")


def test_node_id_maps_each_suite_and_ignores_other_tests() -> None:
    """Locate registered suite cases and leave engineering tests unlabeled."""
    case = contract_case_for_node(
        "tests/unit/testing/test_transport_contract_suite.py::test_cancel[slow]"
    )
    assert case == ContractCase("transport", "test_cancel[slow]")

    module_only = contract_case_for_node(
        "tests\\unit\\testing\\test_monitor_contract_suite.py"
    )
    assert module_only == ContractCase(
        "interaction_monitor", "test_monitor_contract_suite"
    )
    assert (
        contract_case_for_node("tests/contract/test_ci_pipeline.py::test_contract")
        is None
    )
    assert contract_case_for_node("test_transport_contract_suite.py::bad\ncase") is None
    assert contract_case_for_node(cast(str, None)) is None


def test_every_checked_in_suite_module_has_one_component() -> None:
    """Fail when a new contract suite is added without a component role."""
    root = Path(__file__).resolve().parent
    stems = sorted(path.stem for path in root.glob("test_*_contract_suite.py"))

    # The directory is the source of suite modules. The mapping is the source
    # of the component name CI prints, so the two sets must stay identical.
    assert stems == sorted(contract_suite_components())


def test_annotation_adds_one_note_and_keeps_the_original_failure() -> None:
    """Record the location once without replacing the raised exception."""
    failure = AssertionError("boom")
    case = ContractCase("payload_encoder", "encode.empty")

    annotate_contract_failure(failure, case)
    annotate_contract_failure(failure, case)

    assert failure.args == ("boom",)
    assert failure.__notes__ == ["component=payload_encoder fixture=encode.empty"]

    try:
        annotate_contract_failure(cast(BaseException, "boom"), case)
    except TypeError as error:
        assert "BaseException" in str(error)
    else:
        raise AssertionError("Expected a non-exception failure target to fail.")
