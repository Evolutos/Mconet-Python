"""Exact plaintext leak assertions for observable test carriers."""

from __future__ import annotations

from collections.abc import Mapping
from types import GetSetDescriptorType, MappingProxyType, MemberDescriptorType
from typing import cast

_LEAK_MESSAGE = "Secret detected in an inspected carrier."
_UNSUPPORTED_MESSAGE = "Secret scan cannot inspect carrier data"


class SecretScanner:
    """Assert that known test plaintext is absent from observable data.

    The scanner performs exact substring and UTF-8 byte-subsequence matching
    across strings, bytes, built-in containers, exceptions, and dataclass value
    objects. These carriers cover headers, encoded bodies, normalized errors,
    monitoring snapshots, and captured log entries without converting values
    through caller-defined ``str`` or ``repr`` hooks.

    Leak diagnostics contain only an ordinal structural location. They never
    include the protected plaintext, a carrier value, a mapping key, or an
    exception supplied by the caller. Unsupported objects fail closed instead
    of being silently skipped. Instances are stateless and retain neither the
    plaintext nor inspected carriers after :meth:`assert_absent` returns.
    """

    __slots__ = ()

    def assert_absent(self, secret: str, *carriers: object) -> None:
        """Require exact test plaintext to be absent from every carrier.

        Args:
            secret: Exact non-empty plaintext whose disclosure must be detected.
            *carriers: Observable runtime values to inspect recursively.

        Raises:
            TypeError: If input is invalid or a carrier cannot be inspected
                safely without invoking caller-defined behavior.
            AssertionError: If the plaintext occurs in a supported carrier.
        """
        candidate = cast(object, secret)
        # Exact built-in text prevents a subclass from changing encoding or
        # containment behavior while this security assertion is running.
        if type(candidate) is not str or not candidate:
            raise TypeError("secret must be a non-empty string.")
        if not carriers:
            raise TypeError("at least one carrier must be provided for scanning.")

        # Encode once for byte carriers. The explicit work stack avoids Python
        # recursion limits, and one visited set terminates shared object graphs.
        secret_bytes = secret.encode("utf-8")
        pending = [
            (carrier, f"carrier[{index}]")
            for index, carrier in reversed(tuple(enumerate(carriers)))
        ]
        visited: set[int] = set()

        while pending:
            value, location = pending.pop()
            _inspect_carrier(value, location, secret, secret_bytes, pending, visited)


def _inspect_carrier(
    value: object,
    location: str,
    secret: str,
    secret_bytes: bytes,
    pending: list[tuple[object, str]],
    visited: set[int],
) -> None:
    """Inspect one value and append safely discoverable children to ``pending``."""
    value_type = type(value)

    # Strings are the common representation for header values, error messages,
    # snapshots, and logs. Use the built-in operation only on exact str values.
    if value_type is str:
        _assert_text_absent(cast(str, value), secret, location)
        return

    # Search byte carriers without decoding them, so invalid UTF-8 around an
    # otherwise exact secret sequence cannot hide a body disclosure.
    if value_type in (bytes, bytearray, memoryview):
        _assert_bytes_absent(value, secret_bytes, location)
        return

    # Primitive non-text leaves cannot contain string plaintext. Other scalar
    # classes remain unsupported because conversion could invoke custom code.
    if value is None or value_type in (bool, int, float):
        return

    # Mark reference-bearing values before descending so self-references and
    # repeated children terminate while every first-reachable value is scanned.
    identity = id(value)
    if identity in visited:
        return
    visited.add(identity)

    if value_type in (dict, MappingProxyType):
        _queue_mapping(value, location, pending)
        return
    if value_type in (list, tuple):
        _queue_sequence(value, location, pending)
        return
    if value_type in (set, frozenset):
        _queue_set(value, location, pending)
        return
    if isinstance(value, BaseException):
        _queue_exception(value, location, secret, pending)
        return
    if _is_dataclass_instance(value):
        _queue_dataclass(value, location, secret, pending)
        return

    # Arbitrary objects can hide state in properties, extension slots, or native
    # resources. Reject them without calling str, repr, iter, or attribute hooks.
    raise _unsupported(location, "object type is not a supported data carrier")


