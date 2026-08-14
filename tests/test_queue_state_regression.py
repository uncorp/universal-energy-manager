"""
Regression tests for queue-state stale-token-blocker / queue-status correctness.

Verifies:
1. Old token-blocker narrative -> no USER_ACTION_VERIFIED alert.
2. Stale timestamps/forecasts -> not treated as live block.
3. A genuine USER_ACTION_VERIFIED: prefix -> correctly treated as alert.
4. Queue-state version 3+ schema compliance.
5. Gates 5-6 are NOT permanently "blocked" with unverifiable token references.
6. next_concrete_slice does not contain unfounded action demands.
"""

import json
import re
import unittest
from pathlib import Path

# Paths to queue-state files
QUEUE_STATE_ROOT = Path(__file__).resolve().parent.parent / "queue-state.json"
QUEUE_STATE_MC = Path(__file__).resolve().parent.parent / "mission-control" / "queue-state.json"
QUEUE_STATE_MC2 = Path(__file__).resolve().parent.parent / "mission_control" / "queue-state.json"

QUEUE_FILES = [QUEUE_STATE_ROOT, QUEUE_STATE_MC, QUEUE_STATE_MC2]


def load_queue(path: Path) -> dict:
    """Load a queue-state.json file and return parsed dict."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestQueueStateSchema(unittest.TestCase):
    """Verify queue-state schema compliance (version 3+)."""

    def test_version_is_3(self):
        """Queue-state version must be 3 or higher."""
        for qf in QUEUE_FILES:
            qs = load_queue(qf)
            self.assertGreaterEqual(
                qs.get("version", 0),
                3,
                f"{qf}: version must be >= 3, got {qs.get('version')}",
            )

    def test_no_token_blocker_in_uem_state(self):
        """uem_state must NOT contain 'token_truncated' or similar stale narratives."""
        for qf in QUEUE_FILES:
            qs = load_queue(qf)
            state: str = qs.get("uem_state", "") or ""
            self.assertNotIn(
                "token_truncated",
                state.lower(),
                f"{qf}: uem_state must not contain stale token narrative, got: {state}",
            )
            self.assertNotIn(
                "401",
                state,
                f"{qf}: uem_state must not contain HTTP status code, got: {state}",
            )

    def test_gate_5_6_not_blocked_with_token(self):
        """Gates 5-6 must NOT be 'blocked' with unverifiable token references."""
        for qf in QUEUE_FILES:
            qs = load_queue(qf)
            gates = qs.get("plan", {}).get("gates", [])
            gate_map = {g["id"]: g for g in gates}
            for gid in [5, 6]:
                gate = gate_map.get(gid)
                self.assertIsNotNone(gate, f"{qf}: gate {gid} missing")
                reason = gate.get("block_reason", "")
                # If blocked, reason must not reference token truncation
                if gate["status"] == "blocked":
                    self.assertNotIn(
                        "truncated",
                        reason.lower(),
                        f"{qf}: gate {gid} blocked with stale token reference",
                    )
                    self.assertNotIn(
                        "401",
                        reason,
                        f"{qf}: gate {gid} blocked with stale 401 reference",
                    )


class TestStaleTokenBlockerRemoved(unittest.TestCase):
    """Verify the stale token-blocker narrative is removed from all status fields."""

    def test_no_token_narrative_in_block_reasons(self):
        """No gate block_reason should contain truncated-token narrative."""
        for qf in QUEUE_FILES:
            qs = load_queue(qf)
            gates = qs.get("plan", {}).get("gates", [])
            for gate in gates:
                reason = gate.get("block_reason", "")
                self.assertNotIn(
                    "truncated",
                    reason.lower(),
                    f"{qf}: gate {gate['id']} block_reason contains 'truncated': {reason}",
                )
                self.assertNotIn(
                    "eyJhbG",
                    reason,
                    f"{qf}: gate {gate['id']} block_reason contains token prefix",
                )

    def test_no_token_narrative_in_evidence(self):
        """No gate evidence should reference truncated token with fake 401."""
        for qf in QUEUE_FILES:
            qs = load_queue(qf)
            evidence = qs.get("plan", {}).get("evidence", {})
            for gate_id, ev in evidence.items():
                self.assertNotIn(
                    "eyJhbG",
                    ev,
                    f"{qf}: evidence {gate_id} contains token prefix",
                )

    def test_no_token_narrative_in_verification_notes(self):
        """verification_notes must not contain truncated token narrative."""
        for qf in QUEUE_FILES:
            qs = load_queue(qf)
            notes = qs.get("verification_notes", {})
            for note_key, note_val in notes.items():
                self.assertNotIn(
                    "eyJhbG",
                    note_val,
                    f"{qf}: verification_notes.{note_key} contains token prefix",
                )
                self.assertNotIn(
                    "truncated",
                    note_val.lower(),
                    f"{qf}: verification_notes.{note_key} contains 'truncated'",
                )


class TestStaleForecastsRemoved(unittest.TestCase):
    """Verify stale forecast ETAs and 'waiting_external' without fake claims."""

    def test_forecast_no_fake_etas(self):
        """Forecast earliest_check_at and recommended_check_at should be None (no fake ETAs)."""
        for qf in QUEUE_FILES:
            qs = load_queue(qf)
            forecast = qs.get("plan", {}).get("check_again_forecast", {})
            self.assertIsNone(
                forecast.get("earliest_check_at"),
                f"{qf}: forecast should have no earliest_check_at",
            )
            self.assertIsNone(
                forecast.get("recommended_check_at"),
                f"{qf}: forecast should have no recommended_check_at",
            )

    def test_forecast_no_stefan_token_action(self):
        """Forecast caveat must NOT demand Stefan to replace a token."""
        for qf in QUEUE_FILES:
            qs = load_queue(qf)
            forecast = qs.get("plan", {}).get("check_again_forecast", {})
            caveat = forecast.get("caveat", "")
            self.assertNotIn(
                "ersetzt",
                caveat.lower(),
                f"{qf}: forecast caveat must not demand token replacement: {caveat}",
            )
            self.assertNotIn(
                "Stefan ersetzt",
                caveat,
                f"{qf}: forecast must not reference Stefan token replacement",
            )


class TestNextConcreteSlice(unittest.TestCase):
    """Verify next_concrete_slice does not contain unfounded action demands."""

    def test_next_concrete_slice_no_token_demand(self):
        """next_concrete_slice must not contain token replacement demands."""
        for qf in QUEUE_FILES:
            qs = load_queue(qf)
            ncs = qs.get("next_concrete_slice", "")
            self.assertNotIn(
                "ersetzt",
                ncs.lower(),
                f"{qf}: next_concrete_slice must not demand token replacement",
            )
            self.assertNotIn(
                "Stefan ersetzt",
                ncs,
                f"{qf}: next_concrete_slice must not reference Stefan token replacement",
            )
            self.assertNotIn(
                "eyJhbG",
                ncs,
                f"{qf}: next_concrete_slice must not contain token prefix",
            )


class TestUserActionVerifiedSemantics(unittest.TestCase):
    """Test that USER_ACTION_VERIFIED: prefix semantics are enforced."""

    def _extract_alerts(self, qs: dict) -> list[str]:
        """
        Extract all strings that would trigger a USER_ACTION_VERIFIED alert
        from the queue-state (mimicking the notifier logic).
        """
        alerts = []

        def scan(obj, path=""):
            if isinstance(obj, str):
                if re.search(r"^USER_ACTION_VERIFIED:", obj, re.MULTILINE):
                    alerts.append(f"{path}: {obj[:80]}...")
                if re.search(r"^COMPLETION_VERIFIED:", obj, re.MULTILINE):
                    alerts.append(f"{path}: {obj[:80]}...")
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    scan(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    scan(item, f"{path}[{i}]")

        scan(qs)
        return alerts

    def test_current_queue_has_no_user_action_alert(self):
        """Current queue-state must NOT produce any USER_ACTION_VERIFIED alert."""
        for qf in QUEUE_FILES:
            qs = load_queue(qf)
            alerts = self._extract_alerts(qs)
            user_alerts = [a for a in alerts if "USER_ACTION_VERIFIED:" in a]
            self.assertEqual(
                len(user_alerts),
                0,
                f"{qf}: unexpected USER_ACTION_VERIFIED alerts: {user_alerts}",
            )

    def test_stale_forecasts_do_not_produce_alert(self):
        """Stale forecast data must NOT produce USER_ACTION_VERIFIED alerts."""
        stale_qs = {
            "plan": {
                "check_again_forecast": {
                    "caveat": "Gate 5 blocked auf HA-Token. Stefan ersetzt HASS_TOKEN.",
                }
            },
            "next_concrete_slice": "Stefan ersetzt HASS_TOKEN in .env.",
            "verification_notes": {"runtime": "HASS_TOKEN truncated, 401 on /api/config"},
        }
        alerts = self._extract_alerts(stale_qs)
        user_alerts = [a for a in alerts if "USER_ACTION_VERIFIED:" in a]
        self.assertEqual(
            len(user_alerts),
            0,
            f"Stale data should not produce alerts: {user_alerts}",
        )

    def test_genuine_user_action_verifies_produces_alert(self):
        """A genuine USER_ACTION_VERIFIED: prefix SHOULD produce an alert."""
        genuine_qs = {
            "plan": {
                "gates": [
                    {
                        "id": 1,
                        "status": "blocked",
                        "block_reason": "USER_ACTION_VERIFIED: Stefan must provide a new long-lived access token for the test HA instance before Gate 1 can proceed. Contact: admin@example.com.",  # noqa: E501
                    }
                ]
            }
        }
        alerts = self._extract_alerts(genuine_qs)
        user_alerts = [a for a in alerts if "USER_ACTION_VERIFIED:" in a]
        self.assertEqual(
            len(user_alerts),
            1,
            f"Genuine USER_ACTION_VERIFIED: should produce exactly 1 alert, got: {user_alerts}",
        )

    def test_completion_verified_produces_alert(self):
        """A genuine COMPLETION_VERIFIED: prefix SHOULD produce an alert."""
        completion_qs = {
            "completed": [
                "COMPLETION_VERIFIED: Gate 5 completed — HACS entity updated to v0.1.10-rc.2",
            ]
        }
        alerts = self._extract_alerts(completion_qs)
        completion_alerts = [a for a in alerts if "COMPLETION_VERIFIED:" in a]
        self.assertEqual(
            len(completion_alerts),
            1,
            f"Genuine COMPLETION_VERIFIED: should produce exactly 1 alert, got: {completion_alerts}",  # noqa: E501
        )


class TestNoTokenNarrativeInCompleted(unittest.TestCase):
    """Verify the completed array does not contain token-blocker repetition loops."""

    def test_no_stale_token_repetition_in_completed(self):
        """
        The completed array should NOT contain more than 2 entries referencing
        token truncation (historical context is OK, but not the stale loop).
        """
        for qf in QUEUE_FILES:
            qs = load_queue(qf)
            completed = qs.get("completed", [])
            token_entries = [
                c for c in completed if "truncated" in c.lower() or "401" in c
            ]
            # After repair, there should be 0 or very few historical entries
            self.assertLessEqual(
                len(token_entries),
                2,
                f"{qf}: completed has {len(token_entries)} stale token entries: "
                + str(token_entries),
            )

    def test_no_future_timestamp_in_completed(self):
        """
        Completed entries must not contain timestamps from the future
        relative to the last_verified timestamp (detects stale loop artifacts).
        """
        for qf in QUEUE_FILES:
            qs = load_queue(qf)
            last_verified = qs.get("last_verified", "")
            completed = qs.get("completed", [])
            for entry in completed:
                # Extract any ISO timestamp from the entry
                ts_match = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", entry)
                if ts_match and last_verified:
                    entry_ts = ts_match.group(1)
                    self.assertLessEqual(
                        entry_ts,
                        last_verified,
                        f"{qf}: completed entry has future timestamp {entry_ts} "
                        f"> last_verified {last_verified}",
                    )


class TestFileSync(unittest.TestCase):
    """Verify all 3 queue-state files are identical."""

    def test_all_files_identical(self):
        """All queue-state copies must have identical content."""
        contents = []
        for qf in QUEUE_FILES:
            with open(qf, encoding="utf-8") as f:
                contents.append(f.read())
        for i in range(1, len(contents)):
            self.assertEqual(
                contents[0],
                contents[i],
                f"queue-state files differ: {QUEUE_FILES[0]} vs {QUEUE_FILES[i]}",
            )


if __name__ == "__main__":
    unittest.main()
