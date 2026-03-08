"""
Wave 4 Python Bot Behavior Stub Tests

Tests for:
- W4-01: RL training simulate_bot_strategy
- W4-02: RL training collect_metrics_snapshot
- W4-03: Simulation bot run_simulation
- W4-04: Coding bot refactor_code
- W4-05: Memory manager bot ttl_check archive
- W4-06: Hive pipelines predictive_scheduler
- W4-07: UI data service get_phase_fsm

Run: pytest tests/test_bot_behavior_stubs.py -v
"""
from __future__ import annotations

import json
import math
import os
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch


# ─────────────────────────────────────────────────────────────────────────────
# W4-01 & W4-02: RL Training
# ─────────────────────────────────────────────────────────────────────────────
class TestSimulateBotStrategy(unittest.TestCase):
    """W4-01: simulate_bot_strategy() — deterministic mock & valid metrics."""

    def setUp(self) -> None:
        from bots.rl_training import simulate_bot_strategy
        self.simulate = simulate_bot_strategy

    def test_simulate_deterministic_mock(self) -> None:
        """Same action + _test_mode=True always returns the same reward."""
        action = [1, 2]
        result1 = self.simulate(action, _test_mode=True)
        result2 = self.simulate(action, _test_mode=True)
        self.assertEqual(result1["reward"], result2["reward"],
                         "Mock mode must be deterministic for the same input.")
        self.assertEqual(result1["source"], "mock")

    def test_simulate_returns_valid_metrics(self) -> None:
        """Returned metrics are within valid ranges."""
        result = self.simulate([1, 2], _test_mode=True)
        self.assertIn("reward", result)
        self.assertIn("latency_ms", result)
        self.assertIn("success_rate", result)
        self.assertIn("steps", result)
        self.assertIn("source", result)
        self.assertGreaterEqual(result["reward"], -1.0)
        self.assertLessEqual(result["reward"], 1.0)
        self.assertGreater(result["latency_ms"], 0)
        self.assertGreaterEqual(result["success_rate"], 0.0)
        self.assertLessEqual(result["success_rate"], 1.0)
        self.assertIsInstance(result["steps"], int)
        self.assertGreater(result["steps"], 0)

    def test_simulate_production_mode_valid_ranges(self) -> None:
        """Production mode (no randomness) also returns metrics in valid ranges."""
        result = self.simulate([0.5, 0.5], _test_mode=False)
        self.assertGreaterEqual(result["reward"], -1.0)
        self.assertLessEqual(result["reward"], 1.0)
        self.assertGreater(result["latency_ms"], 0)
        self.assertGreaterEqual(result["success_rate"], 0.0)
        self.assertLessEqual(result["success_rate"], 1.0)
        self.assertEqual(result["source"], "sandbox")

    def test_simulate_different_actions_different_results(self) -> None:
        """Different actions produce different mock results."""
        r1 = self.simulate([0, 0], _test_mode=True)
        r2 = self.simulate([1, 2], _test_mode=True)
        # It's unlikely (though technically possible) that both hashes collide.
        # We just check at least one field differs.
        some_differ = any(r1[k] != r2[k] for k in ("reward", "latency_ms", "steps"))
        self.assertTrue(some_differ, "Different actions should produce different metrics.")


class TestCollectMetricsSnapshot(unittest.TestCase):
    """W4-02: collect_metrics_snapshot() — shape, stability, finite values."""

    def setUp(self) -> None:
        from bots.rl_training import collect_metrics_snapshot
        self.snapshot = collect_metrics_snapshot

    def test_metrics_snapshot_shape(self) -> None:
        """Vector shape must be (10,)."""
        arr = self.snapshot()
        self.assertEqual(arr.shape, (10,))

    def test_metrics_snapshot_not_random(self) -> None:
        """Two successive calls within 1 s return similar values (not random)."""
        arr1 = self.snapshot()
        time.sleep(0.05)
        arr2 = self.snapshot()
        import numpy as np
        # Allow up to 0.5 mean-absolute-difference (system metrics change slowly)
        diff = float(np.abs(arr1 - arr2).mean())
        self.assertLess(diff, 0.5,
                        f"Snapshots diverged too much between calls: mean diff={diff:.4f}")

    def test_metrics_snapshot_values_valid(self) -> None:
        """All values must be finite and non-negative."""
        import numpy as np
        arr = self.snapshot()
        self.assertTrue(np.all(np.isfinite(arr)), "All metrics must be finite.")
        self.assertTrue(np.all(arr >= 0.0), "All metrics must be non-negative.")

    def test_metrics_snapshot_values_normalised(self) -> None:
        """All values must be in [0, 1] since they are normalised."""
        import numpy as np
        arr = self.snapshot()
        self.assertTrue(np.all(arr <= 1.0), "Normalised metrics must be ≤ 1.0.")


