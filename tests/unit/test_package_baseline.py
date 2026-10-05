"""S0 package baseline tests."""

import importlib


def test_package_imports() -> None:
    # Verify the minimal distribution exposes only its declared root API.
    module = importlib.import_module("mconet")
    assert module.__all__ == ()
