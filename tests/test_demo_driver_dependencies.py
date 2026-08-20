"""The Stack workflow must install what the demo drivers actually import.

The protocol package is light by construction: `import legivellum` must not
drag in SQLAlchemy and FastAPI, because every gate installs it and most of them
have no use for the control plane. The heavy pieces sit behind extras and a
lazy module `__getattr__`.

The demo driver scripts are not all protocol-only, though. `topology_path.py`
and `bind_asyncgate_path.py` import `legivellum.problemata_control`, which
imports SQLAlchemy at module scope. Installing the base package and running
them gives `ModuleNotFoundError: No module named 'sqlalchemy'` at import time,
before any assertion in the demo runs.

That is what happened: the Stack gate installed `-e ./LegiVellum` with no
extras, and the topology path died on import. It went unnoticed because an
earlier step in the same job failed first, so the step never ran.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "problemata_demo"
WORKFLOW = REPO / ".github" / "workflows" / "stack.yml"

# Submodules that import a third-party package at module scope, and the extra
# in pyproject.toml that provides it.
EXTRA_FOR_MODULE = {
    "problemata_control": "control-plane",
    "metagate_bootstrap": "bootstrap",
}


def _imported_submodules() -> set[str]:
    found: set[str] = set()
    for script in DEMO.glob("*.py"):
        text = script.read_text(encoding="utf-8")
        found.update(re.findall(r"from legivellum\.(\w+) import", text))
        found.update(re.findall(r"import legivellum\.(\w+)", text))
    return found


def _installed_extras() -> set[str]:
    """Extras the workflow asks for, from `pip install -e "./LegiVellum[a,b]"`."""
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(r"pip install[^\n]*\./LegiVellum\[([^\]]*)\]", text)
    return {part.strip() for part in match.group(1).split(",")} if match else set()


def test_the_workflow_installs_every_extra_the_drivers_need():
    needed = {
        EXTRA_FOR_MODULE[module]
        for module in _imported_submodules()
        if module in EXTRA_FOR_MODULE
    }
    missing = needed - _installed_extras()
    assert not missing, (
        f"demo drivers import modules requiring {sorted(missing)}, which the "
        f"Stack workflow does not install. Those scripts die on import."
    )


@pytest.mark.parametrize("module,extra", sorted(EXTRA_FOR_MODULE.items()))
def test_the_extra_map_matches_pyproject(module, extra):
    """Guards the map above from naming an extra that no longer exists."""
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(rf"^{re.escape(extra)}\s*=\s*\[", pyproject, re.M), (
        f"pyproject.toml declares no extra named {extra!r}"
    )


def test_the_base_package_stays_light():
    """The reason the extras exist at all.

    If `legivellum/__init__.py` ever imports the control plane eagerly, the
    extras become decorative and every gate installs SQLAlchemy to read a
    receipt schema.
    """
    import ast

    source = (REPO / "shared" / "legivellum" / "__init__.py").read_text(encoding="utf-8")
    # Parsed, not grepped: the module's own docstring names these packages while
    # explaining why they are absent, and a text search matches that.
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])

    heavy = {"sqlalchemy", "fastapi", "asyncpg", "pydantic_settings"} & imported
    assert not heavy, (
        f"{sorted(heavy)} reached legivellum/__init__.py; the protocol surface "
        "must stay importable without the control plane"
    )
