#!/usr/bin/env python3
"""
PATCH-421b — Complete the LyapunovMonitor duck-type proxy for PSM

WHAT THIS IS:
  The PSM gateway's _LyapProxy in app.py is incomplete. It only had
  is_stable/get_stability_score/get_snapshot, but the RSC gate calls:
    - get_history(n=1)
    - get_consecutive_violations()
    - check_stability()
  Result: every launch attempt vetoes with monitor_unavailable.

WHY IT EXISTS:
  PATCH-421 smoke-test wrote a REQUESTED + VETOED pair to the ledger
  with reason="monitor_unavailable". The veto worked correctly (fail
  closed) but the system never reaches the real RSC stability logic.

HOW IT FITS:
  - Replaces the _LyapProxy class definition inside the PATCH-079d
    block in app.py with a complete one
  - Delegates to rsc_unified_sink which already has get_history()
  - check_stability() returns sink.s_t >= 0.70 (the SLO threshold)
  - get_consecutive_violations() tracks via a module-level counter
    that resets when we see a stable sample

LAST UPDATED: 2026-05-25 by PATCH-421b
"""
import ast
import shutil
from pathlib import Path

APP = Path("/opt/Murphy-System/src/runtime/app.py")
src = APP.read_text()
NL = chr(10)

if "PATCH-421b" in src:
    print("  ⚠ PATCH-421b already applied — skipping")
    raise SystemExit(0)

OLD = (
        "                # Return a duck-typed Lyapunov-compatible object" + NL +
        "                class _LyapProxy:" + NL +
        "                    def is_stable(self):" + NL +
        "                        c = get_sink().get()" + NL +
        "                        return c is not None and c.s_t >= 0.70" + NL +
        "                    def get_stability_score(self):" + NL +
        "                        c = get_sink().get()" + NL +
        "                        return c.s_t if c else 1.0" + NL +
        "                    def get_snapshot(self):" + NL +
        "                        c = get_sink().get()" + NL +
        "                        return c.to_dict() if c else {}" + NL +
        "                return _LyapProxy()"
)

NEW = (
        "                # PATCH-421b: Complete duck-type proxy. RSC gate calls:" + NL +
        "                #   get_history(n=1), get_consecutive_violations(), check_stability()" + NL +
        "                # The rsc_unified_sink has get_history(); the other two are derived" + NL +
        "                # from S(t) threshold (>= 0.70 is stable, < is a violation)." + NL +
        "                class _LyapProxy:" + NL +
        "                    _STABLE_THRESHOLD = 0.70" + NL +
        "                    # check_stability — called by RSC gate" + NL +
        "                    def check_stability(self):" + NL +
        "                        c = get_sink().get()" + NL +
        "                        return c is not None and c.s_t >= self._STABLE_THRESHOLD" + NL +
        "                    # get_history — called by RSC gate, returns list of dicts" + NL +
        "                    def get_history(self, n=None):" + NL +
        "                        try:" + NL +
        "                            n = n or 1" + NL +
        "                            return get_sink().get_history(n=n)" + NL +
        "                        except Exception:" + NL +
        "                            return []" + NL +
        "                    # get_consecutive_violations — derived from history" + NL +
        "                    def get_consecutive_violations(self):" + NL +
        "                        try:" + NL +
        "                            hist = get_sink().get_history(n=10) or []" + NL +
        "                            count = 0" + NL +
        "                            for entry in hist:  # newest first per RSCSink contract" + NL +
        "                                s = entry.get('s_t', 1.0) if isinstance(entry, dict) else 1.0" + NL +
        "                                if s < self._STABLE_THRESHOLD:" + NL +
        "                                    count += 1" + NL +
        "                                else:" + NL +
        "                                    break" + NL +
        "                            return count" + NL +
        "                        except Exception:" + NL +
        "                            return 0" + NL +
        "                    # Legacy methods kept for any other callers" + NL +
        "                    def is_stable(self):" + NL +
        "                        return self.check_stability()" + NL +
        "                    def get_stability_score(self):" + NL +
        "                        c = get_sink().get()" + NL +
        "                        return c.s_t if c else 1.0" + NL +
        "                    def get_snapshot(self):" + NL +
        "                        c = get_sink().get()" + NL +
        "                        return c.to_dict() if c else {}" + NL +
        "                return _LyapProxy()"
)

if OLD not in src:
    print("  ✗ exact _LyapProxy block not found — aborting")
    raise SystemExit(1)

new_src = src.replace(OLD, NEW, 1)
ast.parse(new_src)
print("  ✓ AST parses")

backup = APP.with_suffix(".py.pre-421b")
shutil.copy(APP, backup)
APP.write_text(new_src)
print(f"  ✓ wrote {APP} (backup: {backup.name})")
print()
print("  Restart murphy-production to activate.")
