"""Value and rejection tests for protocol body-signing requirements."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from typing import cast

from mconet.core.domain import OpenIdentifier
from mconet.core.spi import BodySigningMode, BodySigningRequirement

_MAX_SIGNED_INT64 = (1 << 63) - 1


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match requirement-owned wording so fixture construction or a different
        # validation branch cannot make a negative signing test pass accidentally.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_body_signing_requirement_defaults_to_canonical_none_mode() -> None:
    """Verify the default requirement represents no body signing exactly."""
    requirement = BodySigningRequirement()

    # The initial release path has one unambiguous no-signing representation and
    # carries no unused algorithm or buffering configuration.
    assert requirement.required is False
    assert requirement.acceptable_modes == ("none",)
    assert requirement.digest_algorithms == frozenset()
    assert requirement.max_buffer_bytes is None


def test_body_signing_requirement_preserves_non_none_rejection_facts() -> None:
    """Verify a future signing requirement remains available to the runtime guard."""
    algorithm = OpenIdentifier("sha256")
    algorithms = frozenset((algorithm,))
    modes: tuple[BodySigningMode, ...] = (
        "precomputed_digest",
        "unsigned_payload",
    )

    requirement = BodySigningRequirement(True, modes, algorithms)

    # The value does not downgrade unsupported initial-release modes to none;
    # authorization can deterministically reject them before credential access.
    assert requirement.required is True
    assert requirement.acceptable_modes is modes
    assert requirement.digest_algorithms is algorithms
    assert requirement.max_buffer_bytes is None
    assert "none" not in requirement.acceptable_modes


def test_body_signing_requirement_preserves_mode_preference_and_buffer_limit() -> None:
    """Verify ordered future modes and bounded buffering remain exact."""
    modes: tuple[BodySigningMode, ...] = (
        "precomputed_digest",
        "buffered_digest",
        "chunked_signature",
    )
    algorithms = frozenset((OpenIdentifier("sha256"), OpenIdentifier("sha512")))

    requirement = BodySigningRequirement(True, modes, algorithms, 8_388_608)

    # Handler resolution consumes modes from left to right; neither tuple order,
    # algorithm membership, nor the explicit cap is inferred or normalized.
    assert requirement.acceptable_modes is modes
    assert requirement.digest_algorithms is algorithms
    assert requirement.max_buffer_bytes == 8_388_608


def test_body_signing_requirement_has_immutable_value_semantics() -> None:
    """Verify every protocol fact participates in equality and frozen storage."""
    first = BodySigningRequirement()
    same = BodySigningRequirement(False, ("none",), frozenset(), None)
    required = BodySigningRequirement(True, ("unsigned_payload",))

    # Canonical no-signing instances compare and hash equally, while required
    # signing stays distinct and no field can change after plan creation.
    assert first == same
    assert hash(first) == hash(same)
    assert first != required
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("required", True),
        "cannot assign to field",
    )


def test_body_signing_requirement_exposes_only_protocol_requirements() -> None:
    """Verify authentication policy and resolved handler stay outside the value."""
    requirement = BodySigningRequirement()

    # The four-field surface records only plan facts and cannot select handlers,
    # inspect body metadata, fetch credentials, or carry a generated signature.
    assert tuple(field.name for field in fields(BodySigningRequirement)) == (
        "required",
        "acceptable_modes",
        "digest_algorithms",
        "max_buffer_bytes",
    )
    assert not hasattr(requirement, "handler")
    assert not hasattr(requirement, "authorization")
    assert not hasattr(requirement, "body_metadata")
    assert not hasattr(requirement, "signature")


def test_body_signing_requirement_requires_exact_boolean() -> None:
    """Verify numeric and textual flags cannot become signing policy."""
    invalid_values: tuple[object, ...] = (0, 1, "false", None, object())

    # Python's bool/int relationship must not introduce coercion semantics that
    # differ from other bindings' explicit Boolean representation.
    for required in invalid_values:
        _assert_raises(
            TypeError,
            lambda required=required: BodySigningRequirement(
                cast(bool, required), ("none",)
            ),
            "required must be a boolean",
        )


def test_body_signing_requirement_requires_nonempty_mode_tuple() -> None:
    """Verify mode preference uses a nonempty immutable ordered collection."""
    invalid_collections: tuple[object, ...] = (
        ["none"],
        {"none"},
        frozenset(("none",)),
    )

    # Lists permit mutation and set forms discard protocol preference order, so
    # construction rejects them instead of silently taking a snapshot.
    for modes in invalid_collections:
        _assert_raises(
            TypeError,
            lambda modes=modes: BodySigningRequirement(
                False, cast(tuple[BodySigningMode, ...], modes)
            ),
            "acceptable_modes must be a tuple",
        )
    _assert_raises(
        ValueError,
        lambda: BodySigningRequirement(True, cast(tuple[BodySigningMode, ...], ())),
        "acceptable_modes must not be empty",
    )


def test_body_signing_requirement_rejects_invalid_or_duplicate_modes() -> None:
    """Verify the closed mode vocabulary remains unique and type-safe."""
    invalid_modes: tuple[object, ...] = ("vendor_signing", "None", 1, None)

    # Unknown strings are not portable protocol modes, while non-strings cannot
    # satisfy even the primitive representation of the closed vocabulary.
    for mode in invalid_modes:
        expected_error = TypeError if not isinstance(mode, str) else ValueError
        expected_message = (
            "must contain strings"
            if expected_error is TypeError
            else "contains an unsupported mode"
        )
        _assert_raises(
            expected_error,
            lambda mode=mode: BodySigningRequirement(
                True, cast(tuple[BodySigningMode, ...], (mode,))
            ),
            expected_message,
        )
    _assert_raises(
        ValueError,
        lambda: BodySigningRequirement(True, ("unsigned_payload", "unsigned_payload")),
        "must not contain duplicates",
    )


def test_body_signing_requirement_enforces_required_mode_coherence() -> None:
    """Verify none cannot be mixed with required or optional signing modes."""
    invalid_requirements = (
        (True, cast(tuple[BodySigningMode, ...], ("none",))),
        (
            True,
            cast(
                tuple[BodySigningMode, ...],
                ("none", "precomputed_digest"),
            ),
        ),
        (False, cast(tuple[BodySigningMode, ...], ("unsigned_payload",))),
    )

    # Required signing cannot resolve to none; optional signing has exactly the
    # canonical none-only representation documented by the architecture.
    for required, modes in invalid_requirements:
        message = (
            "required signing cannot accept none"
            if required
            else "optional signing must accept only none"
        )
        _assert_raises(
            ValueError,
            lambda required=required, modes=modes: BodySigningRequirement(
                required, modes
            ),
            message,
        )


def test_body_signing_requirement_requires_immutable_open_algorithms() -> None:
    """Verify algorithm negotiation uses an immutable open identifier set."""
    invalid_collections: tuple[object, ...] = (
        {OpenIdentifier("sha256")},
        (OpenIdentifier("sha256"),),
        [OpenIdentifier("sha256")],
    )

    # Mutable or ordered containers are not the architecture's Set semantics and
    # therefore are rejected without implicit conversion.
    for algorithms in invalid_collections:
        _assert_raises(
            TypeError,
            lambda algorithms=algorithms: BodySigningRequirement(
                True,
                ("precomputed_digest",),
                cast(frozenset[OpenIdentifier], algorithms),
            ),
            "digest_algorithms must be a frozenset",
        )
    _assert_raises(
        TypeError,
        lambda: BodySigningRequirement(
            True,
            ("precomputed_digest",),
            cast(frozenset[OpenIdentifier], frozenset(("sha256",))),
        ),
        "digest_algorithms must contain OpenIdentifier values",
    )


def test_none_body_signing_rejects_unused_signing_metadata() -> None:
    """Verify the canonical none form cannot carry ignored signing settings."""
    _assert_raises(
        ValueError,
        lambda: BodySigningRequirement(
            False,
            ("none",),
            frozenset((OpenIdentifier("sha256"),)),
        ),
        "none mode cannot declare digest algorithms",
    )
    _assert_raises(
        ValueError,
        lambda: BodySigningRequirement(False, ("none",), frozenset(), 1024),
        "none mode cannot declare max_buffer_bytes",
    )
    _assert_raises(
        TypeError,
        lambda: BodySigningRequirement(
            False,
            ("none",),
            frozenset(),
            cast(int, "1024"),
        ),
        "max_buffer_bytes must be an integer or None",
    )


def test_body_signing_requirement_validates_buffer_limit() -> None:
    """Verify buffering uses an explicit positive portable Int64 byte limit."""
    valid = BodySigningRequirement(
        True,
        ("buffered_digest",),
        frozenset((OpenIdentifier("sha256"),)),
        _MAX_SIGNED_INT64,
    )
    assert valid.max_buffer_bytes == _MAX_SIGNED_INT64

    # bool, float, and string values are not exact integer byte counts; zero,
    # negatives, and overflow cannot express a safe portable buffering bound.
    for limit in (True, 1.0, "1024"):
        _assert_raises(
            TypeError,
            lambda limit=limit: BodySigningRequirement(
                True,
                ("buffered_digest",),
                frozenset(),
                cast(int, limit),
            ),
            "max_buffer_bytes must be an integer or None",
        )
    for limit in (0, -1, 1 << 63):
        _assert_raises(
            ValueError,
            lambda limit=limit: BodySigningRequirement(
                True, ("buffered_digest",), frozenset(), limit
            ),
            "must be a positive signed 64-bit integer",
        )


def test_buffer_limit_and_mode_must_be_declared_together() -> None:
    """Verify buffering cannot be selected without a cap or capped when absent."""
    _assert_raises(
        ValueError,
        lambda: BodySigningRequirement(True, ("buffered_digest",)),
        "buffered_digest requires max_buffer_bytes",
    )
    _assert_raises(
        ValueError,
        lambda: BodySigningRequirement(
            True, ("precomputed_digest",), frozenset(), 1024
        ),
        "max_buffer_bytes requires buffered_digest",
    )