# ─────────────────────────────────────────────────────────────────────────────
# W4-03: Simulation Bot
# ─────────────────────────────────────────────────────────────────────────────
class TestRunSimulation(unittest.TestCase):
    """W4-03: run_simulation() — spring-mass solver, unsupported fallback."""

    def _make_task(self, sim_type: str, params: dict | None = None) -> dict:
        return {
            "task_id": f"test_{sim_type}",
            "simulation_type": sim_type,
            "input_parameters": params or {},
        }

    def setUp(self) -> None:
        from bots.simulation_bot import _spring_mass_damper, SimulationBot
        self._solver = _spring_mass_damper
        # Build a minimal SimulationBot that doesn't require the GPT runner
        with patch("bots.simulation_bot.GPTOSSRunner"):
            self.bot = SimulationBot()

    def test_spring_mass_known_solution(self) -> None:
        """Undamped spring-mass with x0=1, v0=0 → displacement stays bounded."""
        result = self._solver(k=10.0, m=1.0, c=0.0, x0=1.0, v0=0.0, t_end=5.0, dt=0.01)
        displ = result["displacement"]
        # The displacement of an undamped oscillator should always be in [-1, 1]
        self.assertTrue(all(-1.05 <= d <= 1.05 for d in displ),
                        "Displacement should oscillate within initial amplitude.")
        # Equilibrium: time-average of |displacement| should be less than x0
        mean_abs = sum(abs(d) for d in displ) / len(displ)
        self.assertLess(mean_abs, 1.0)

    def test_spring_mass_damped_converges(self) -> None:
        """Heavily damped spring-mass should converge toward 0."""
        result = self._solver(k=5.0, m=1.0, c=10.0, x0=1.0, v0=0.0, t_end=10.0, dt=0.05)
        displ = result["displacement"]
        # Final displacement should be much smaller than initial
        self.assertLess(abs(displ[-1]), 0.5)

    def test_simulation_unsupported_type(self) -> None:
        """Unknown simulation type → structured fallback with confidence=0."""
        with patch("bots.simulation_bot.get_cache", return_value=None), \
             patch("bots.simulation_bot.set_cache"):
            result = self.bot.run_simulation(self._make_task("quantum_foam_nonsense"))
        inner = result["results"]
        self.assertEqual(inner["confidence"], 0)
        self.assertIn("note", inner)
        self.assertIn("unsupported simulation type", inner["note"].lower())

    def test_simulation_result_structure(self) -> None:
        """Spring-mass simulation returns all expected fields."""
        with patch("bots.simulation_bot.get_cache", return_value=None), \
             patch("bots.simulation_bot.set_cache"):
            result = self.bot.run_simulation(
                self._make_task("spring_mass_damper", {"k": 5.0, "m": 1.0, "c": 0.5})
            )
        inner = result["results"]
        for field in ("displacement", "stress", "time_steps", "solver", "confidence"):
            self.assertIn(field, inner, f"Missing field: {field}")
        self.assertIsInstance(inner["displacement"], list)
        self.assertIsInstance(inner["stress"], list)
        self.assertIsInstance(inner["time_steps"], list)
        self.assertGreater(inner["confidence"], 0)


# ─────────────────────────────────────────────────────────────────────────────
# W4-04: Coding Bot
# ─────────────────────────────────────────────────────────────────────────────
class TestRefactorCode(unittest.TestCase):
    """W4-04: refactor_code() — AST-level refactoring."""

    def setUp(self) -> None:
        from bots.coding_bot import CodingBot
        self.bot = CodingBot()

    def test_remove_unused_import(self) -> None:
        """Unused import should be removed; change recorded."""
        code = "import os\n\ndef hello():\n    return 1\n"
        result = self.bot.refactor_code(code)
        self.assertIsInstance(result, dict)
        self.assertNotIn("import os", result["code"])
        self.assertTrue(
            any("removed unused import: os" in ch for ch in result["changes"]),
            f"Expected removal note. Got: {result['changes']}",
        )

    def test_camelcase_to_snake(self) -> None:
        """camelCase variable names should be converted to snake_case."""
        code = "myVariable = 1\nresult = myVariable + 2\n"
        result = self.bot.refactor_code(code)
        self.assertIn("my_variable", result["code"])
        self.assertTrue(
            any("my_variable" in ch for ch in result["changes"]),
            f"Expected rename note. Got: {result['changes']}",
        )

    def test_syntax_error_returns_unchanged(self) -> None:
        """Invalid Python code → input returned unchanged, confidence=0."""
        bad_code = "def broken(:\n    pass\n"
        result = self.bot.refactor_code(bad_code)
        self.assertEqual(result["code"], bad_code)
        self.assertEqual(result["confidence"], 0.0)

    def test_no_changes_needed(self) -> None:
        """Clean code with no refactoring opportunities → empty changes list."""
        code = "x = 1\ny = x + 2\n"
        result = self.bot.refactor_code(code)
        self.assertEqual(result["changes"], [])
        self.assertGreater(result["confidence"], 0.0)

    def test_result_structure(self) -> None:
        """refactor_code always returns dict with code, changes, confidence."""
        result = self.bot.refactor_code("x = 1\n")
        self.assertIn("code", result)
        self.assertIn("changes", result)
        self.assertIn("confidence", result)
        self.assertIsInstance(result["changes"], list)
        self.assertIsInstance(result["confidence"], float)


