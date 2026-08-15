"""The type gate must stay able to fail.

Seven byte-identical `.mypy-ci.ini` files used to sit beside seven
`pyproject.toml` files declaring `strict = true`. Every CI job passed
`--config-file .mypy-ci.ini`, which set `follow_imports = skip`,
`check_untyped_defs = false`, and disabled fifteen error codes. Declared
strictness was fiction, and mypy could not fail.

The two codes that mattered most were in that disable list:

  call-arg      catches `logger.info(msg, receipt_id=...)` on a stdlib logger.
                In ReceiptGate that line ran *after* `db.commit()` and outside
                the try/except, so at INFO level every first write committed
                durably and then returned "Failed to store receipt". In
                AsyncGate the same shape sat in the ReceiptGate emit-failure
                handler, where the TypeError rolled back the savepoint around
                the task completion it was only meant to warn about.

  attr-defined  catches `self.tasks.count_by_status` on a repository with no
                such method, and `Server.list_tools` against an `mcp` package
                that has no such attribute.

Both were live. Both are fixed. This test exists so the codes that found them
cannot be switched off again without a test failing, which is the guarantee the
deleted config files removed.

Codes *may* be disabled -- annotation debt is real and listing it explicitly is
better than a blanket `strict = false`. But not these.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

STACK_ROOT = Path(__file__).resolve().parents[2]

# Repositories inside the Slice Zero scope fence.
IN_SCOPE = ("LegiVellum", "ReceiptGate", "AsyncGate")

# Error codes that must remain enabled, with the defect each one caught.
REQUIRED_CODES = {
    "call-arg": "structlog kwargs on a stdlib logger, raising after commit",
    "attr-defined": "calling a method that does not exist on the object",
}


def _pyproject(repo: str) -> dict:
    path = STACK_ROOT / repo / "pyproject.toml"
    if not path.exists():
        pytest.skip(f"{path} not present")
    return tomllib.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("repo", IN_SCOPE)
def test_no_mypy_ci_override_file(repo: str):
    """The override file must not come back.

    Its existence is the mechanism by which the declared config and the
    enforced config drifted apart.
    """
    override = STACK_ROOT / repo / ".mypy-ci.ini"
    assert not override.exists(), (
        f"{override} is back. CI would run it instead of the declared "
        f"[tool.mypy] config, and the two would drift apart again."
    )


@pytest.mark.parametrize("repo", IN_SCOPE)
def test_mypy_config_is_declared(repo: str):
    config = _pyproject(repo).get("tool", {}).get("mypy")
    assert config is not None, (
        f"{repo} declares no [tool.mypy]; CI would have nothing to enforce"
    )


@pytest.mark.parametrize("repo", IN_SCOPE)
@pytest.mark.parametrize("code", sorted(REQUIRED_CODES))
def test_live_bug_error_codes_remain_enabled(repo: str, code: str):
    config = _pyproject(repo).get("tool", {}).get("mypy", {})
    disabled = config.get("disable_error_code", [])
    if isinstance(disabled, str):
        disabled = [disabled]
    assert code not in disabled, (
        f"{repo} disables '{code}'. That code caught a live defect in this "
        f"codebase: {REQUIRED_CODES[code]}. Fix the finding rather than "
        f"disabling the check."
    )


@pytest.mark.parametrize("repo", IN_SCOPE)
def test_typecheck_is_not_weakened_by_follow_imports_skip(repo: str):
    """`follow_imports = skip` makes mypy unable to see imported types.

    With it set, mypy cannot check call signatures across modules, which
    silently defeats `call-arg` even while the code appears enabled.
    """
    config = _pyproject(repo).get("tool", {}).get("mypy", {})
    assert config.get("follow_imports", "normal") != "skip", (
        f"{repo} sets follow_imports = skip, which defeats cross-module "
        f"signature checking and therefore defeats call-arg in practice"
    )
