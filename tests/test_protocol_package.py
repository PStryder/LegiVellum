"""The protocol package must be importable, light, and fail closed.

These pin Phase 0. Each asserts an invariant rather than exercising a path, and
each fails if the corresponding guard is removed:

- Remove the lazy `__getattr__` split and re-import the control plane eagerly
  in `__init__.py`, and the "light import" tests fail.
- Restore `except ImportError: JSONSCHEMA_AVAILABLE = False`, or make
  `schema_path()` return instead of raise, and the fail-closed tests fail.
- Re-add a third-party `ulid` dependency and the ULID tests still pass, but the
  import-weight test fails, which is the point: the dependency is what was
  hazardous, not the algorithm.

The defect being prevented is specific and was live across the stack: importing
`legivellum.models` pulled SQLAlchemy and FastAPI through `__init__.py`, gates
did not install them, the resulting ImportError was swallowed by every emitter,
and receipts were posted unvalidated while the system reported success.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SCHEMA = REPO_ROOT / "docs" / "canonical" / "receipt.schema.v1.json"
PACKAGED_SCHEMA = REPO_ROOT / "shared" / "legivellum" / "schemas" / "receipt.schema.v1.json"

# Modules the protocol surface must never drag in. If importing the receipt
# model requires an application server or a database driver, gates will not
# install it, and history says they will then disable validation instead.
FORBIDDEN_ON_PROTOCOL_IMPORT = ("sqlalchemy", "fastapi", "asyncpg", "httpx", "ulid")


def _run_in_subprocess(code: str) -> subprocess.CompletedProcess[str]:
    """Run code in a fresh interpreter.

    Import weight cannot be measured in-process: pytest has already imported
    half the world, so `sys.modules` here proves nothing.
    """
    return subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120
    )


class TestProtocolImportIsLight:
    def test_importing_legivellum_does_not_load_the_control_plane(self):
        result = _run_in_subprocess(
            "import sys, legivellum;"
            f"loaded = sorted(m for m in {FORBIDDEN_ON_PROTOCOL_IMPORT!r} if m in sys.modules);"
            "print(loaded)"
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "[]", (
            f"importing legivellum loaded {result.stdout.strip()}; the protocol "
            f"surface must not require the control-plane dependency tree"
        )

    def test_models_and_validation_are_independently_importable(self):
        result = _run_in_subprocess(
            "from legivellum.models import Receipt;"
            "from legivellum.validation import validate_receipt, validate_json_schema;"
            "print('ok')"
        )
        assert result.returncode == 0, result.stderr
        assert "ok" in result.stdout

    def test_control_plane_names_still_resolve(self):
        """Laziness must not silently drop the existing public surface."""
        import legivellum

        assert "PostgresProblemataRepository" in legivellum.__all__
        assert "bootstrap_from_metagate" in legivellum.__all__
        assert "Receipt" in legivellum.__all__

    def test_unknown_attribute_still_raises_attribute_error(self):
        import legivellum

        with pytest.raises(AttributeError):
            legivellum.definitely_not_a_real_name


class TestSchemaResolutionFailsClosed:
    def test_packaged_schema_is_byte_identical_to_canonical(self):
        """Two copies exist so the wheel can validate without a checkout.

        They must not drift: a packaged schema that has fallen behind canonical
        validates the wrong contract everywhere it is installed.
        """
        assert PACKAGED_SCHEMA.exists(), f"{PACKAGED_SCHEMA} missing from the package"
        assert (
            PACKAGED_SCHEMA.read_bytes() == CANONICAL_SCHEMA.read_bytes()
        ), "packaged schema has drifted from docs/canonical/receipt.schema.v1.json"

    def test_missing_schema_raises_rather_than_passing_everything(self, monkeypatch):
        """The whole Phase 0 thesis in one assertion.

        The prior implementation returned [] when it could not find the schema,
        so every receipt validated successfully in every deployment.
        """
        from legivellum import validation

        monkeypatch.setenv(validation.SCHEMA_DIR_ENV, "/nonexistent/schema/dir")
        with pytest.raises(RuntimeError, match="does not exist"):
            validation.schema_path()

    def test_schema_dir_override_is_honoured(self, tmp_path, monkeypatch):
        from legivellum import validation

        (tmp_path / validation.SCHEMA_FILENAME).write_bytes(CANONICAL_SCHEMA.read_bytes())
        monkeypatch.setenv(validation.SCHEMA_DIR_ENV, str(tmp_path))
        assert validation.schema_path() == tmp_path / validation.SCHEMA_FILENAME

    def test_jsonschema_is_a_hard_import(self):
        """No `except ImportError` may re-appear around the validator.

        Checks for an *assignment* rather than the bare name, so the comment
        explaining why the flag was removed does not trip its own test.
        """
        source = (REPO_ROOT / "shared" / "legivellum" / "validation.py").read_text(
            encoding="utf-8"
        )
        assert not re.search(r"^\s*JSONSCHEMA_AVAILABLE\s*=", source, re.M), (
            "the availability flag is back; a broken install would again mean "
            "'validation disabled' rather than 'startup fails'"
        )


class TestCanonicalValidationActuallyRuns:
    """Phase 0 exit condition, run in-process here and in-container in CI."""

    def test_known_good_receipt_validates(self, canonical_good_receipt):
        from legivellum.validation import validate_json_schema

        assert validate_json_schema(canonical_good_receipt) == []

    def test_known_bad_receipt_is_rejected(self, canonical_good_receipt):
        from legivellum.validation import validate_json_schema

        bad = dict(canonical_good_receipt)
        # An accepted receipt must carry outcome_kind "NA"; the schema's
        # phase-conditional block forbids a real outcome on an open obligation.
        bad["outcome_kind"] = "response_text"
        errors = validate_json_schema(bad)
        assert errors, "schema accepted a receipt the canonical rules forbid"

    def test_additional_properties_are_rejected(self, canonical_good_receipt):
        from legivellum.validation import validate_json_schema

        bad = dict(canonical_good_receipt)
        bad["receipt_type"] = "task.assigned"
        assert validate_json_schema(bad), "additionalProperties: false is not holding"


class TestUlid:
    def test_shape(self):
        from legivellum.ulid import is_ulid, new_ulid

        value = new_ulid()
        assert len(value) == 26
        assert is_ulid(value)

    def test_lexicographic_order_matches_time_order(self):
        """Receipt ids sort by creation time; the ledger relies on it."""
        from legivellum.ulid import new_ulid

        earlier = new_ulid(timestamp_ms=1_600_000_000_000)
        later = new_ulid(timestamp_ms=1_600_000_001_000)
        assert earlier < later

    def test_ids_minted_in_the_same_millisecond_differ(self):
        from legivellum.ulid import new_ulid

        stamp = 1_600_000_000_000
        values = {new_ulid(timestamp_ms=stamp) for _ in range(1000)}
        assert len(values) == 1000

    def test_timestamp_round_trips(self):
        from legivellum.ulid import new_ulid, timestamp_ms_of

        stamp = 1_600_000_000_123
        assert timestamp_ms_of(new_ulid(timestamp_ms=stamp)) == stamp

    def test_rejects_out_of_range_timestamp(self):
        from legivellum.ulid import new_ulid

        with pytest.raises(ValueError):
            new_ulid(timestamp_ms=1 << 48)

    def test_generate_receipt_id_produces_a_ulid(self):
        from legivellum.models import generate_receipt_id
        from legivellum.ulid import is_ulid

        assert is_ulid(generate_receipt_id())


class TestShippedExamplesConform:
    """Every shipped example must validate; every negative example must fail.

    The negative fixtures existed since the schema was written and were run by
    nothing — `tools/validate_all_examples.py` globs `examples/receipts/*.json`
    non-recursively, so `examples/receipts/invalid/` was never opened. A change
    that loosened the schema would have passed CI green.
    """

    def test_valid_example_validates(self, canonical_valid_example):
        from legivellum.validation import validate_json_schema

        errors = validate_json_schema(canonical_valid_example)
        assert errors == [], f"shipped valid example rejected: {[e.message for e in errors]}"

    def test_invalid_example_is_rejected(self, canonical_invalid_example):
        """Rejected by the full validator, not the schema alone.

        The routing invariant (`recipient_ai == escalation_to`) is deliberately
        not expressible in JSON Schema -- the canonical schema says so and
        requires application-level enforcement. Asserting against
        `validate_json_schema` alone would therefore fail on a fixture that is
        correctly caught one layer up. The contract the stack depends on is
        that *something* refuses it.
        """
        from legivellum.validation import validate_receipt

        assert validate_receipt(
            canonical_invalid_example
        ), "shipped negative example was accepted by the full validator"