# ─────────────────────────────────────────────────────────────────────────────
# W4-05: Memory Manager Bot ttl_check
# ─────────────────────────────────────────────────────────────────────────────
class _StubSentenceTransformer:
    """Minimal stub to avoid loading the real model."""

    def get_sentence_embedding_dimension(self) -> int:
        return 4

    def encode(self, text: str):
        import numpy as np
        return np.ones(4, dtype="float32")


class TestTTLCheck(unittest.TestCase):
    """W4-05: ttl_check() — archival of expired entries."""

    def _make_bot(self, db_path: str):
        import bots.memory_manager_bot as mmb_module
        _orig = mmb_module.SentenceTransformer
        mmb_module.SentenceTransformer = _StubSentenceTransformer  # type: ignore
        _orig_db = mmb_module.DB_PATH
        mmb_module.DB_PATH = db_path
        try:
            from bots.memory_manager_bot import MemoryManagerBot
            bot = MemoryManagerBot.__new__(MemoryManagerBot)
            bot.model = _StubSentenceTransformer()
            bot.dim = 4
            bot.index = None
            bot.id_to_text = {}
            bot.enc_key = None
            bot.context_window = 50
            bot.archived_memories = {}
            bot._ensure_db()
            return bot
        finally:
            mmb_module.SentenceTransformer = _orig  # type: ignore
            mmb_module.DB_PATH = _orig_db

    def test_ttl_expired_entry_archived(self) -> None:
        """Entry with TTL=0 and old last_accessed → ends up in archived_memories."""
        import sqlite3
        from bots import memory_manager_bot as mmb_module

        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test.db")
            bot = self._make_bot(db)
            mmb_module.DB_PATH = db

            # Insert a memory with TTL=1 and last_accessed far in the past
            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT INTO memories (text, embedding, trust, last_accessed, access_count, ttl_seconds, compressed, is_deleted, tenant) "
                "VALUES (?, ?, 1.0, ?, 0, 1, 0, 0, 'default')",
                ("old entry", b"\x00" * 16, time.time() - 10000),
            )
            conn.commit()
            mem_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.close()

            result = bot.ttl_check(threshold=1.1)  # threshold above any realistic decay

            self.assertIn(mem_id, bot.archived_memories,
                          "Expired entry should be in archived_memories.")
            # Check it's marked deleted in DB
            conn = sqlite3.connect(db)
            row = conn.execute("SELECT is_deleted FROM memories WHERE id = ?", (mem_id,)).fetchone()
            conn.close()
            self.assertEqual(row[0], 1, "Entry should be marked deleted in DB.")

    def test_ttl_valid_entry_kept(self) -> None:
        """Entry with high retention score → stays in active store."""
        import sqlite3
        from bots import memory_manager_bot as mmb_module

        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test2.db")
            bot = self._make_bot(db)
            mmb_module.DB_PATH = db

            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT INTO memories (text, embedding, trust, last_accessed, access_count, ttl_seconds, compressed, is_deleted, tenant) "
                "VALUES (?, ?, 1.0, ?, 1000, 3600, 0, 0, 'default')",
                ("fresh entry", b"\x00" * 16, time.time()),
            )
            conn.commit()
            mem_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.close()

            bot.ttl_check(threshold=0.0)  # threshold so low nothing should be archived

            self.assertNotIn(mem_id, bot.archived_memories,
                             "Fresh entry should NOT be archived.")

    def test_archive_compressed(self) -> None:
        """Archived entry blob is smaller than original text (zlib compression)."""
        import sqlite3
        from bots import memory_manager_bot as mmb_module

        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test3.db")
            bot = self._make_bot(db)
            mmb_module.DB_PATH = db

            long_text = "Lorem ipsum dolor sit amet. " * 100
            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT INTO memories (text, embedding, trust, last_accessed, access_count, ttl_seconds, compressed, is_deleted, tenant) "
                "VALUES (?, ?, 1.0, ?, 0, 1, 0, 0, 'default')",
                (long_text, b"\x00" * 16, time.time() - 10000),
            )
            conn.commit()
            mem_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.close()

            bot.ttl_check(threshold=1.1)

            self.assertIn(mem_id, bot.archived_memories)
            compressed = bot.archived_memories[mem_id]
            self.assertLess(len(compressed), len(long_text.encode("utf-8")),
                            "Compressed blob should be smaller than original.")

    def test_archived_not_searchable(self) -> None:
        """After archival, id_to_text no longer contains the entry."""
        import sqlite3
        from bots import memory_manager_bot as mmb_module

        with tempfile.TemporaryDirectory() as tmpdir:
            db = os.path.join(tmpdir, "test4.db")
            bot = self._make_bot(db)
            mmb_module.DB_PATH = db

            conn = sqlite3.connect(db)
            conn.execute(
                "INSERT INTO memories (text, embedding, trust, last_accessed, access_count, ttl_seconds, compressed, is_deleted, tenant) "
                "VALUES (?, ?, 1.0, ?, 0, 1, 0, 0, 'default')",
                ("archived text", b"\x00" * 16, time.time() - 10000),
            )
            conn.commit()
            mem_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.close()

            bot.id_to_text[mem_id] = "archived text"
            bot.ttl_check(threshold=1.1)

            self.assertNotIn(mem_id, bot.id_to_text,
                             "Archived entry should be removed from id_to_text.")


