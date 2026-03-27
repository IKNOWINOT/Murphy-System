"""
Commissioning-specific document templates.

Each function accepts a ``CommissioningPlan``-shaped dict (the ``result.plan``
from the commissioning bot Output) plus an optional :class:`BrandProfile` and
renders a Markdown string that can be fed to any downstream format converter.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _brand_header(brand: Optional[Any], document_title: str) -> str:
    """Return a rendered Markdown header line (or empty string if no brand)."""
    if brand is None:
        return ""
    ctx = {
        "document_title": document_title,
        "date": date.today().isoformat(),
        "page_number": "1",
    }
    header = brand.render_header(ctx)
    return f"_{header}_\n\n---\n\n"


def _brand_footer(brand: Optional[Any]) -> str:
    """Return a rendered Markdown footer line (or empty string if no brand)."""
    if brand is None:
        return ""
    ctx = {"page_number": "—", "date": date.today().isoformat()}
    footer = brand.render_footer(ctx)
    return f"\n\n---\n\n_{footer}_"


def _cover_page(plan: Dict[str, Any], brand: Optional[Any]) -> str:
    """Render the cover page block."""
    company = brand.company_name if brand else "murphy_system"
    site = plan.get("site", "N/A")
    system = plan.get("system", "N/A")
    today = date.today().isoformat()
    lines = [
        "---",
        "# Commissioning Plan Report",
        "",
        f"**Project Site:** {site}",
        f"**System:** {system}",
        f"**Prepared by:** {company}",
        f"**Date:** {today}",
    ]
    if brand and brand.legal_line:
        lines.append(f"**{brand.legal_line}**")
    lines.append("---")
    return "\n".join(lines)


def _asset_table(assets: List[Dict[str, Any]]) -> str:
    """Render an asset inventory as a Markdown table."""
    if not assets:
        return "_No assets listed._"
    rows = ["| ID | Name | Type | Tag | Location |", "|----|------|------|-----|----------|"]
    for a in assets:
        rows.append(
            "| {id} | {name} | {type} | {tag} | {location} |".format(
                id=a.get("id", ""),
                name=a.get("name", ""),
                type=a.get("type", ""),
                tag=a.get("tag", ""),
                location=a.get("location", ""),
            )
        )
    return "\n".join(rows)


def _point_table(points: List[Dict[str, Any]]) -> str:
    """Render a BAS point list as a Markdown table."""
    if not points:
        return "_No points listed._"
    rows = [
        "| Name | Type | Unit | Source | Asset ID | Range |",
        "|------|------|------|--------|----------|-------|",
    ]
    for p in points:
        rng = p.get("range", {})
        range_str = (
            f"{rng.get('min', '')}–{rng.get('max', '')} {rng.get('unit', '')}"
            if isinstance(rng, dict)
            else str(rng)
        )
        rows.append(
            "| {name} | {pt} | {unit} | {src} | {aid} | {rng} |".format(
                name=p.get("name", ""),
                pt=p.get("point_type", ""),
                unit=p.get("unit", ""),
                src=p.get("source", ""),
                aid=p.get("asset_id", ""),
                rng=range_str,
            )
        )
    return "\n".join(rows)


def _procedure_block(proc: Dict[str, Any], index: int) -> str:
    """Render a single test procedure."""
    title = proc.get("name", f"Procedure {index}")
    lines = [f"### {index}. {title}", ""]

    preconditions = proc.get("preconditions", [])
    if preconditions:
        lines.append("**Preconditions:**")
        for pre in preconditions:
            lines.append(f"- {pre}")
        lines.append("")

    steps = proc.get("steps", [])
    if steps:
        lines.append("**Steps:**")
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. {step}")
        lines.append("")

    acceptance = proc.get("acceptance", [])
    if acceptance:
        lines.append("**Acceptance Criteria:**")
        for crit in acceptance:
            lines.append(f"- {crit}")
        lines.append("")

    risks = proc.get("risks", [])
    if risks:
        lines.append("**Risks:**")
        for r in risks:
            lines.append(f"- {r}")
        lines.append("")

    return "\n".join(lines)


def _risk_table(risk_register: Dict[str, Any]) -> str:
    """Render a risk register as a Markdown table."""
    items = risk_register.get("items", []) if isinstance(risk_register, dict) else []
    if not items:
        return "_No risks recorded._"
    rows = [
        "| ID | Description | Severity | Mitigation |",
        "|----|-------------|----------|------------|",
    ]
    for r in items:
        rows.append(
            "| {id} | {desc} | {sev} | {mit} |".format(
                id=r.get("id", ""),
                desc=r.get("description", ""),
                sev=r.get("severity", ""),
                mit=r.get("mitigation", ""),
            )
        )
    return "\n".join(rows)


def _deliverables_list(deliverables: List[Dict[str, Any]]) -> str:
    """Render deliverables as a bullet list."""
    if not deliverables:
        return "_No deliverables listed._"
    lines = []
    for d in deliverables:
        link = d.get("link", "")
        entry = f"- **{d.get('name', '')}** ({d.get('type', '')})"
        if link:
            entry += f" — [{link}]({link})"
        lines.append(entry)
    return "\n".join(lines)


def _schedule_block(schedule: Dict[str, Any]) -> str:
    """Render schedule information."""
    if not schedule:
        return "_No schedule provided._"
    lines = []
    window = schedule.get("window", {})
    if isinstance(window, dict):
        start = window.get("start", "TBD")
        end = window.get("end", "TBD")
        lines.append(f"- **Start:** {start}")
        lines.append(f"- **End:** {end}")
    elif window:
        lines.append(f"- **Window:** {window}")
    deps = schedule.get("dependencies", [])
    if deps:
        lines.append(f"- **Dependencies:** {', '.join(str(d) for d in deps)}")
    return "\n".join(lines) if lines else "_No schedule provided._"


# ---------------------------------------------------------------------------
# Public template functions
# ---------------------------------------------------------------------------


def cx_plan_report(plan: Dict[str, Any], brand: Optional[Any] = None) -> str:
    """
    Full commissioning plan report.

    Sections: cover page, project info, asset inventory, point list,
    test procedures, risk register, deliverables, schedule.
    """
    parts: list[str] = []

    parts.append(_brand_header(brand, "Commissioning Plan Report"))
    parts.append(_cover_page(plan, brand))
    parts.append("\n\n## Table of Contents\n")
    toc = [
        "1. Project Information",
        "2. Asset Inventory",
        "3. Point List",
        "4. Test Procedures",
        "5. Risk Register",
        "6. Deliverables",
        "7. Schedule",
    ]
    parts.append("\n".join(toc))

    # 1. Project Information
    parts.append("\n\n## 1. Project Information\n")
    parts.append(f"- **Site:** {plan.get('site', 'N/A')}")
    parts.append(f"- **System:** {plan.get('system', 'N/A')}")

    # 2. Asset Inventory
    parts.append("\n\n## 2. Asset Inventory\n")
    parts.append(_asset_table(plan.get("assets", [])))

    # 3. Point List
    parts.append("\n\n## 3. Point List\n")
    parts.append(_point_table(plan.get("points", [])))

    # 4. Test Procedures
    parts.append("\n\n## 4. Test Procedures\n")
    procedures = plan.get("procedures", [])
    if procedures:
        for i, proc in enumerate(procedures, 1):
            parts.append(_procedure_block(proc, i))
    else:
        parts.append("_No procedures defined._")

    # 5. Risk Register
    parts.append("\n\n## 5. Risk Register\n")
    parts.append(_risk_table(plan.get("risk_register", {})))

    # 6. Deliverables
    parts.append("\n\n## 6. Deliverables\n")
    parts.append(_deliverables_list(plan.get("deliverables", [])))

    # 7. Schedule
    parts.append("\n\n## 7. Schedule\n")
    parts.append(_schedule_block(plan.get("schedule", {})))

    parts.append(_brand_footer(brand))
    return "\n".join(parts)


def _fpt_from_meta_forms(forms: List[Dict[str, Any]], plan: Dict[str, Any], brand: Optional[Any]) -> str:
    """
    Render the FPT report from the commissioning bot's ``meta.forms`` structured
    data (generated by ``makeFPTForms()`` in ``bots/commissioning_bot/internal/forms/fpt.ts``).

    Each form object contains the rich step-level fields produced by the bot:
    ``action``, ``expected_effect``, ``hold_s``, ``safety``, ``watch_points``,
    and per-step capture fields (``observed``, ``pass``, ``notes``).
    """
    site = plan.get("site", "N/A")
    system = plan.get("system", "N/A")
    company = brand.company_name if brand else "murphy_system"

    parts: list[str] = []
    parts.append(_brand_header(brand, "Functional Performance Test Report"))
    parts.append("# Functional Performance Test Report\n")
    parts.append(f"**Site:** {site}  |  **System:** {system}  |  **Prepared by:** {company}\n")
    parts.append(f"**Date:** {date.today().isoformat()}\n")
    parts.append("---\n")

    for idx, form_obj in enumerate(forms, 1):
        form = form_obj.get("content", form_obj)
        title = form.get("title", form.get("id", f"Test {idx}"))
        form_id = form.get("id", f"{idx:03d}")
        parts.append(f"## FPT-{form_id}: {title}\n")

        # Preconditions
        preconditions = form.get("preconditions", [])
        if preconditions:
            parts.append("**Preconditions:**")
            for pre in preconditions:
                parts.append(f"- [ ] {pre}")
            parts.append("")

        # Rich step table from meta.forms
        steps = form.get("steps", [])
        if steps:
            parts.append("**Test Steps:**\n")
            parts.append(
                "| # | Action | Expected Effect | Hold (s) | Observed | Pass? | Notes |"
            )
            parts.append("|---|--------|-----------------|----------|----------|-------|-------|")
            for step in steps:
                action = step.get("action", "")
                expected = step.get("expected_effect", "")
                hold = str(step.get("hold_s", "")) if step.get("hold_s") else ""
                # Safety warnings in bold if present
                safety = step.get("safety", [])
                if safety:
                    action = f"**⚠ {'; '.join(safety)}** {action}".strip()
                parts.append(
                    f"| {step.get('id', '')} | {action} | {expected} | {hold} |  |  |  |"
                )
            parts.append("")

        # Watch points
        watch_points = form.get("watch_points", [])
        if watch_points:
            parts.append("**Watch Points:**")
            for wp in watch_points:
                parts.append(f"- {wp}")
            parts.append("")

        # Acceptance criteria
        acceptance = form.get("acceptance", [])
        if acceptance:
            parts.append("**Acceptance Criteria:**")
            for crit in acceptance:
                parts.append(f"- [ ] {crit}")
            parts.append("")

        # Sign-off block from bot-generated signoff list
        signoff = form.get("signoff", [
            {"role": "CxA", "name": "", "date": ""},
            {"role": "Controls", "name": "", "date": ""},
            {"role": "Owner", "name": "", "date": ""},
        ])
        parts.append("**Sign-off:**\n")
        parts.append("| Role | Name | Date |")
        parts.append("|------|------|------|")
        for s in signoff:
            parts.append(f"| {s.get('role', '')} | {s.get('name', '_______')} | {s.get('date', '_______')} |")
        parts.append("")
        parts.append("---\n")

    parts.append(_brand_footer(brand))
    return "\n".join(parts)


def fpt_report(plan: Dict[str, Any], brand: Optional[Any] = None) -> str:
    """
    Functional Performance Test (FPT) report template.

    When the commissioning bot's ``meta.forms`` data is available (embedded
    under the ``_meta_forms`` key by :meth:`~export_pipeline.ExportPipeline._extract_plan`),
    the richer structured form data from the bot is used directly — rendering
    step-level fields (action, expected_effect, hold_s, safety, watch_points,
    signoff) as produced by ``makeFPTForms()`` in the commissioning bot.

    Falls back to the procedure-based layout when ``_meta_forms`` is absent.
    """
    meta_forms: List[Dict[str, Any]] = plan.get("_meta_forms", [])
    if meta_forms:
        return _fpt_from_meta_forms(meta_forms, plan, brand)

    # ---------- fallback: render from procedures in the plan ----------
    parts: list[str] = []
    parts.append(_brand_header(brand, "Functional Performance Test Report"))
    site = plan.get("site", "N/A")
    system = plan.get("system", "N/A")
    company = brand.company_name if brand else "murphy_system"

    parts.append("# Functional Performance Test Report\n")
    parts.append(f"**Site:** {site}  |  **System:** {system}  |  **Prepared by:** {company}\n")
    parts.append(f"**Date:** {date.today().isoformat()}\n")
    parts.append("---\n")

    procedures = plan.get("procedures", [])
    if not procedures:
        parts.append("_No procedures defined._")
    else:
        for i, proc in enumerate(procedures, 1):
            parts.append(f"## FPT-{i:03d}: {proc.get('name', f'Test {i}')}\n")

            preconditions = proc.get("preconditions", [])
            if preconditions:
                parts.append("**Preconditions:**")
                for pre in preconditions:
                    parts.append(f"- [ ] {pre}")
                parts.append("")

            steps = proc.get("steps", [])
            if steps:
                parts.append("**Test Steps:**\n")
                parts.append("| # | Step | Expected Result | Actual Result | Pass/Fail |")
                parts.append("|---|------|-----------------|---------------|-----------|")
                for j, step in enumerate(steps, 1):
                    parts.append(f"| {j} | {step} |  |  |  |")
                parts.append("")

            acceptance = proc.get("acceptance", [])
            if acceptance:
                parts.append("**Acceptance Criteria:**")
                for crit in acceptance:
                    parts.append(f"- [ ] {crit}")
                parts.append("")

            parts.append("**Technician Sign-off:** _________________  **Date:** _________\n")
            parts.append("---\n")

    parts.append(_brand_footer(brand))
    return "\n".join(parts)


def cx_punch_list(plan: Dict[str, Any], brand: Optional[Any] = None) -> str:
    """
    Commissioning punch list template.

    Extracts open items from procedures and risk register.
    """
    parts: list[str] = []
    parts.append(_brand_header(brand, "Commissioning Punch List"))
    site = plan.get("site", "N/A")
    company = brand.company_name if brand else "murphy_system"

    parts.append("# Commissioning Punch List\n")
    parts.append(f"**Site:** {site}  |  **Prepared by:** {company}  |  **Date:** {date.today().isoformat()}\n")
    parts.append("---\n")

    parts.append("| # | Description | System | Priority | Responsible | Due Date | Status |")
    parts.append("|---|-------------|--------|----------|-------------|----------|--------|")

    item_num = 1
    # Items from risk register
    risk_register = plan.get("risk_register", {})
    risks = risk_register.get("items", []) if isinstance(risk_register, dict) else []
    for r in risks:
        sev = r.get("severity", "medium")
        parts.append(
            f"| {item_num} | {r.get('description', '')} | {plan.get('system', '')} "
            f"| {sev} |  |  | Open |"
        )
        item_num += 1

    # Items from procedure risks
    for proc in plan.get("procedures", []):
        for risk in proc.get("risks", []):
            parts.append(
                f"| {item_num} | {risk} | {plan.get('system', '')} | medium |  |  | Open |"
            )
            item_num += 1

    if item_num == 1:
        parts.append("_No open items._")

    parts.append(_brand_footer(brand))
    return "\n".join(parts)


def cx_summary(plan: Dict[str, Any], brand: Optional[Any] = None) -> str:
    """
    Executive summary template for a commissioning project.
    """
    parts: list[str] = []
    parts.append(_brand_header(brand, "Commissioning Executive Summary"))
    site = plan.get("site", "N/A")
    system = plan.get("system", "N/A")
    company = brand.company_name if brand else "murphy_system"

    parts.append("# Commissioning Executive Summary\n")
    parts.append(f"**Site:** {site}  |  **System:** {system}  |  **Prepared by:** {company}\n")
    parts.append(f"**Date:** {date.today().isoformat()}\n")
    parts.append("---\n")

    # Counts
    n_assets = len(plan.get("assets", []))
    n_points = len(plan.get("points", []))
    n_procedures = len(plan.get("procedures", []))
    deliverables = plan.get("deliverables", [])

    parts.append("## Scope at a Glance\n")
    parts.append(f"- **Assets in scope:** {n_assets}")
    parts.append(f"- **BAS points:** {n_points}")
    parts.append(f"- **Test procedures:** {n_procedures}")
    parts.append(f"- **Deliverables:** {len(deliverables)}")

    # Schedule highlights
    schedule = plan.get("schedule", {})
    window = schedule.get("window", {}) if isinstance(schedule, dict) else {}
    if isinstance(window, dict) and (window.get("start") or window.get("end")):
        parts.append("\n## Schedule\n")
        parts.append(f"- **Start:** {window.get('start', 'TBD')}")
        parts.append(f"- **End:** {window.get('end', 'TBD')}")

    # Deliverables
    if deliverables:
        parts.append("\n## Key Deliverables\n")
        for d in deliverables:
            parts.append(f"- {d.get('name', '')} ({d.get('type', '')})")

    # Risk summary
    risk_register = plan.get("risk_register", {})
    risks = risk_register.get("items", []) if isinstance(risk_register, dict) else []
    if risks:
        parts.append("\n## Risk Summary\n")
        parts.append(f"Total risks identified: **{len(risks)}**\n")
        high = [r for r in risks if str(r.get("severity", "")).lower() in ("high", "critical")]
        if high:
            parts.append(f"- **High/Critical:** {len(high)}")

    parts.append(_brand_footer(brand))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Template registry for the pipeline
# ---------------------------------------------------------------------------

COMMISSIONING_TEMPLATES: Dict[str, Any] = {
    "cx_plan_report": cx_plan_report,
    "fpt_report": fpt_report,
    "cx_punch_list": cx_punch_list,
    "cx_summary": cx_summary,
}
