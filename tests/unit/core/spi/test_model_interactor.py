"""R1 surface tests for the public model interactor protocol."""

from __future__ import annotations

import inspect

from mconet.core.domain import ModelOutput, ModelRequest
from mconet.core.spi import InteractionOptions, ModelInteractor


class _Interactor:
    """Interactor that exposes only the unary method."""

    async def interact(
        self,
        request: ModelRequest,
        options: InteractionOptions,
    ) -> ModelOutput:
        """Return no output because the test does not call this method."""
        del request, options
        raise AssertionError("interact must not be called.")


class _MissingInteract:
    """Object that does not implement the unary method."""


def test_r1_interactor_exposes_only_interact() -> None:
    """Verify a unary implementation matches and streaming methods are absent."""
    interactor = _Interactor()
    assert isinstance(interactor, ModelInteractor)
    assert inspect.iscoroutinefunction(_Interactor.interact)
    assert not isinstance(_MissingInteract(), ModelInteractor)
    for name in ("stream", "send_stream", "open_session", "submit"):
        assert not hasattr(ModelInteractor, name)