def _queue_mapping(
    value: object,
    location: str,
    pending: list[tuple[object, str]],
) -> None:
    """Queue exact built-in mapping keys and values using ordinal-only paths."""
    try:
        # Exact dict and mappingproxy methods cannot dispatch to caller-defined
        # overrides. Materialize membership before recursive inspection.
        entries = tuple(cast(Mapping[object, object], value).items())
    except BaseException:
        raise _unsupported(location, "mapping entries are unreadable") from None

    for index in range(len(entries) - 1, -1, -1):
        key, item = entries[index]
        # Keys can leak during logging just as values can. Push value first so
        # the LIFO stack visits the key first for deterministic diagnostics.
        pending.append((item, f"{location}.mappingValue[{index}]"))
        pending.append((key, f"{location}.mappingKey[{index}]"))


def _queue_sequence(
    value: object,
    location: str,
    pending: list[tuple[object, str]],
) -> None:
    """Queue exact list or tuple members in their observable order."""
    sequence = cast(list[object] | tuple[object, ...], value)
    # Reverse stack insertion preserves the source order when values are popped.
    for index in range(len(sequence) - 1, -1, -1):
        pending.append((sequence[index], f"{location}.sequenceValue[{index}]"))


def _queue_set(
    value: object,
    location: str,
    pending: list[tuple[object, str]],
) -> None:
    """Queue exact set members without exposing unstable values in diagnostics."""
    try:
        members = tuple(cast(set[object] | frozenset[object], value))
    except BaseException:
        raise _unsupported(location, "set entries are unreadable") from None

    # Python set order is intentionally unspecified, so every member uses the
    # same stable structural location instead of a misleading process-local index.
    pending.extend((member, f"{location}.setValue") for member in members)


def _queue_exception(
    value: BaseException,
    location: str,
    secret: str,
    pending: list[tuple[object, str]],
) -> None:
    """Queue an exception's message arguments, chain, and stored data safely."""
    try:
        # Read through BaseException's native descriptors so a subclass cannot
        # replace args, chaining, or state access with caller-defined behavior.
        name = type.__getattribute__(type(value), "__name__")
        arguments = _read_exception_attribute(value, "args")
        cause = _read_exception_attribute(value, "__cause__")
        context = _read_exception_attribute(value, "__context__")
        state = _read_exception_attribute(value, "__dict__")
    except BaseException:
        raise _unsupported(location, "exception data is unreadable") from None

    _assert_text_absent(name, secret, f"{location}.exceptionType")
    if type(arguments) is not tuple or type(state) is not dict:
        raise _unsupported(location, "exception data is not a built-in container")

    # State keys and values may be rendered by diagnostics. Queue the exception
    # chain as data rather than following traceback frames or their local values.
    _queue_mapping(
        cast(dict[object, object], state), f"{location}.exceptionState", pending
    )
    if context is not None:
        pending.append((context, f"{location}.exceptionContext"))
    if cause is not None:
        pending.append((cause, f"{location}.exceptionCause"))
    pending.append(
        (cast(tuple[object, ...], arguments), f"{location}.exceptionArguments")
    )

    # Frozen slot dataclass exceptions, including ModelInteractionError, retain
    # structured fields outside __dict__. Read only native dataclass storage.
    if _is_dataclass_instance(value):
        _queue_dataclass(value, f"{location}.exceptionFields", secret, pending)


def _read_exception_attribute(value: BaseException, name: str) -> object:
    """Read one BaseException-owned attribute without subclass dispatch."""
    namespace = type.__getattribute__(BaseException, "__dict__")
    descriptor = namespace.get(name)
    if type(descriptor) is not GetSetDescriptorType:
        # This is an interpreter invariant failure, but use the same safe error
        # family and no dynamic value if an unsupported runtime violates it.
        raise TypeError(f"{_UNSUPPORTED_MESSAGE}: exception layout is unsupported.")
    return descriptor.__get__(value, type(value))


def _is_dataclass_instance(value: object) -> bool:
    """Detect inherited dataclass metadata without instance attribute dispatch."""
    return _dataclass_field_mapping(value) is not None


def _dataclass_field_mapping(value: object) -> dict[object, object] | None:
    """Return native dataclass metadata discovered from class namespaces only."""
    # Read every class namespace through type's native descriptor. This bypasses
    # custom metaclass and instance __getattribute__ hooks used by hostile data.
    owners = type.__getattribute__(type(value), "__mro__")
    for owner in owners:
        namespace = type.__getattribute__(owner, "__dict__")
        if "__dataclass_fields__" in namespace:
            metadata = namespace["__dataclass_fields__"]
            return (
                cast(dict[object, object], metadata) if type(metadata) is dict else None
            )
    return None


