"""Stable component and fixture identity for contract-suite failures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import cast

# Suite module stems are the stable join between pytest node ids and component
# roles. A new contract suite must be added here before CI can locate it.
_SUITE_COMPONENTS = MappingProxyType(
    {
        "test_adapter_contract_suite": "task_protocol_adapter",
        "test_authorization_handler_contract_suite": "authorization_handler",
        "test_authorization_handler_resolver_contract_suite": (
            "authorization_handler_resolver"
        ),
        "test_error_payload_decoder_contract_suite": "error_payload_decoder",
        "test_model_integration_resolver_contract_suite": "model_integration_resolver",
        "test_monitor_contract_suite": "interaction_monitor",
        "test_payload_encoder_contract_suite": "payload_encoder",
        "test_secret_contract_suite": "secret_boundary",
        "test_service_access_resolver_contract_suite": "service_access_resolver",
        "test_success_payload_decoder_contract_suite": "success_payload_decoder",
        "test_transport_contract_suite": "transport",
    }
)


@dataclass(frozen=True, slots=True)
class ContractCase:
    """Name the component and fixture case that produced a contract result.

    These suites define their cases in code, so the fixture id is the pytest
    case name rather than a separate JSON document. The two fields stay free of
    line breaks so a failure note remains a single locatable record.
    """

    component: str
    """Stable component role, such as ``payload_encoder``."""

    fixture: str
    """Stable case id within that component's contract suite."""

    def __post_init__(self) -> None:
        """Reject identities that cannot be printed as one failure record."""
        component = cast(object, self.component)
        fixture = cast(object, self.fixture)
        # Exact strings keep bool and other subclasses from becoming labels.
        # Empty or multiline values would make the CI record ambiguous.
        if type(component) is not str or not _is_single_line(component):
            raise TypeError("component must be a single-line non-empty string.")
        if type(fixture) is not str or not _is_single_line(fixture):
            raise TypeError("fixture must be a single-line non-empty string.")


def contract_suite_components() -> MappingProxyType[str, str]:
    """Return the suite module stems that CI knows how to locate."""
    # A proxy keeps callers from adding a stem that the failure note would
    # then report without a reviewed component role.
    return _SUITE_COMPONENTS


def contract_case_for_node(node_id: str) -> ContractCase | None:
    """Return the contract case for one pytest node id, if it is a known suite.

    Args:
        node_id: Pytest node id, including the path and the case after ``::``.

    Returns:
        The component and fixture case, or ``None`` when the node is not one of
        the registered contract suites or does not carry a usable case id.
    """
    candidate = cast(object, node_id)
    if type(candidate) is not str:
        return None

    # Pytest node ids use POSIX separators. Normalize before taking the stem so
    # a Windows collector cannot miss the suite module.
    normalized = candidate.replace("\\", "/")
    file_part, separator, fixture = normalized.partition("::")
    stem = PurePosixPath(file_part).stem
    component = _SUITE_COMPONENTS.get(stem)
    if component is None:
        return None
    if not separator:
        # A collection error may report only the module. Keep that locatable
        # instead of dropping the component identity.
        fixture = stem
    if not _is_single_line(fixture):
        return None
    return ContractCase(component, fixture)


def annotate_contract_failure(error: BaseException, case: ContractCase) -> None:
    """Attach one component/fixture note without replacing the original failure.

    Args:
        error: The exact exception already raised by the contract case.
        case: Validated component and fixture identity for that case.

    Raises:
        TypeError: If ``error`` is not an exception or ``case`` is not a
            :class:`ContractCase`.
    """
    error_value = cast(object, error)
    case_value = cast(object, case)
    if not isinstance(error_value, BaseException):
        raise TypeError("error must be a BaseException.")
    if not isinstance(case_value, ContractCase):
        raise TypeError("case must be a ContractCase.")

    note = f"component={case.component} fixture={case.fixture}"
    notes = getattr(error, "__notes__", ())
    # A second hook pass must not stack the same location onto one failure.
    if isinstance(notes, list) and note in notes:
        return
    error.add_note(note)


def _is_single_line(value: str) -> bool:
    """Return whether a label is visible and cannot break a failure record."""
    return bool(value) and "\n" not in value and "\r" not in value