# ─────────────────────────────────────────────────────────────────────────────
# W4-06: Hive Pipelines predictive_scheduler
# ─────────────────────────────────────────────────────────────────────────────
class TestPredictiveScheduler(unittest.TestCase):
    """W4-06: predictive_scheduler() — EWMA from real history."""

    def _make_mocks(self):
        sched = MagicMock()
        sched.predict_ETC.return_value = (1.0, 0.0)
        mem = MagicMock()
        mem.ttl_check.return_value = {"archived": 0, "total_checked": 0, "bytes_saved": 0}
        scaling = MagicMock()
        return sched, mem, scaling

    def test_scheduler_with_history(self) -> None:
        """With 10 task durations, ETC should be computed from data (not 1.0)."""
        from bots.hive_pipelines import predictive_scheduler

        sched, mem, scaling = self._make_mocks()
        durations = [2.0, 2.5, 3.0, 2.8, 3.2, 2.9, 3.1, 2.7, 3.0, 3.5]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            records = [{"task_type": "test_task", "actual_time": d} for d in durations]
            json.dump(records, f)
            log_path = f.name

        try:
            result = predictive_scheduler(sched, mem, scaling,
                                          task_type="test_task", log_path=log_path)
        finally:
            os.unlink(log_path)

        self.assertEqual(result["source"], "history")
        self.assertNotAlmostEqual(result["etc_seconds"], 1.0, places=2,
                                  msg="ETC should be derived from history, not hardcoded 1.0.")
        self.assertGreater(result["sample_size"], 0)

    def test_scheduler_empty_log(self) -> None:
        """Empty history → fallback to 1.0, flagged as default."""
        from bots.hive_pipelines import predictive_scheduler

        sched, mem, scaling = self._make_mocks()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([], f)
            log_path = f.name

        try:
            result = predictive_scheduler(sched, mem, scaling,
                                          task_type="nonexistent_task", log_path=log_path)
        finally:
            os.unlink(log_path)

        self.assertEqual(result["source"], "default")
        self.assertAlmostEqual(result["etc_seconds"], 1.0, places=4)

    def test_scheduler_ewma_recency_bias(self) -> None:
        """Recent durations should weigh more heavily than older ones."""
        from bots.hive_pipelines import _ewma

        # Old observations are small, recent ones are large → EWMA > simple mean
        old_low = [1.0] * 7
        recent_high = [10.0, 10.0, 10.0]
        values = old_low + recent_high
        ewma_val = _ewma(values, alpha=0.5)
        simple_mean = sum(values) / len(values)
        self.assertGreater(ewma_val, simple_mean,
                           "EWMA should weight recent high values more than mean.")

    def test_scheduler_missing_log_falls_back(self) -> None:
        """Missing log file falls back to default gracefully."""
        from bots.hive_pipelines import predictive_scheduler

        sched, mem, scaling = self._make_mocks()
        result = predictive_scheduler(sched, mem, scaling,
                                      log_path="/nonexistent/path.json")
        self.assertEqual(result["source"], "default")
        self.assertAlmostEqual(result["etc_seconds"], 1.0, places=4)


