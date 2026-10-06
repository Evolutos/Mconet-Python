"""Immutable default behavior tests for NamedModel."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import (
    Extensions,
    JsonValue,
    ModelDescriptor,
    NamedModel,
    OpenIdentifier,
)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _mutate_mapping(mapping: dict[str, JsonValue]) -> None:
    """Attempt one item assignment through a dynamically narrowed mapping."""
    mapping["x"] = 1


def test_named_model_has_immutable_neutral_defaults() -> None:
    """Verify optional facts stay absent and mapping defaults stay immutable."""
    model = NamedModel("provider-model-2026")

    # A model name is opaque: suffixes do not imply family or version facts.
    assert model.name == "provider-model-2026"
    assert model.display_name is None
    assert model.family is None
    assert model.version is None
    assert model.description is None
    assert model.metadata == {}
    assert model.extensions == {}
    assert isinstance(model, ModelDescriptor)
    _assert_raises(
        FrozenInstanceError,
        lambda: model.__setattr__("name", "other"),
        "cannot assign to field",
    )
    _assert_raises(
        TypeError,
        lambda: _mutate_mapping(cast(dict[str, JsonValue], model.metadata)),
        "does not support item assignment",
    )


def test_named_model_preserves_explicit_facts_without_inference() -> None:
    """Verify supplied family, version, metadata, and extensions remain exact."""
    metadata: dict[str, JsonValue] = {"contextWindow": 128_000}
    extensions: dict[str, JsonValue] = {"futureField": {"enabled": True}}
    model = NamedModel(
        name="opaque-name",
        display_name="Display Name",
        family=OpenIdentifier("vendor.family"),
        version="2026-10",
        description="Description",
        metadata=metadata,
        extensions=extensions,
    )

    # Top-level snapshots detach membership from caller-owned dictionaries.
    metadata["contextWindow"] = 1
    extensions["other"] = None
    assert model.family == OpenIdentifier("vendor.family")
    assert model.version == "2026-10"
    assert model.metadata == {"contextWindow": 128_000}
    assert model.extensions == {"futureField": {"enabled": True}}


def test_named_model_rejects_invalid_storage_shapes() -> None:
    """Verify dynamic callers cannot bypass primitive and mapping boundaries."""
    _assert_raises(
        TypeError,
        lambda: NamedModel(cast(str, 1)),
        "name must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: NamedModel("model", family=cast(OpenIdentifier, "family")),
        "family must be an OpenIdentifier",
    )
    _assert_raises(
        TypeError,
        lambda: NamedModel("model", metadata=cast(Extensions, [])),
        "metadata must be a mapping",
    )
