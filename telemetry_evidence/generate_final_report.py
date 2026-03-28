#!/usr/bin/env python3
"""
PHASE 8: Generate the final evidence report.

Reads all telemetry_evidence/ data and produces FINAL_REPORT.md
"""

import json
import glob
import os
import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "telemetry_log.jsonl")
REPORT_FILE = os.path.join(SCRIPT_DIR, "FINAL_REPORT.md")


def timestamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load_log_entries():
    """Load all entries from the telemetry log."""
    entries = []
    if not os.path.exists(LOG_FILE):
        return entries
    with open(LOG_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def load_phase_summary(phase_dir, summary_filename):
    """Load a phase summary JSON file."""
    filepath = os.path.join(SCRIPT_DIR, phase_dir, summary_filename)
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    # Try finding any summary file in the directory
    pattern = os.path.join(SCRIPT_DIR, phase_dir, "*summary*.json")
    files = glob.glob(pattern)
    if files:
        with open(files[0], "r") as f:
            return json.load(f)
    return None


def count_evidence_files():
    """Count all evidence files generated."""
    count = 0
    for root, _dirs, files in os.walk(SCRIPT_DIR):
        for f in files:
            if f.endswith((".json", ".txt", ".xml", ".log")):
                count += 1
    return count


def generate_report():
    """Generate the comprehensive final report."""
    print("=" * 60)
    print(" PHASE 8: Generating Final Report")
    print(f" {timestamp()}")
    print("=" * 60)
    print()

    entries = load_log_entries()
    total_events = len(entries)
    pass_count = sum(1 for e in entries if e.get("status") == "pass")
    fail_count = sum(1 for e in entries if e.get("status") == "fail")
    warn_count = sum(1 for e in entries if e.get("status") in ("warn", "partial"))
    evidence_files = count_evidence_files()

    # Collect phase summaries
    phase_summaries = {
        "Phase 1 (Health)": load_phase_summary("03_health", "phase1_summary.json"),
        "Phase 2 (API Core)": load_phase_summary("04_api_core", "phase2_summary.json"),
        "Phase 3 (UI)": load_phase_summary("17_ui_interfaces", "phase3_summary.json"),
        "Phase 4 (Security)": load_phase_summary("18_security_plane", "phase4_summary.json"),
        "Phase 6 (Sales Demo)": load_phase_summary("21_sales_demo", "phase6_summary.json"),
        "Phase 7 (Fix Loop)": load_phase_summary("22_fixes_applied", "phase7_summary.json"),
    }

    # Generate markdown
    lines = []
    lines.append("# Murphy System — Final Telemetry Evidence Report")
    lines.append("")
    lines.append(f"**Generated:** {timestamp()}")
    lines.append(f"**Total telemetry events:** {total_events}")
    lines.append(f"**Evidence files generated:** {evidence_files}")
    lines.append("")
    lines.append("## Overall Results")
    lines.append("")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| ✅ Passed | {pass_count} |")
    lines.append(f"| ❌ Failed | {fail_count} |")
    lines.append(f"| ⚠️ Warnings | {warn_count} |")
    lines.append(f"| 📊 Total Events | {total_events} |")
    lines.append(f"| 📁 Evidence Files | {evidence_files} |")
    lines.append("")

    # Phase-by-phase breakdown
    lines.append("## Phase-by-Phase Summary")
    lines.append("")
    for phase_name, summary in phase_summaries.items():
        lines.append(f"### {phase_name}")
        lines.append("")
        if summary is None:
            lines.append("_No data collected — phase may not have been executed._")
        else:
            if "overall" in summary:
                overall = summary["overall"]
                p = overall.get("passed", 0)
                t = overall.get("total", 0)
                pct = (p / t * 100) if t > 0 else 0
                lines.append(f"- **Result:** {p}/{t} passed ({pct:.0f}%)")
            # Show sub-sections if present
            for key, val in summary.items():
                if key in ("phase", "timestamp", "overall"):
                    continue
                if isinstance(val, dict) and "passed" in val and "total" in val:
                    lines.append(
                        f"- {key}: {val['passed']}/{val['total']} passed"
                    )
                elif isinstance(val, list):
                    lines.append(f"- {key}: {len(val)} items")
        lines.append("")

    # Failure details
    failures = [e for e in entries if e.get("status") == "fail"]
    if failures:
        lines.append("## Failure Details")
        lines.append("")
        lines.append("| Phase | Step | Detail |")
        lines.append("|-------|------|--------|")
        seen = set()
        for f_item in failures:
            key = f"{f_item.get('phase', '')}:{f_item.get('step', '')}"
            if key in seen:
                continue
            seen.add(key)
            detail = f_item.get("detail", "")[:60]
            lines.append(
                f"| {f_item.get('phase', '')} | {f_item.get('step', '')} | {detail} |"
            )
        lines.append("")

    # Evidence directory listing
    lines.append("## Evidence Directory Structure")
    lines.append("")
    lines.append("```")
    for dirname in sorted(os.listdir(SCRIPT_DIR)):
        dirpath = os.path.join(SCRIPT_DIR, dirname)
        if os.path.isdir(dirpath) and not dirname.startswith("."):
            file_count = len(
                [
                    f
                    for f in os.listdir(dirpath)
                    if os.path.isfile(os.path.join(dirpath, f))
                ]
            )
            lines.append(f"  {dirname}/ ({file_count} files)")
    lines.append("```")
    lines.append("")

    # Write report
    report_content = "\n".join(lines)
    with open(REPORT_FILE, "w") as f:
        f.write(report_content)

    print(f"  ✓ Report written to {REPORT_FILE}")
    print(f"  Total events: {total_events}")
    print(f"  Passed: {pass_count}, Failed: {fail_count}, Warnings: {warn_count}")
    print(f"  Evidence files: {evidence_files}")
    print()
    print("=" * 60)
    print(" PHASE 8 COMPLETE: FINAL_REPORT.md generated")
    print("=" * 60)

    return {
        "report_file": REPORT_FILE,
        "total_events": total_events,
        "passed": pass_count,
        "failed": fail_count,
        "warnings": warn_count,
    }


if __name__ == "__main__":
    generate_report()