# ─────────────────────────────────────────────────────────────────────────────
# W4-07: UI Data Service get_phase_fsm
# ─────────────────────────────────────────────────────────────────────────────
class _MockMFGCSystem:
    """Minimal mock of the mfgc_system dependency."""

    def __init__(self, confidence: float = 0.5, variables: dict | None = None):
        self._confidence = confidence
        self._variables = variables or {}

    def get_system_state(self) -> dict:
        return {"confidence": self._confidence, "variables": self._variables, "band": "test"}

    def get_active_gates(self) -> list:
        return []

    def get_swarm_agents(self) -> list:
        return []

    def get_execution_packets(self) -> list:
        return []


class TestGetPhaseFSM(unittest.TestCase):
    """W4-07: get_phase_fsm() — Type and Enumerate phases implemented."""

    def _make_service(self, confidence: float = 0.5, variables: dict | None = None):
        from src.ui_data_service import UIDataService
        system = _MockMFGCSystem(confidence=confidence, variables=variables)
        return UIDataService(system)

    def test_type_phase_valid(self) -> None:
        """State with correctly-typed variables → Type phase passes."""
        service = self._make_service(
            confidence=0.1,
            variables={"score": {"dtype": "float", "value": 0.5}},
        )
        fsm = service.get_phase_fsm()
        type_phase = fsm["type_phase"]
        self.assertEqual(type_phase["status"], "pass")
        self.assertNotIn("score", type_phase.get("errors", []))

    def test_type_phase_mismatch(self) -> None:
        """State with wrong types → Type phase fails with specific errors."""
        service = self._make_service(
            confidence=0.1,
            variables={"count": {"dtype": "int", "value": "not_an_int"}},
        )
        fsm = service.get_phase_fsm()
        type_phase = fsm["type_phase"]
        self.assertEqual(type_phase["status"], "fail")
        errors = type_phase.get("errors", [])
        self.assertTrue(any("count" in e for e in errors),
                        f"Expected error mentioning 'count'. Got: {errors}")

    def test_enumerate_phase_lists_transitions(self) -> None:
        """Given state 'Expand' (low confidence) → lists valid next states."""
        service = self._make_service(confidence=0.1)  # Expand phase
        fsm = service.get_phase_fsm()
        self.assertEqual(fsm["current_phase"], "Expand")
        enum_phase = fsm["enumerate_phase"]
        transitions = enum_phase["results"]["valid_transitions"]
        self.assertIn("Constrain", transitions)
        self.assertGreater(len(transitions), 0)

    def test_full_fsm_traversal(self) -> None:
        """Walk through all phases — no 'Not implemented' messages anywhere."""
        for confidence in [0.1, 0.5, 0.75, 0.85, 0.92]:
            service = self._make_service(confidence=confidence)
            fsm = service.get_phase_fsm()
            # Serialise to string and check no 'not implemented' text
            fsm_str = json.dumps(fsm).lower()
            self.assertNotIn("not implemented",
                             fsm_str,
                             f"Found 'Not implemented' at confidence={confidence}: {fsm_str[:200]}")

    def test_type_phase_allowed_is_true(self) -> None:
        """Type phase must always be allowed (not False)."""
        service = self._make_service()
        fsm = service.get_phase_fsm()
        self.assertTrue(fsm["fsm"]["Type"]["allowed"],
                        "Type phase should be allowed (not hardcoded False).")

    def test_enumerate_phase_allowed_is_true(self) -> None:
        """Enumerate phase must always be allowed (not False)."""
        service = self._make_service()
        fsm = service.get_phase_fsm()
        self.assertTrue(fsm["fsm"]["Enumerate"]["allowed"],
                        "Enumerate phase should be allowed (not hardcoded False).")

    def test_fsm_structure_complete(self) -> None:
        """All 7 phases must be present in the FSM output."""
        service = self._make_service()
        fsm = service.get_phase_fsm()
        for phase in ("Expand", "Type", "Enumerate", "Constrain", "Collapse", "Bind", "Execute"):
            self.assertIn(phase, fsm["fsm"], f"Phase {phase} missing from FSM.")


if __name__ == "__main__":
    unittest.main()