def _queue_dataclass(
    value: object,
    location: str,
    secret: str,
    pending: list[tuple[object, str]],
) -> None:
    """Queue native dataclass field storage without evaluating properties."""
    try:
        class_name = type.__getattribute__(type(value), "__name__")
        field_mapping = _dataclass_field_mapping(value)
    except BaseException:
        raise _unsupported(location, "dataclass metadata is unreadable") from None

    if field_mapping is None:
        raise _unsupported(location, "dataclass metadata is not a built-in mapping")
    field_names = tuple(field_mapping)
    if any(type(name) is not str for name in field_names):
        raise _unsupported(location, "dataclass field names are not strings")

    _assert_text_absent(class_name, secret, f"{location}.dataclassType")
    for index in range(len(field_names) - 1, -1, -1):
        field_name = cast(str, field_names[index])
        # A generated field name can appear in repr output, so inspect it while
        # keeping the diagnostic path ordinal and free of caller-controlled text.
        _assert_text_absent(field_name, secret, f"{location}.fieldName[{index}]")
        field_value = _read_dataclass_field(value, field_name, location)
        pending.append((field_value, f"{location}.fieldValue[{index}]"))


def _read_dataclass_field(value: object, name: str, location: str) -> object:
    """Read one dataclass field only from a real instance dict or native slot."""
    state = _read_native_instance_state(value, location)
    if state is not None:
        if name in state:
            return state[name]

    # Slotted dataclasses store fields in native member descriptors. Reject any
    # property, custom descriptor, or missing declaration instead of invoking it.
    owners = type.__getattribute__(type(value), "__mro__")
    for owner in owners:
        namespace = type.__getattribute__(owner, "__dict__")
        descriptor = namespace.get(name)
        if type(descriptor) is MemberDescriptorType:
            try:
                return descriptor.__get__(value, type(value))
            except BaseException:
                raise _unsupported(location, "dataclass slot is unreadable") from None
        if descriptor is not None:
            break
    raise _unsupported(location, "dataclass field is not native stored data")


def _read_native_instance_state(
    value: object,
    location: str,
) -> dict[str, object] | None:
    """Read an instance dictionary only through its native class descriptor."""
    owners = type.__getattribute__(type(value), "__mro__")
    for owner in owners:
        namespace = type.__getattribute__(owner, "__dict__")
        descriptor = namespace.get("__dict__")
        if descriptor is None:
            continue
        if type(descriptor) is not GetSetDescriptorType:
            raise _unsupported(location, "dataclass state uses a custom descriptor")
        try:
            state = descriptor.__get__(value, type(value))
        except BaseException:
            raise _unsupported(location, "dataclass state is unreadable") from None
        if type(state) is not dict:
            raise _unsupported(location, "dataclass state is not a built-in mapping")
        return cast(dict[str, object], state)
    return None


def _assert_text_absent(value: str, secret: str, location: str) -> None:
    """Reject one exact string containing the protected plaintext."""
    # Exact substring matching is appropriate because the test owns the known
    # plaintext; heuristic credential detection belongs to repository tooling.
    if secret in value:
        raise AssertionError(f"{_LEAK_MESSAGE} Location: {location}.")


def _assert_bytes_absent(value: object, secret: bytes, location: str) -> None:
    """Reject one exact binary carrier containing the UTF-8 plaintext bytes."""
    try:
        # memoryview.tobytes respects the visible slice; bytes() snapshots mutable
        # bytearray data before the containment check.
        if type(value) is memoryview:
            content = value.tobytes()
        elif type(value) is bytes:
            content = value
        else:
            content = bytes(cast(bytearray, value))
    except BaseException:
        raise _unsupported(location, "binary data is unreadable") from None
    if secret in content:
        raise AssertionError(f"{_LEAK_MESSAGE} Location: {location}.")


def _unsupported(location: str, reason: str) -> TypeError:
    """Create a fail-closed diagnostic containing implementation-owned text."""
    # Location and reason are constructed only by this module. No carrier value,
    # field name, secret, or caught exception is attached to the result.
    return TypeError(f"{_UNSUPPORTED_MESSAGE} at {location}: {reason}.")
