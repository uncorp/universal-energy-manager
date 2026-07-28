"""Regression test: remove dead `data_description` blocks from strings.json.

HA 2024.3.3 (the pinned version) does NOT support ``data_description`` in
config-flow strings.json — that feature landed in HA 2024.7+.  The
`description_placeholders` / ``{placeholder}``-token approach in the step's
``description`` text is the correct and only working mechanism for this HA
version.

Requirement 1 forbids technical terms like "signed" / "separate" anywhere
in the visible UI.  The ``data_description`` blocks currently contain the
word "signed" in the grid-export description, which would be visible in
newer HA versions and violates Req 1.

This test:
1. Verifies ``data_description`` blocks do NOT contain "signed"/"separate".
2. After the fix, verifies ``data_description`` blocks are removed entirely
   (dead code cleanup) — one block per step: confirm, manual_mapping,
   reconfigure_edit.
"""

from __future__ import annotations

import json
from pathlib import Path


def _load_strings() -> dict:
    strings_path = (
        Path(__file__).parents[1]
        / "custom_components"
        / "universal_energy_manager"
        / "strings.json"
    )
    with open(strings_path, encoding="utf-8") as f:
        return json.load(f)


def _load_full_text() -> str:
    strings_path = (
        Path(__file__).parents[1]
        / "custom_components"
        / "universal_energy_manager"
        / "strings.json"
    )
    with open(strings_path, encoding="utf-8") as f:
        return f.read()


# =========================================================================== #
# TEST 1: data_description must NOT contain forbidden technical terms         #
# =========================================================================== #


class TestDataDescriptionNoForbiddenTerms:
    """data_description blocks must not contain technical terms like
    'signed' or 'separate' anywhere — these violate Req 1."""

    def test_data_description_no_signed_in_any_step(self) -> None:
        """No data_description block may contain the word 'signed'."""
        strings = _load_strings()
        for step_name in ("confirm", "manual_mapping", "reconfigure_edit"):
            step = strings.get("config", {}).get("step", {}).get(step_name, {})
            data_desc = step.get("data_description", {})
            for key, val in data_desc.items():
                assert "signed" not in str(val).lower(), (
                    f"data_description['{key}'] in step '{step_name}' must "
                    f"not contain 'signed', got: {val}"
                )

    def test_data_description_no_separate_in_any_step(self) -> None:
        """No data_description block may contain the word 'separate'."""
        strings = _load_strings()
        for step_name in ("confirm", "manual_mapping", "reconfigure_edit"):
            step = strings.get("config", {}).get("step", {}).get(step_name, {})
            data_desc = step.get("data_description", {})
            for key, val in data_desc.items():
                assert "separate" not in str(val).lower(), (
                    f"data_description['{key}'] in step '{step_name}' must "
                    f"not contain 'separate', got: {val}"
                )


# =========================================================================== #
# TEST 2: data_description blocks removed (dead code cleanup)                 #
# =========================================================================== #


class TestDataDescriptionDeadCodeRemoved:
    """HA 2024.3.3 does not support data_description.  All
    data_description blocks in strings.json must be removed as dead code.
    Field descriptions are delivered via description_placeholders instead."""

    def test_no_data_description_in_confirm_step(self) -> None:
        """confirm step must not have a data_description key."""
        strings = _load_strings()
        confirm = strings.get("config", {}).get("step", {}).get("confirm", {})
        assert "data_description" not in confirm, (
            "confirm step must not have data_description (HA 2024.3.3 unsupported)"
        )

    def test_no_data_description_in_manual_mapping_step(self) -> None:
        """manual_mapping step must not have a data_description key."""
        strings = _load_strings()
        mapping = strings.get("config", {}).get("step", {}).get(
            "manual_mapping", {}
        )
        assert "data_description" not in mapping, (
            "manual_mapping step must not have data_description (HA 2024.3.3 "
            "unsupported)"
        )

    def test_no_data_description_in_reconfigure_edit_step(self) -> None:
        """reconfigure_edit step must not have a data_description key."""
        strings = _load_strings()
        edit = strings.get("config", {}).get("step", {}).get(
            "reconfigure_edit", {}
        )
        assert "data_description" not in edit, (
            "reconfigure_edit step must not have data_description (HA 2024.3.3 "
            "unsupported)"
        )

    def test_no_signed_in_any_string_json_text(self) -> None:
        """The entire strings.json must not contain 'signed' anywhere —
        it is a technical term forbidden by Req 1."""
        full_text = _load_full_text()
        assert "signed" not in full_text.lower(), (
            "strings.json must not contain 'signed' anywhere (forbidden "
            "technical term per Req 1)"
        )
