import importlib
import importlib.util
from types import ModuleType

import pytest

# NB: `from platform_observability import setup` would give the setup() FUNCTION (re-exported in __init__),
# not the module of the same name, so the module is imported explicitly.
obs_setup: ModuleType = importlib.import_module("platform_observability.setup")


def test_optional_instrumentation_skips_libraries_that_are_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: the production image has no `redis`; start-up must not crash because of it."""
    imported: list[str] = []
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a, **k: None)
    monkeypatch.setattr(importlib, "import_module", lambda name: imported.append(name))
    obs_setup._instrument_optional()
    assert imported == []  # nothing was even imported
