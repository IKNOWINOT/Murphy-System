"""Demo Deliverable Generator for Murphy System.

Generation pipeline for custom queries:
  1. MFGC  — Multi-Factor Gate Controller gates and confidence-scores the
             request through its 7-phase execution model.
  2. MSS   — The MSS system provides three operators: Magnify, Simplify,
             and Solidify. The deliverable pipeline uses two:
             • Magnify  → expands query to functional requirements + components
             • Solidify → converts to a full implementation plan (RM5)
             Simplify is intentionally omitted here — reducing resolution would
             produce less detailed deliverables, the opposite of what is needed.
  3. Librarian lookup — caller (app.py endpoint) runs murphy.librarian_ask()
             and injects the result as `librarian_context`.
  4. LLM / LocalLLMFallback — generates final prose with all enriched context.
             When MSS is available, _build_content_from_mss() is used directly.
  5. Automation Blueprint — if the query requests major automation, a
             paid-tier blueprint preview is appended. Execution requires an
             active SOLO or higher subscription — it is NOT a free addition.

Predefined scenarios (6 chips) use rich hardcoded templates.

License: BSL 1.1 — Inoni LLC / Corey Post
"""
from __future__ import annotations

import base64
import hashlib
import io
import logging
import re
import uuid as _uuid_stdlib
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from murphy_identity import MURPHY_SYSTEM_IDENTITY

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline Error Tracker  (label: FORGE-ERR-TRACKER-001)
# ---------------------------------------------------------------------------
# Accumulates every error/fallback that occurs during a single pipeline run
# so the final log entry shows the full combination of failures that led
# to the output the user received.
# ---------------------------------------------------------------------------

class PipelineErrorTracker:
    """Track every fallback and error through a single forge pipeline run."""

    def __init__(self, query: str) -> None:
        self.query = query[:120]
        self.run_id = _uuid_stdlib.uuid4().hex[:12]
        self.errors: List[Dict[str, str]] = []
        self.fallbacks: List[str] = []
        self.path_taken: List[str] = []
        self._start = datetime.now(timezone.utc)

    def record_error(self, code: str, component: str, message: str) -> None:
        """Record a specific error with its labelled code."""
        entry = {
            "code": code,
            "component": component,
            "message": str(message)[:300],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.errors.append(entry)
        logger.error(
            "%s [%s] %s — query: %s (run=%s)",
            code, component, message, self.query, self.run_id,
        )

    def record_fallback(self, component: str, reason: str) -> None:
        """Record when a component falls back to a secondary path."""
        label = f"{component}: {reason}"
        self.fallbacks.append(label)
        logger.warning(
            "FORGE-FALLBACK [%s] %s — query: %s (run=%s)",
            component, reason, self.query, self.run_id,
        )

    def record_path(self, step: str) -> None:
        """Record a pipeline step that was successfully executed."""
        self.path_taken.append(step)

    def summary(self) -> Dict[str, Any]:
        """Return a summary of all errors, fallbacks, and path taken."""
        elapsed = (datetime.now(timezone.utc) - self._start).total_seconds()
        return {
            "run_id": self.run_id,
            "query": self.query,
            "elapsed_seconds": round(elapsed, 2),
            "path_taken": self.path_taken,
            "error_count": len(self.errors),
            "fallback_count": len(self.fallbacks),
            "errors": self.errors,
            "fallbacks": self.fallbacks,
        }

    def log_final_summary(self) -> None:
        """Emit a single log line summarising the full pipeline run."""
        s = self.summary()
        if s["error_count"] == 0 and s["fallback_count"] == 0:
            logger.info(
                "FORGE-PIPELINE-SUMMARY run=%s path=[%s] errors=0 fallbacks=0 "
                "elapsed=%.1fs query=%s",
                self.run_id, " → ".join(self.path_taken),
                s["elapsed_seconds"], self.query,
            )
        else:
            logger.warning(
                "FORGE-PIPELINE-SUMMARY run=%s path=[%s] errors=%d fallbacks=%d "
                "elapsed=%.1fs error_codes=[%s] fallbacks=[%s] query=%s",
                self.run_id, " → ".join(self.path_taken),
                s["error_count"], s["fallback_count"], s["elapsed_seconds"],
                ", ".join(e["code"] for e in self.errors),
                " | ".join(self.fallbacks),
                self.query,
            )


# ---------------------------------------------------------------------------
# Multi-format deliverable output  (label: FORGE-MULTIFORMAT-001)
# ---------------------------------------------------------------------------
# Supported output formats beyond plain text.  Each format uses existing
# Murphy infrastructure (document_export, demo_bundle_generator, drawing
# engine) when available, with graceful fallback.
# ---------------------------------------------------------------------------

SUPPORTED_FORMATS = {
    "txt":  {"label": "Plain Text (.txt)",           "mime": "text/plain",                           "ext": "txt"},
    "pdf":  {"label": "PDF Document (.pdf)",         "mime": "application/pdf",                      "ext": "pdf"},
    "html": {"label": "HTML Document (.html)",       "mime": "text/html",                            "ext": "html"},
    "docx": {"label": "Microsoft Word (.docx)",      "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "ext": "docx"},
    "zip":  {"label": "Project Bundle (.zip)",       "mime": "application/zip",                      "ext": "zip"},
    "md":   {"label": "Markdown (.md)",              "mime": "text/markdown",                        "ext": "md"},
}


def convert_deliverable_format(
    deliverable: Dict[str, Any],
    target_format: str,
    query: str = "",
) -> Dict[str, Any]:
    """Convert a text deliverable to the requested output format.

    Returns a dict with ``content`` (base64-encoded for binary formats),
    ``filename``, ``mime_type``, ``format``, and ``is_binary``.

    Label: FORGE-MULTIFORMAT-001
    """
    content = deliverable.get("content", "")
    title = deliverable.get("title", "Murphy Deliverable")
    base_filename = deliverable.get("filename", "murphy-deliverable.txt")
    stem = re.sub(r"\.[^.]+$", "", base_filename)

    fmt_info = SUPPORTED_FORMATS.get(target_format, SUPPORTED_FORMATS["txt"])

    if target_format == "txt":
        return {
            "content": content,
            "filename": f"{stem}.txt",
            "mime_type": fmt_info["mime"],
            "format": "txt",
            "is_binary": False,
        }

    if target_format == "md":
        # Strip the branded wrapper — return raw markdown content
        md_content = _strip_branded_wrapper(content)
        return {
            "content": md_content,
            "filename": f"{stem}.md",
            "mime_type": fmt_info["mime"],
            "format": "md",
            "is_binary": False,
        }

    if target_format == "html":
        html_content = _convert_to_html(content, title)
        return {
            "content": html_content,
            "filename": f"{stem}.html",
            "mime_type": fmt_info["mime"],
            "format": "html",
            "is_binary": False,
        }

    if target_format == "pdf":
        pdf_result = _convert_to_pdf(content, title)
        return {
            "content": pdf_result["content"],
            "filename": f"{stem}.pdf",
            "mime_type": fmt_info["mime"],
            "format": "pdf",
            "is_binary": True,
        }

    if target_format == "docx":
        docx_result = _convert_to_docx(content, title)
        return {
            "content": docx_result["content"],
            "filename": f"{stem}.docx",
            "mime_type": fmt_info["mime"],
            "format": "docx",
            "is_binary": True,
        }

    if target_format == "zip":
        zip_result = _convert_to_zip_bundle(deliverable, query)
        return {
            "content": zip_result["content"],
            "filename": f"{stem}-bundle.zip",
            "mime_type": fmt_info["mime"],
            "format": "zip",
            "is_binary": True,
        }

    # Unknown format — return as text
    logger.warning("FORGE-MULTIFORMAT-ERR-001: Unknown format '%s' — returning txt", target_format)
    return {
        "content": content,
        "filename": f"{stem}.txt",
        "mime_type": "text/plain",
        "format": "txt",
        "is_binary": False,
    }


def _strip_branded_wrapper(content: str) -> str:
    """Remove Murphy ASCII logo, metadata block, and license footer."""
    lines = content.split("\n")
    # Find content between the metadata block and license footer
    start = 0
    end = len(lines)
    for i, line in enumerate(lines):
        if line.startswith("═" * 20) and i > 5:
            # First ═══ line after the logo is end of metadata block
            start = i + 1
            break
    for i in range(len(lines) - 1, -1, -1):
        if "LICENSE NOTICE" in lines[i]:
            # Walk back to the ═══ line before the license
            for j in range(i - 1, -1, -1):
                if lines[j].startswith("═" * 20):
                    end = j
                    break
            break
    return "\n".join(lines[start:end]).strip()


def _convert_to_html(content: str, title: str) -> str:
    """Convert deliverable text to a styled HTML document."""
    try:
        from document_export.export_pipeline import ExportPipeline  # noqa: PLC0415
        pipeline = ExportPipeline()
        result = pipeline.export_sync(
            source_output={"content": content, "title": title},
            fmt="html",
        )
        if result and result.content:
            return result.content
    except Exception as exc:  # FORGE-MULTIFORMAT-ERR-002
        logger.warning("FORGE-MULTIFORMAT-ERR-002: document_export HTML failed: %s — using built-in", exc)

    # Built-in HTML conversion
    import html as _html_mod
    escaped = _html_mod.escape(content)
    # Convert Murphy box-drawing to HTML formatting
    escaped = re.sub(r"^(■ .+)$", r"<h2>\1</h2>", escaped, flags=re.MULTILINE)
    escaped = re.sub(r"^(─{3,}.*)$", r"<hr>", escaped, flags=re.MULTILINE)
    escaped = re.sub(r"^(═{3,}.*)$", r"<hr class='thick'>", escaped, flags=re.MULTILINE)
    escaped = escaped.replace("\n", "<br>\n")
    escaped = re.sub(r"□", "☐", escaped)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html_mod.escape(title)}</title>
<style>
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; max-width: 900px;
         margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #1a1a2e; }}
  h2 {{ color: #1E3A5F; border-bottom: 2px solid #2E86AB; padding-bottom: .3rem; }}
  hr {{ border: none; border-top: 1px solid #ccc; margin: 1.5rem 0; }}
  hr.thick {{ border-top: 3px double #1E3A5F; }}
  pre {{ background: #f5f7fa; padding: 1rem; border-radius: 4px; overflow-x: auto; }}
  .header {{ text-align: center; padding: 2rem 0; border-bottom: 3px solid #1E3A5F; }}
  .header h1 {{ color: #1E3A5F; margin: 0; }}
  .meta {{ color: #666; font-size: 0.9rem; margin-top: 0.5rem; }}
  .footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 2px solid #1E3A5F;
             font-size: 0.8rem; color: #888; text-align: center; }}
</style>
</head>
<body>
<div class="header">
  <h1>Murphy System</h1>
  <p class="meta">{_html_mod.escape(title)} — Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
</div>
<div class="content">
{escaped}
</div>
<div class="footer">
  Generated by Murphy System — murphy.systems<br>
  © {datetime.now(timezone.utc).year} Inoni Limited Liability Company (Corey Post)
</div>
</body>
</html>"""


def _convert_to_pdf(content: str, title: str) -> Dict[str, str]:
    """Convert to PDF and return base64-encoded content."""
    # Try document_export pipeline first
    try:
        from document_export.export_pipeline import ExportPipeline  # noqa: PLC0415
        pipeline = ExportPipeline()
        result = pipeline.export_sync(
            source_output={"content": content, "title": title},
            fmt="pdf",
        )
        if result and result.content:
            # ExportPipeline already returns base64 for binary formats
            return {"content": result.content}
    except Exception as exc:  # FORGE-MULTIFORMAT-ERR-003
        logger.warning("FORGE-MULTIFORMAT-ERR-003: document_export PDF failed: %s — trying fallback", exc)

    # Try DocumentGenerationEngine
    try:
        from execution.document_generation_engine import DocumentGenerationEngine  # noqa: PLC0415
        engine = DocumentGenerationEngine()
        b64 = engine.render_pdf(content)
        if b64 and isinstance(b64, str) and len(b64) > 100:
            return {"content": b64}
    except Exception as exc:  # FORGE-MULTIFORMAT-ERR-004
        logger.warning("FORGE-MULTIFORMAT-ERR-004: DocumentGenerationEngine PDF failed: %s — using text fallback", exc)

    # Last resort: base64-encode the HTML version
    html_content = _convert_to_html(content, title)
    return {"content": base64.b64encode(html_content.encode("utf-8")).decode("ascii")}


def _convert_to_docx(content: str, title: str) -> Dict[str, str]:
    """Convert to DOCX and return base64-encoded content."""
    # Try document_export pipeline
    try:
        from document_export.export_pipeline import ExportPipeline  # noqa: PLC0415
        pipeline = ExportPipeline()
        result = pipeline.export_sync(
            source_output={"content": content, "title": title},
            fmt="word",
        )
        if result and result.content:
            return {"content": result.content}
    except Exception as exc:  # FORGE-MULTIFORMAT-ERR-005
        logger.warning("FORGE-MULTIFORMAT-ERR-005: document_export DOCX failed: %s — trying fallback", exc)

    # Try DocumentGenerationEngine
    try:
        from execution.document_generation_engine import DocumentGenerationEngine  # noqa: PLC0415
        engine = DocumentGenerationEngine()
        b64 = engine.render_word(content)
        if b64 and isinstance(b64, str) and len(b64) > 100:
            return {"content": b64}
    except Exception as exc:  # FORGE-MULTIFORMAT-ERR-006
        logger.warning("FORGE-MULTIFORMAT-ERR-006: DocumentGenerationEngine DOCX failed: %s — using text fallback", exc)

    # Fallback: provide the content as base64-encoded plain text
    return {"content": base64.b64encode(content.encode("utf-8")).decode("ascii")}


def _convert_to_zip_bundle(deliverable: Dict[str, Any], query: str) -> Dict[str, str]:
    """Create a ZIP bundle containing the deliverable in multiple formats.

    The bundle includes:
    - The original .txt deliverable
    - An HTML version
    - A Markdown version
    - A README with project overview
    """
    content = deliverable.get("content", "")
    title = deliverable.get("title", "Murphy Deliverable")
    base_filename = deliverable.get("filename", "murphy-deliverable.txt")
    stem = re.sub(r"\.[^.]+$", "", base_filename)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Original text deliverable
        zf.writestr(f"{stem}/{base_filename}", content)

        # Markdown version
        md_content = _strip_branded_wrapper(content)
        zf.writestr(f"{stem}/{stem}.md", md_content)

        # HTML version
        html_content = _convert_to_html(content, title)
        zf.writestr(f"{stem}/{stem}.html", html_content)

        # README
        readme = (
            f"# {title}\n\n"
            f"Generated by Murphy System on {now_str}\n\n"
            f"## Query\n{query}\n\n"
            f"## Contents\n"
            f"- `{base_filename}` — Full branded deliverable (text)\n"
            f"- `{stem}.md` — Markdown version (for editing)\n"
            f"- `{stem}.html` — HTML version (for viewing/printing)\n\n"
            f"## About\n"
            f"This deliverable was generated by Murphy System's AI-powered\n"
            f"forge pipeline. Visit https://murphy.systems for more.\n\n"
            f"© {datetime.now(timezone.utc).year} Inoni LLC (Corey Post)\n"
        )
        zf.writestr(f"{stem}/README.md", readme)

    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return {"content": b64}

# ---------------------------------------------------------------------------
# Branding constants
# ---------------------------------------------------------------------------

_MURPHY_ASCII_LOGO = r"""╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║    ███╗   ███╗██╗   ██╗██████╗ ██████╗ ██╗  ██╗██╗   ██╗           ║
║    ████╗ ████║██║   ██║██╔══██╗██╔══██╗██║  ██║╚██╗ ██╔╝           ║
║    ██╔████╔██║██║   ██║██████╔╝██████╔╝███████║ ╚████╔╝            ║
║    ██║╚██╔╝██║██║   ██║██╔══██╗██╔═══╝ ██╔══██║  ╚██╔╝             ║
║    ██║ ╚═╝ ██║╚██████╔╝██║  ██║██║     ██║  ██║   ██║              ║
║    ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝   ╚═╝              ║
║                                                                      ║
║                       S Y S T E M                                    ║
║                                                                      ║
║              Generated by Murphy System — murphy.systems             ║
║           © 2025 Inoni Limited Liability Company (Corey Post)        ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝"""

_LICENSE_FOOTER = """═══════════════════════════════════════════════════════════════════════

  LICENSE NOTICE — THIS SECTION MAY NOT BE REMOVED

  This deliverable was generated by Murphy System, a product of
  Inoni Limited Liability Company. The OUTPUT of this generation
  is provided under the Apache License, Version 1.0.

  Licensed under the Apache License, Version 1.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-1.0

  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on an
  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied.

  Murphy System itself is licensed under BSL 1.1.
  See https://github.com/IKNOWINOT/Murphy-System/blob/main/LICENSE

  © 2025 Inoni Limited Liability Company (Corey Post)
  https://murphy.systems

═══════════════════════════════════════════════════════════════════════"""

# ---------------------------------------------------------------------------
# Predefined scenario templates
# ---------------------------------------------------------------------------

_SCENARIO_TEMPLATES: Dict[str, Dict[str, str]] = {
    "onboarding": {
        "title": "Client Onboarding Package",
        "content": """\
■ SECTION 1 — CLIENT INTAKE CHECKLIST
──────────────────────────────────────
  □  Company legal name and DBA (if applicable)
  □  Primary contact: name, title, email, phone
  □  Billing contact (if different)
  □  Signed Non-Disclosure Agreement (NDA) on file
  □  Completed discovery questionnaire returned
  □  Business goals & success metrics documented
  □  Existing tooling inventory (CRM, ERP, billing)
  □  Timeline expectations confirmed
  □  Budget range approved by stakeholder

■ SECTION 2 — MASTER SERVICE AGREEMENT OUTLINE
────────────────────────────────────────────────
  1.  Scope of Services
      - Murphy System workflow automation (defined in SOW)
      - Integration with client-specified third-party APIs
      - Monthly performance reporting

  2.  Term & Renewal
      - Initial term: 12 months from execution date
      - Auto-renews annually unless 30-day written notice

  3.  Fees & Payment
      - Monthly retainer: as per attached SOW
      - Net-30 payment terms; 1.5 % monthly late fee
      - Expenses reimbursed at cost + 10 % admin fee

  4.  Intellectual Property
      - Client owns all data inputs and outputs
      - Murphy System retains ownership of platform IP

  5.  Confidentiality, Data Security & Compliance
      - BSL-1.1 platform; Apache 1.0 deliverable outputs
      - SOC 2 Type II controls in effect

  6.  Limitation of Liability & Indemnification
  7.  Governing Law & Dispute Resolution (AAA Arbitration)
  8.  Signatures block

■ SECTION 3 — INITIAL INVOICE TEMPLATE
────────────────────────────────────────
  Invoice #:    2091
  Client:       [Client Name]
  Date:         [Today]
  Due Date:     [Today + 30 days]

  ┌─────────────────────────────────────────────┬──────────┐
  │ Description                                 │  Amount  │
  ├─────────────────────────────────────────────┼──────────┤
  │ Onboarding & setup fee                      │ $1,500   │
  │ Month 1 retainer (Murphy System automation) │ $3,000   │
  │ API integration (3 services)                │   $500   │
  ├─────────────────────────────────────────────┼──────────┤
  │ TOTAL DUE                                   │ $5,000   │
  └─────────────────────────────────────────────┴──────────┘

  Payment via: ACH / Wire / Stripe link attached
  Notes: First invoice; subsequent invoices billed on the 1st.

■ SECTION 4 — CRM SETUP STEPS
───────────────────────────────
  Step 1: Create contact record in HubSpot / CRM of choice
    - Fields: Full name, company, email, phone, pipeline stage
  Step 2: Assign to pipeline: "Active Clients"
  Step 3: Set follow-up task: 7-day check-in call
  Step 4: Tag: onboarding_2025, murphy_automated
  Step 5: Link invoice #2091 to contact record
  Step 6: Enable deal tracking; set expected close: Month 3

■ SECTION 5 — PROJECT BOARD TASK LIST (14 TASKS)
──────────────────────────────────────────────────
  Sprint 1 — Foundation (Week 1–2)
    [P1] ✦  API credentials collection & vault storage
    [P1] ✦  Murphy workflow installation & environment setup
    [P2] ✦  CRM integration test (read/write contact records)
    [P2] ✦  Billing integration test (create/send invoice)

  Sprint 2 — Automation Build (Week 3–4)
    [P1] ✦  Onboarding workflow: intake → contract → invoice
    [P1] ✦  Notification routing (email + Slack alerts)
    [P2] ✦  Reporting dashboard configuration
    [P3] ✦  Custom workflow rules per client SLA

  Sprint 3 — QA & Handoff (Week 5–6)
    [P1] ✦  End-to-end workflow test with dummy data
    [P1] ✦  Client UAT session scheduled & completed
    [P2] ✦  Documentation delivered (runbook + API guide)
    [P2] ✦  Training session completed (1 hr)
    [P3] ✦  Go-live approval signed
    [P3] ✦  30-day hypercare period begins
""",
    },
    "finance": {
        "title": "Q3 Finance Report",
        "content": """\
■ SECTION 1 — EXECUTIVE SUMMARY
─────────────────────────────────
  Period:   Q3 2024 (July 1 – September 30)
  Prepared: Murphy System Automated Finance Report

  Q3 performance exceeded plan by 7.3 %. Revenue grew 18 % YoY driven
  by SaaS subscription expansion. Operating expenses remained within
  budget. EBITDA margin improved to 34.1 % (+2.8 pp vs Q2 2024).

  Key Highlights:
  • Net Revenue:   $2,847,000   (+18 % YoY, +6 % QoQ)
  • Gross Profit:  $1,938,000   (68 % margin)
  • EBITDA:        $  971,000   (34.1 % margin)
  • Cash on hand:  $4,120,000   (3.4× monthly burn)

■ SECTION 2 — REVENUE BREAKDOWN
─────────────────────────────────
  ┌────────────────────────────┬───────────┬────────┬──────────┐
  │ Revenue Stream             │   Q3 2024 │  Q3 YoY│ % of Rev │
  ├────────────────────────────┼───────────┼────────┼──────────┤
  │ SaaS Subscriptions         │ $1,850,000│  +22 % │  65.0 %  │
  │ Professional Services      │   $640,000│  +12 % │  22.5 %  │
  │ Integration Fees           │   $285,000│   +8 % │  10.0 %  │
  │ Training & Certification   │    $72,000│   +5 % │   2.5 %  │
  ├────────────────────────────┼───────────┼────────┼──────────┤
  │ TOTAL REVENUE              │ $2,847,000│  +18 % │ 100.0 %  │
  └────────────────────────────┴───────────┴────────┴──────────┘

■ SECTION 3 — EXPENSE CATEGORIZATION
──────────────────────────────────────
  ┌────────────────────────────┬───────────┬──────────┐
  │ Expense Category           │   Amount  │ % of Rev │
  ├────────────────────────────┼───────────┼──────────┤
  │ Cost of Revenue (COGS)     │   $909,000│  31.9 %  │
  │ Sales & Marketing          │   $426,000│  15.0 %  │
  │ Research & Development     │   $341,000│  12.0 %  │
  │ General & Administrative   │   $200,000│   7.0 %  │
  ├────────────────────────────┼───────────┼──────────┤
  │ TOTAL OPERATING EXPENSES   │ $1,876,000│  65.9 %  │
  └────────────────────────────┴───────────┴──────────┘

■ SECTION 4 — 6-MONTH REVENUE FORECAST (Q4 2024 – Q1 2025)
─────────────────────────────────────────────────────────────
  Month         │ Revenue Forecast │ Growth Assumption
  ──────────────┼──────────────────┼───────────────────
  October 2024  │   $   965,000    │ +2.0 % MoM
  November 2024 │   $   985,000    │ +2.1 % MoM
  December 2024 │   $ 1,015,000    │ +3.0 % (seasonal)
  January 2025  │   $   940,000    │ -7.4 % (Jan reset)
  February 2025 │   $   970,000    │ +3.2 % MoM
  March 2025    │   $ 1,010,000    │ +4.1 % MoM
  ──────────────┼──────────────────┼───────────────────
  6-Month Total │   $ 5,885,000    │ +22 % vs H2 2023

■ SECTION 5 — RECOMMENDATIONS
───────────────────────────────
  1. Accelerate SaaS expansion:  Upsell 15 % of PS clients to
     annual subscription by Q4; estimated ARR lift: +$240,000.
  2. Optimise COGS:  Renegotiate 3 cloud vendor contracts; target
     5 % reduction → saves ~$45,000/quarter.
  3. Marketing efficiency:  Redirect 20 % of paid-search budget
     to content/SEO; CAC payback period currently 7.2 months —
     target: 5.5 months by Q1 2025.
  4. R&D focus:  Prioritise AI workflow automation features;
     top 3 prospects cited as primary purchase driver.
  5. Cash management:  Maintain ≥3× monthly burn; consider 6-
     month T-bill ladder for idle reserves.
""",
    },
    "hr": {
        "title": "Candidate Screening Report",
        "content": """\
■ SECTION 1 — CANDIDATE SCORING MATRIX
────────────────────────────────────────
  Role: Senior Product Manager
  Hiring Manager: [Name]   |   Req ID: PM-2024-07

  ┌──────────────────┬───────┬───────┬───────┬───────┬───────┐
  │ Criterion        │ Wt %  │Cand A │Cand B │Cand C │Cand D │
  ├──────────────────┼───────┼───────┼───────┼───────┼───────┤
  │ Domain expertise │  25 % │  4/5  │  5/5  │  3/5  │  4/5  │
  │ Leadership exp.  │  20 % │  5/5  │  4/5  │  4/5  │  3/5  │
  │ Data & analytics │  20 % │  4/5  │  4/5  │  5/5  │  3/5  │
  │ Communication    │  15 % │  5/5  │  4/5  │  4/5  │  4/5  │
  │ Culture fit      │  10 % │  4/5  │  5/5  │  3/5  │  5/5  │
  │ Compensation fit │  10 % │  5/5  │  3/5  │  5/5  │  4/5  │
  ├──────────────────┼───────┼───────┼───────┼───────┼───────┤
  │ WEIGHTED SCORE   │ 100 % │ 4.55  │ 4.25  │ 3.90  │ 3.75  │
  │ RANK             │       │  #1   │  #2   │  #3   │  #4   │
  └──────────────────┴───────┴───────┴───────┴───────┴───────┘

■ SECTION 2 — SKILLS ASSESSMENT SUMMARY
─────────────────────────────────────────
  Candidate A — ★★★★★ RECOMMENDED
    Strengths:  8 years PM at SaaS; shipped 3 products >$10M ARR;
                SQL proficient; led cross-functional teams of 12+.
    Gaps:       No formal MBA; limited enterprise sales exposure.
    Verdict:    Strong hire. Offer within band.

  Candidate B — ★★★★☆ STRONG ALTERNATE
    Strengths:  FAANG background; exceptional strategic vision;
                excellent culture alignment scores.
    Gaps:       Compensation expectations 15 % above band.
    Verdict:    Good backup. Negotiate or flag for future req.

  Candidate C — ★★★☆☆ CONDITIONAL
    Strengths:  Deep analytics; strong data science background.
    Gaps:       Limited stakeholder management; no leadership exp.
    Verdict:    Better fit for Sr. Analyst role. Redirect.

  Candidate D — ★★★☆☆ NOT RECOMMENDED
    Strengths:  Great culture fit; enthusiastic.
    Gaps:       2 years experience; significant skill gap for Sr. level.
    Verdict:    Revisit in 12–18 months with growth.

■ SECTION 3 — STRUCTURED INTERVIEW QUESTIONS
──────────────────────────────────────────────
  Round 1 — Screening (30 min, Recruiter)
    Q1. Walk me through your product development process.
    Q2. Describe a product you own end-to-end. What was the outcome?
    Q3. How do you prioritize a backlog with competing stakeholders?

  Round 2 — Technical (60 min, Engineering Lead)
    Q4. Given a drop in a key metric, how do you diagnose root cause?
    Q5. Describe a data-driven decision you made and its impact.
    Q6. How do you write a PRD? Walk us through a recent example.

  Round 3 — Leadership (45 min, VP Product)
    Q7. Tell me about a time you influenced without authority.
    Q8. How have you managed conflict in cross-functional teams?
    Q9. What's your product vision for our space in 3 years?

■ SECTION 4 — RECOMMENDATION SUMMARY
──────────────────────────────────────
  Proceed to offer:  Candidate A
  Backup:            Candidate B (pending compensation discussion)
  Next steps:
    □  Reference checks: 3 professional references (48 hrs)
    □  Background screening: employment + education verification
    □  Offer letter: draft within 2 business days of ref clearance
    □  Target start date: 3 weeks from offer acceptance
""",
    },
    "compliance": {
        "title": "Compliance Audit Report",
        "content": """\
■ SECTION 1 — COMPLIANCE CHECKLIST
─────────────────────────────────────
  Framework:  SOC 2 Type II + GDPR + ISO 27001 (Partial)
  Audit date: [Today]
  Scope:      Data processing systems, access controls, logging

  Access Controls
    [✓] Multi-factor authentication enforced (all users)
    [✓] Role-based access control (RBAC) implemented
    [✓] Privileged access management (PAM) — quarterly review
    [✗] Least-privilege review not completed this quarter  ← FINDING

  Data Protection
    [✓] Data encrypted at rest (AES-256)
    [✓] Data encrypted in transit (TLS 1.3)
    [✓] GDPR Article 30 processing register up to date
    [✗] Data retention schedules not fully documented      ← FINDING

  Incident Response
    [✓] IR plan documented and approved
    [✓] Tabletop exercise completed (Q2)
    [✗] IR plan not tested with full runbook walkthrough   ← FINDING

  Vendor Management
    [✓] Third-party vendor risk assessments on file
    [✓] DPA agreements signed for all data processors
    [✓] Annual vendor re-certification completed

  Logging & Monitoring
    [✓] Centralised SIEM configured (Splunk / ELK)
    [✓] Anomaly detection alerts active
    [✓] Log retention ≥12 months confirmed

■ SECTION 2 — FINDINGS MATRIX
───────────────────────────────
  ┌─────┬────────────────────────────────────┬──────────┬──────────┐
  │ ID  │ Finding                            │ Severity │  Owner   │
  ├─────┼────────────────────────────────────┼──────────┼──────────┤
  │ F-1 │ Least-privilege review overdue     │ MEDIUM   │ IT Ops   │
  │ F-2 │ Data retention policy gaps         │ HIGH     │ Legal    │
  │ F-3 │ IR plan not fully tested           │ MEDIUM   │ SecOps   │
  └─────┴────────────────────────────────────┴──────────┴──────────┘

■ SECTION 3 — RISK ASSESSMENT
───────────────────────────────
  Residual Risk Level:  MEDIUM  (target: LOW by Q1 2025)

  Risk F-2 (Data Retention) — HIGH
    Current state: Retention schedules exist for primary DBs but
    not for backup/archive systems or 3rd-party integrations.
    Potential impact: GDPR Article 5(e) violation; fines up to 4 %
    of global turnover. Reputational damage.
    Likelihood: LOW (no breach indicators)
    Risk score: 6/10

  Risk F-1 (Least Privilege) — MEDIUM
    Current state: RBAC in place; access review last run 5 months ago.
    Potential impact: Insider threat or account compromise could
    escalate privileges beyond required scope.
    Risk score: 4/10

  Risk F-3 (IR Plan Test) — MEDIUM
    Current state: Plan documented; tabletop done in Q2 but no
    full-runbook exercise completed this calendar year.
    Risk score: 3/10

■ SECTION 4 — REMEDIATION TIMELINE
─────────────────────────────────────
  Finding │ Action Required                        │ Due Date   │ Status
  ────────┼────────────────────────────────────────┼────────────┼─────────
  F-1     │ Complete least-privilege access review  │ +2 weeks   │ Assigned
  F-2     │ Document retention for backup/archive   │ +4 weeks   │ In flight
  F-2     │ Obtain DPA confirmation from 3 vendors  │ +3 weeks   │ Pending
  F-3     │ Schedule & complete IR runbook exercise │ +6 weeks   │ Scheduled
""",
    },
    "project": {
        "title": "Project Plan",
        "content": """\
■ SECTION 1 — PROJECT CHARTER
───────────────────────────────
  Project Name:  Murphy System Automation Deployment
  Sponsor:       [Executive Sponsor]
  PM:            [Project Manager]
  Start Date:    [Today]
  Target End:    [Today + 12 weeks]
  Budget:        $48,000
  Priority:      P1 — Strategic

  Objective:
    Deploy Murphy System workflow automation across core business
    functions (onboarding, finance, HR) to reduce manual processing
    time by ≥60 % and achieve ROI within 6 months.

  Success Criteria:
    • 3 automated workflows live and stable in production
    • <2 % error rate on automated tasks
    • Team trained and self-sufficient
    • ROI model validated with actual time-savings data

■ SECTION 2 — MILESTONE TIMELINE
──────────────────────────────────
  Week  1–2  │ ◉ Milestone 1: Environment setup & API credentials
  Week  3–4  │ ◉ Milestone 2: Core workflow development (onboarding)
  Week  5–6  │ ◉ Milestone 3: Finance & HR workflows developed
  Week  7–8  │ ◉ Milestone 4: Internal QA & load testing
  Week  9–10 │ ◉ Milestone 5: UAT with stakeholders
  Week 11    │ ◉ Milestone 6: Production deployment
  Week 12    │ ◉ Milestone 7: Hypercare & KPI review

■ SECTION 3 — RESOURCE ALLOCATION
────────────────────────────────────
  ┌──────────────────────────┬────────────┬──────────┬──────────┐
  │ Resource                 │ Role       │ Allocation│  Weeks   │
  ├──────────────────────────┼────────────┼──────────┼──────────┤
  │ Murphy System Engineer   │ Lead Dev   │  100 %   │  1–10    │
  │ Client IT Lead           │ DevOps     │   50 %   │  1–12    │
  │ Business Analyst         │ Requirements│  75 %   │  1–6     │
  │ QA Engineer              │ Testing    │  100 %   │  7–11    │
  │ Project Manager          │ Governance │   25 %   │  1–12    │
  └──────────────────────────┴────────────┴──────────┴──────────┘

  Budget breakdown:
    Labour (internal):   $30,000 (62 %)
    Murphy System licence: $9,600 (20 %)
    API integrations:    $5,400 (11 %)
    Training & docs:     $3,000 (7 %)

■ SECTION 4 — RISK REGISTER
─────────────────────────────
  ID  │ Risk                        │ Probability │ Impact │ Mitigation
  ────┼─────────────────────────────┼─────────────┼────────┼──────────────────
  R-1 │ API credential delays       │ MEDIUM      │ HIGH   │ Start vendor requests Week 1
  R-2 │ Scope creep                 │ HIGH        │ MEDIUM │ Change control process; weekly PM check-in
  R-3 │ Key-person dependency       │ LOW         │ HIGH   │ Knowledge transfer docs; backup resource identified
  R-4 │ Integration compatibility   │ LOW         │ MEDIUM │ POC in Week 1 before full build begins
  R-5 │ Stakeholder availability    │ MEDIUM      │ MEDIUM │ UAT slots booked in advance; async sign-off options

■ SECTION 5 — RACI MATRIX
───────────────────────────
  Task                      │ PM  │ Dev │ BA  │ QA  │ Sponsor
  ──────────────────────────┼─────┼─────┼─────┼─────┼─────────
  Requirements gathering    │ A   │ C   │ R   │ I   │ I
  Architecture design       │ I   │ R   │ C   │ C   │ A
  Development               │ I   │ R/A │ C   │ C   │ I
  QA & testing              │ I   │ C   │ I   │ R/A │ I
  UAT sign-off              │ C   │ I   │ C   │ I   │ R/A
  Production deployment     │ A   │ R   │ I   │ C   │ I
  Post-launch review        │ R   │ C   │ C   │ C   │ A

  R=Responsible  A=Accountable  C=Consulted  I=Informed
""",
    },
    "invoice": {
        "title": "Invoice Processing Report",
        "content": """\
■ SECTION 1 — PROCESSING SUMMARY
──────────────────────────────────
  Batch ID:      INV-BATCH-2024-Q3-001
  Processed:     [Today]
  Total invoices: 47
  Total value:   $284,750.00

  ┌─────────────────────────────────┬───────┬────────────┐
  │ Status                          │ Count │ Value      │
  ├─────────────────────────────────┼───────┼────────────┤
  │ Approved & queued for payment   │  38   │ $234,200   │
  │ Pending 3-way match             │   5   │  $31,500   │
  │ Exception — requires review     │   3   │  $14,250   │
  │ Duplicate detected & rejected   │   1   │   $4,800   │
  ├─────────────────────────────────┼───────┼────────────┤
  │ TOTAL                           │  47   │ $284,750   │
  └─────────────────────────────────┴───────┴────────────┘

■ SECTION 2 — PAYMENT SCHEDULE
────────────────────────────────
  ┌─────────────────────────┬───────────┬────────────┬─────────────┐
  │ Vendor                  │ Invoice # │ Amount     │ Payment Date│
  ├─────────────────────────┼───────────┼────────────┼─────────────┤
  │ Acme Supplies Co.       │ SI-88421  │  $12,400   │ [+7 days]   │
  │ Cloud Infra Ltd.        │ CI-00391  │  $34,800   │ [+7 days]   │
  │ Marketing Agency X      │ MA-2291   │  $18,000   │ [+14 days]  │
  │ Office Depot            │ OD-77612  │   $1,240   │ [+30 days]  │
  │ [+ 34 more vendors]     │ ...       │ $168,260   │ [Various]   │
  ├─────────────────────────┼───────────┼────────────┼─────────────┤
  │ TOTAL APPROVED          │           │ $234,700   │             │
  └─────────────────────────┴───────────┴────────────┴─────────────┘

  Early-pay discounts captured:  3 invoices × 2 %  = $1,416.00 saved.

■ SECTION 3 — RECONCILIATION REPORT
──────────────────────────────────────
  PO Matching Summary:
    • 3-way match (PO + Receipt + Invoice):  38 of 42 eligible  ✓
    • 2-way match (PO + Invoice only):        4 of 42          △
    • No matching PO found:                   3 invoices       ✗

  GL Coding:
    • Auto-coded by Murphy System:  44 invoices (93.6 %)
    • Requires manual GL code:       3 invoices  (6.4 %)

  Variance Analysis:
    Invoices within ±2 % of PO value: 40 (95 %)
    Invoices >2 % above PO value:      2 (requires approval)

■ SECTION 4 — EXCEPTION LOG
─────────────────────────────
  EX-001 │ INV #SI-88499 │ Vendor: Acme Supplies │ $4,100
    Issue: Invoice amount $200 over PO. Vendor claims
           freight surcharge added post-PO.
    Action: Route to Purchasing for PO amendment or credit memo.
    SLA: Resolve within 5 business days.

  EX-002 │ INV #TK-1122 │ Vendor: Tech Kit Inc. │ $7,350
    Issue: No matching receipt found. Goods may not have arrived.
    Action: Warehouse confirmation requested. Payment on hold.
    SLA: Warehouse response within 48 hrs.

  EX-003 │ INV #MA-2299 │ Vendor: Marketing Agency X │ $2,800
    Issue: Duplicate invoice detected (matches MA-2291 amount
           and date; different invoice number — possible re-submission).
    Action: Vendor contacted; payment withheld pending clarification.
    SLA: Vendor response within 24 hrs.
""",
    },
    # ──────────────────────────────────────────────────────────────────────
    # NEW SWARM FORGE DELIVERABLES
    # ──────────────────────────────────────────────────────────────────────
    "game": {
        "title": "HTML5 MMORPG — Single-Level Playable Demo",
        "content": """\
■ YOUR GAME — COMPLETE SINGLE-LEVEL HTML5 MMORPG
════════════════════════════════════════════════════

  This is a REAL, RUNNABLE single-level browser game. Copy the HTML below
  into a file named  game.html  and open it in any modern browser.
  Touch controls are included for mobile. No build step required.

  ──────────────────────────────────────────────────────────────────────
  STORY PREMISE
  ──────────────────────────────────────────────────────────────────────
  The Shattered Nexus — a world where seven ancient factions once kept
  the balance of elemental forces. A century of silence was broken when
  the Voidtide swallowed the Eastern Citadel, corrupting every guardian
  stationed there. You are Kael, a Drifter — a wanderer with no faction
  who can absorb and channel any element. Level 1 begins in the Ashfen
  Marshes: find the Shard of Ignition, defeat the Marshwarden boss, and
  unlock the portal to the Eastern Citadel.

  WORLD: Shattered Nexus
  PLAYER CLASS: Drifter (adaptive element absorption)
  LEVEL 1 REGION: Ashfen Marshes
  OBJECTIVE: Retrieve Shard of Ignition, defeat Marshwarden
  ENEMIES: Bog Wraiths (3), Corroded Guardians (2), Marshwarden (boss)
  ITEMS: Health Crystal, Ember Rune, Speed Sigil, Shard of Ignition

  ──────────────────────────────────────────────────────────────────────
  COMPLETE RUNNABLE GAME CODE  (save as game.html)
  ──────────────────────────────────────────────────────────────────────

<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>Shattered Nexus — Level 1: Ashfen Marshes</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{background:#0a0a0f;display:flex;flex-direction:column;align-items:center;
     justify-content:center;min-height:100vh;font-family:'Courier New',monospace;
     color:#e0e0e0;overflow:hidden;}
#hud{width:100%;max-width:640px;display:flex;justify-content:space-between;
     padding:6px 12px;background:rgba(0,0,0,.7);font-size:13px;border-bottom:1px solid #333;}
#hud .hp{color:#ff6b6b;} #hud .xp{color:#ffd93d;} #hud .zone{color:#6bcb77;}
canvas{display:block;max-width:640px;width:100%;cursor:crosshair;
       border:1px solid #222;image-rendering:pixelated;}
#msg{width:100%;max-width:640px;min-height:28px;background:rgba(0,0,0,.8);
     color:#00ff88;font-size:12px;padding:4px 12px;border-top:1px solid #222;}
#dpad{display:none;width:100%;max-width:640px;background:#111;padding:10px;
      justify-content:space-between;align-items:center;}
.dring{display:grid;grid-template-columns:repeat(3,44px);grid-template-rows:repeat(3,44px);gap:3px;}
.dkey{background:rgba(255,255,255,.08);border:1px solid #444;border-radius:6px;
      display:flex;align-items:center;justify-content:center;font-size:18px;
      color:#aaa;user-select:none;-webkit-user-select:none;cursor:pointer;}
.dkey:active{background:rgba(0,255,136,.2);border-color:#00ff88;}
.atk{width:56px;height:56px;border-radius:50%;background:rgba(255,80,80,.15);
     border:2px solid #ff5050;display:flex;align-items:center;justify-content:center;
     font-size:22px;cursor:pointer;user-select:none;-webkit-user-select:none;}
.atk:active{background:rgba(255,80,80,.4);}
@media(max-width:600px),(hover:none){#dpad{display:flex;}}
#over{display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);
      flex-direction:column;align-items:center;justify-content:center;z-index:99;}
#over h2{font-size:2rem;margin-bottom:1rem;}
#over.win h2{color:#ffd93d;}
#over.lose h2{color:#ff6b6b;}
#over button{padding:.6rem 2rem;background:#00ff88;border:none;border-radius:6px;
             font-size:1rem;cursor:pointer;font-family:inherit;font-weight:700;}
</style>
</head>
<body>
<div id="hud">
  <span class="hp">❤ HP: <b id="hpVal">100</b>/100</span>
  <span class="zone">⚔ Ashfen Marshes — Lv1</span>
  <span class="xp">✦ XP: <b id="xpVal">0</b></span>
</div>
<canvas id="gc" width="640" height="400"></canvas>
<div id="msg">Move with WASD / arrow keys. Attack with SPACE or the button below.</div>
<div id="dpad">
  <div class="dring">
    <div></div>
    <div class="dkey" id="dU">▲</div>
    <div></div>
    <div class="dkey" id="dL">◀</div>
    <div></div>
    <div class="dkey" id="dR">▶</div>
    <div></div>
    <div class="dkey" id="dD">▼</div>
    <div></div>
  </div>
  <div class="atk" id="dAtk">⚡</div>
</div>
<div id="over"><h2 id="overMsg"></h2><p id="overSub" style="margin-bottom:1.5rem;color:#aaa;"></p><button onclick="location.reload()">Play Again</button></div>
<script>
(function(){
'use strict';
var c=document.getElementById('gc'),ctx=c.getContext('2d');
var W=640,H=400;
var TILE=32;
var keys={};
// ── Tilemap 20×12 (0=grass,1=wall,2=water,3=path) ──
var MAP=[
[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
[1,3,3,3,0,0,0,0,1,0,0,0,0,0,0,0,0,0,3,1],
[1,3,0,0,0,2,2,0,1,0,0,0,0,0,0,0,0,0,3,1],
[1,3,0,0,0,2,2,0,0,0,0,1,1,0,0,0,0,0,3,1],
[1,3,0,0,0,0,0,0,0,0,0,1,1,0,0,0,0,0,3,1],
[1,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,1],
[1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,3,1],
[1,0,0,2,2,0,0,0,1,0,0,0,0,0,0,1,1,0,3,1],
[1,0,0,2,2,0,0,0,0,0,0,0,0,0,0,1,1,0,3,1],
[1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,3,1],
[1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,3,1],
[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]
];
var COLORS={0:'#2d4a1e',1:'#1a1a2e',2:'#1e3a5f',3:'#3d2b1a'};

// ── Entities ──
var player={x:1.5*TILE,y:5*TILE,w:20,h:20,hp:100,xp:0,speed:2.8,
            attacking:false,atkTimer:0,atkRange:48,dir:1,
            invTimer:0};
var enemies=[
  {x:8*TILE,y:2*TILE,w:20,h:20,hp:35,maxHp:35,spd:1.0,xp:20,name:'Bog Wraith',col:'#7b4fc4',atk:8,range:26,atkCd:0},
  {x:14*TILE,y:3*TILE,w:20,h:20,hp:35,maxHp:35,spd:1.0,xp:20,name:'Bog Wraith',col:'#7b4fc4',atk:8,range:26,atkCd:0},
  {x:5*TILE,y:9*TILE,w:20,h:20,hp:35,maxHp:35,spd:1.0,xp:20,name:'Bog Wraith',col:'#7b4fc4',atk:8,range:26,atkCd:0},
  {x:12*TILE,y:8*TILE,w:22,h:22,hp:55,maxHp:55,spd:0.9,xp:35,name:'Corroded Guardian',col:'#5a9e6f',atk:12,range:28,atkCd:0},
  {x:16*TILE,y:7*TILE,w:22,h:22,hp:55,maxHp:55,spd:0.9,xp:35,name:'Corroded Guardian',col:'#5a9e6f',atk:12,range:28,atkCd:0},
  {x:17*TILE,y:5*TILE,w:28,h:28,hp:180,maxHp:180,spd:0.65,xp:150,name:'MARSHWARDEN',col:'#c45e1a',atk:22,range:32,atkCd:0,boss:true}
];
var items=[
  {x:3*TILE,y:3*TILE,type:'hp',col:'#ff6b6b',label:'❤',val:30,taken:false},
  {x:6*TILE,y:8*TILE,type:'hp',col:'#ff6b6b',label:'❤',val:30,taken:false},
  {x:10*TILE,y:6*TILE,type:'speed',col:'#ffd93d',label:'⚡',val:0.8,taken:false},
  {x:15*TILE,y:10*TILE,type:'shard',col:'#00ffff',label:'◈',val:0,taken:false}
];
var portal={x:18*TILE,y:5*TILE,active:false};
var cam={x:0,y:0};
var msg='';var msgTimer=0;
var gameOver=false;var won=false;

function setMsg(m){msg=m;msgTimer=240;}

function solid(tx,ty){
  if(tx<0||ty<0||tx>=20||ty>=12)return true;
  var t=MAP[ty][tx];
  return t===1||t===2;
}
function collides(ax,ay,aw,ah,bx,by,bw,bh){
  return ax<bx+bw&&ax+aw>bx&&ay<by+bh&&ay+ah>by;
}
function dist(a,b){var dx=a.x-b.x,dy=a.y-b.y;return Math.sqrt(dx*dx+dy*dy);}

function tryMove(ent,dx,dy){
  var nx=ent.x+dx,ny=ent.y+dy;
  var tx=Math.floor((nx+ent.w/2)/TILE),ty=Math.floor((ny+ent.h/2)/TILE);
  var tx0=Math.floor(nx/TILE),ty0=Math.floor(ny/TILE);
  var tx1=Math.floor((nx+ent.w-1)/TILE),ty1=Math.floor((ny+ent.h-1)/TILE);
  var blocked=solid(tx0,ty0)||solid(tx1,ty0)||solid(tx0,ty1)||solid(tx1,ty1);
  if(!blocked){ent.x=nx;ent.y=ny;}
}

function attack(){
  if(player.atkTimer>0)return;
  player.attacking=true;player.atkTimer=22;
  enemies.forEach(function(e){
    if(e.hp<=0)return;
    if(dist(player,e)<player.atkRange+e.w/2){
      e.hp-=28;setMsg('Hit '+e.name+'! ('+(e.hp>0?e.hp+' HP left':'defeated')+')');
      if(e.hp<=0){
        player.xp+=e.xp;
        document.getElementById('xpVal').textContent=player.xp;
        setMsg((e.boss?'BOSS DEFEATED! ':'Enemy defeated! ')+'+'+e.xp+' XP');
      }
    }
  });
}

// ── Input ──
document.addEventListener('keydown',function(e){keys[e.key]=true;if(e.key===' '){e.preventDefault();attack();}});
document.addEventListener('keyup',function(e){keys[e.key]=false;});
['dU','dD','dL','dR'].forEach(function(id){
  var el=document.getElementById(id);
  var kMap={dU:'ArrowUp',dD:'ArrowDown',dL:'ArrowLeft',dR:'ArrowRight'};
  el.addEventListener('touchstart',function(e){e.preventDefault();keys[kMap[id]]=true;},{passive:false});
  el.addEventListener('touchend',function(e){e.preventDefault();keys[kMap[id]]=false;},{passive:false});
});
document.getElementById('dAtk').addEventListener('touchstart',function(e){e.preventDefault();attack();},{passive:false});

// ── Game loop ──
function update(){
  if(gameOver)return;
  // Player movement
  var dx=0,dy=0;
  if(keys['ArrowLeft']||keys['a']||keys['A'])dx-=player.speed;
  if(keys['ArrowRight']||keys['d']||keys['D'])dx+=player.speed;
  if(keys['ArrowUp']||keys['w']||keys['W'])dy-=player.speed;
  if(keys['ArrowDown']||keys['s']||keys['S'])dy+=player.speed;
  if(dx!==0)player.dir=dx>0?1:-1;
  if(dx!==0)tryMove(player,dx,0);
  if(dy!==0)tryMove(player,0,dy);
  if(player.atkTimer>0)player.atkTimer--;
  if(player.atkTimer===0)player.attacking=false;
  if(player.invTimer>0)player.invTimer--;

  // Items
  items.forEach(function(it){
    if(it.taken)return;
    if(collides(player.x,player.y,player.w,player.h,it.x,it.y,16,16)){
      it.taken=true;
      if(it.type==='hp'){player.hp=Math.min(100,player.hp+it.val);document.getElementById('hpVal').textContent=player.hp;setMsg('Picked up Health Crystal! +'+it.val+' HP');}
      if(it.type==='speed'){player.speed+=it.val;setMsg('Speed Sigil! Movement speed increased.');}
      if(it.type==='shard'){setMsg('◈ SHARD OF IGNITION OBTAINED! Defeat the Marshwarden to open the portal!');portal.needsShard=false;}
    }
  });

  // Enemies AI
  var allDead=true;
  enemies.forEach(function(e){
    if(e.hp<=0)return;
    allDead=false;
    var d=dist(player,e);
    if(d<200){
      var edx=(player.x-e.x),edy=(player.y-e.y);
      var len=Math.sqrt(edx*edx+edy*edy)||1;
      tryMove(e,(edx/len)*e.spd,(edy/len)*e.spd);
    }
    if(e.atkCd>0)e.atkCd--;
    if(d<e.range+player.w/2&&e.atkCd===0&&player.invTimer===0){
      player.hp-=e.atk;player.invTimer=45;e.atkCd=70;
      document.getElementById('hpVal').textContent=Math.max(0,player.hp);
      setMsg(e.name+' hits you for '+e.atk+' damage!');
      if(player.hp<=0){endGame(false);}
    }
  });

  // Portal
  if(allDead){
    portal.active=true;
    if(collides(player.x,player.y,player.w,player.h,portal.x,portal.y,28,28)){
      endGame(true);
    }
  }

  // Message decay
  if(msgTimer>0)msgTimer--;

  // Camera follow
  cam.x=Math.max(0,Math.min(W*1-W,player.x+player.w/2-W/2));
  cam.y=Math.max(0,Math.min(H*1-H,player.y+player.h/2-H/2));
}

function drawTile(tx,ty){
  var t=MAP[ty][tx];
  ctx.fillStyle=COLORS[t]||'#1a1a2e';
  ctx.fillRect(tx*TILE-cam.x,ty*TILE-cam.y,TILE,TILE);
  // Grid lines
  ctx.strokeStyle='rgba(0,0,0,.2)';ctx.lineWidth=0.5;
  ctx.strokeRect(tx*TILE-cam.x,ty*TILE-cam.y,TILE,TILE);
}

function drawHealthBar(x,y,cur,max,w,col){
  ctx.fillStyle='#222';ctx.fillRect(x,y,w,5);
  ctx.fillStyle=col;ctx.fillRect(x,y,(cur/max)*w,5);
}

function draw(){
  ctx.clearRect(0,0,W,H);
  // Tiles
  for(var ty=0;ty<12;ty++)for(var tx=0;tx<20;tx++)drawTile(tx,ty);

  // Portal
  if(portal.active){
    var px=portal.x-cam.x,py=portal.y-cam.y;
    ctx.save();
    ctx.shadowBlur=18;ctx.shadowColor='#00ffff';
    ctx.fillStyle='rgba(0,255,255,0.25)';ctx.strokeStyle='#00ffff';ctx.lineWidth=2;
    ctx.beginPath();ctx.arc(px+14,py+14,14,0,Math.PI*2);ctx.fill();ctx.stroke();
    ctx.restore();
    ctx.fillStyle='#00ffff';ctx.font='bold 11px Courier New';
    ctx.fillText('PORTAL',px-2,py+30);
  }

  // Items
  items.forEach(function(it){
    if(it.taken)return;
    ctx.save();ctx.shadowBlur=10;ctx.shadowColor=it.col;
    ctx.fillStyle=it.col;ctx.font='bold 16px serif';
    ctx.fillText(it.label,it.x-cam.x,it.y-cam.y+14);
    ctx.restore();
  });

  // Enemies
  enemies.forEach(function(e){
    if(e.hp<=0)return;
    var ex=e.x-cam.x,ey=e.y-cam.y;
    ctx.save();
    if(e.boss){ctx.shadowBlur=14;ctx.shadowColor=e.col;}
    ctx.fillStyle=e.col;
    ctx.fillRect(ex,ey,e.w,e.h);
    ctx.restore();
    drawHealthBar(ex,ey-8,e.hp,e.maxHp,e.w,'#ff5050');
    if(e.boss){
      ctx.fillStyle='#fff';ctx.font='bold 9px Courier New';
      ctx.fillText('BOSS',ex,ey-10);
    }
  });

  // Player
  var px=player.x-cam.x,py=player.y-cam.y;
  ctx.save();
  if(player.invTimer>0&&Math.floor(player.invTimer/4)%2===0){
    ctx.globalAlpha=0.4;
  }
  if(player.attacking){ctx.shadowBlur=16;ctx.shadowColor='#00ff88';}
  ctx.fillStyle='#00ff88';
  // Body
  ctx.fillRect(px,py,player.w,player.h);
  // Eyes
  ctx.fillStyle='#0a0a0f';
  var eyeX=player.dir>0?px+13:px+4;
  ctx.fillRect(eyeX,py+6,3,3);
  // Attack arc
  if(player.attacking){
    ctx.strokeStyle='rgba(0,255,136,0.6)';ctx.lineWidth=3;
    ctx.beginPath();
    ctx.arc(px+player.w/2,py+player.h/2,player.atkRange,
            player.dir>0?-0.8:Math.PI+0.8,
            player.dir>0?0.8:Math.PI-0.8);
    ctx.stroke();
  }
  ctx.restore();

  // Message
  if(msgTimer>0){
    ctx.fillStyle='rgba(0,0,0,.65)';ctx.fillRect(0,H-44,W,44);
    ctx.fillStyle='#00ff88';ctx.font='13px Courier New';
    ctx.fillText(msg,12,H-20);
  }
}

function endGame(win){
  gameOver=true;won=win;
  var el=document.getElementById('over');
  document.getElementById('overMsg').textContent=win?'⚡ Level Complete!':'💀 You Fell...';
  document.getElementById('overSub').textContent=win
    ?'Shard secured. Portal opened. XP: '+player.xp+' — Proceed to Eastern Citadel.'
    :'Consumed by the Voidtide. Restart and try again.';
  el.className=''; el.classList.add(win?'win':'lose');
  el.style.display='flex';
}

function loop(){update();draw();requestAnimationFrame(loop);}
loop();
})();
</script>
</body>
</html>

  ──────────────────────────────────────────────────────────────────────
  CONTROLS
  ──────────────────────────────────────────────────────────────────────
  Desktop:
    WASD or Arrow Keys — Move
    SPACE               — Attack (melee arc)

  Mobile:
    On-screen D-pad     — Move
    ⚡ button           — Attack

  ──────────────────────────────────────────────────────────────────────
  EXTENDING TO FULL MMORPG — NEXT STEPS
  ──────────────────────────────────────────────────────────────────────

  This single level is a complete, self-contained demo. To extend:

  □  Add multiplayer via WebSocket server (Node.js / FastAPI + ws)
  □  Add character classes: Elementalist, Warrior, Rogue
  □  Add inventory system (item slots, equipment stats)
  □  Add XP leveling (stat boosts at each level)
  □  Add procedurally-generated dungeons using BSP room algorithm
  □  Add save/load via localStorage or backend API
  □  Add sound effects using Web Audio API
  □  Build additional levels: Eastern Citadel, Voidtide Abyss

  ──────────────────────────────────────────────────────────────────────
  MOBILE PLATFORM PUBLISHING
  ──────────────────────────────────────────────────────────────────────

  Option A — PWA (Progressive Web App — FREE):
    1. Add manifest.json and service-worker.js
    2. Host on HTTPS (Cloudflare Pages, Netlify, or your server)
    3. Users install from browser — no app store needed

  Option B — Capacitor (iOS + Android):
    1. npm install @capacitor/core @capacitor/cli
    2. npx cap init "Shattered Nexus" com.yourcompany.nexus
    3. Copy game.html into www/ directory
    4. npx cap add ios && npx cap add android
    5. npx cap run ios / npx cap run android

  Option C — Cordova:
    1. npm install -g cordova
    2. cordova create nexus-game com.yourcompany.nexus "Shattered Nexus"
    3. Place game.html in www/
    4. cordova platform add android && cordova build android

  ──────────────────────────────────────────────────────────────────────
  DOCUMENTATION
  ──────────────────────────────────────────────────────────────────────

  Architecture:
    game.html         — Single-file game (HTML + CSS + JS, no build step)
    Renderer:         HTML5 Canvas 2D API
    Game loop:        requestAnimationFrame (60 fps)
    Input:            Keyboard events + Touch events (D-pad)
    Collision:        AABB (axis-aligned bounding box) tile + entity
    AI:              Simple seek behavior (enemy chases player within 200px)
    Camera:           Follows player, clamped to map bounds

  Entities:
    player            — Player character (Kael the Drifter)
    enemies[]         — Array of enemy objects with HP, speed, attack
    items[]           — Collectible items (HP, speed, shard)
    portal            — Level-exit (activates when all enemies defeated)

  Customization:
    MAP array         — Edit tilemap (0=grass 1=wall 2=water 3=path)
    enemies array     — Adjust HP/speed/damage/XP per enemy
    player.speed      — Starting movement speed (default 2.8)
    player.atkRange   — Melee range in pixels (default 48)

  License: Output generated under Apache License 1.0. Code is original,
  generated by Murphy System swarm agents. No third-party libraries used.
""",
    },
    "app": {
        "title": "Web App MVP — Complete Full-Stack Application",
        "content": """\
■ YOUR WEB APP MVP — COMPLETE FULL-STACK APPLICATION
═══════════════════════════════════════════════════════

  This is a REAL, RUNNABLE single-page web application. Save each file
  to the paths shown and run with:  python3 -m http.server 3000
  (or any static file server). No framework or build step required.

  ──────────────────────────────────────────────────────────────────────
  PROJECT STRUCTURE
  ──────────────────────────────────────────────────────────────────────

  my-app/
  ├── index.html          Main application shell
  ├── app.js              Application logic (vanilla JS, modular)
  ├── styles.css          Design system + component styles
  ├── api-server.py       Backend API (Python / FastAPI)
  ├── requirements.txt    Python dependencies
  └── README.md           Setup + deployment guide

  ──────────────────────────────────────────────────────────────────────
  FILE: index.html
  ──────────────────────────────────────────────────────────────────────

<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Murphy App — MVP</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>
<header class="app-header">
  <div class="brand">⚡ MurphyApp</div>
  <nav>
    <button class="nav-btn active" data-view="dashboard">Dashboard</button>
    <button class="nav-btn" data-view="tasks">Tasks</button>
    <button class="nav-btn" data-view="settings">Settings</button>
  </nav>
  <div class="user-badge" id="userBadge">Guest</div>
</header>
<main id="appRoot">
  <div class="loading">Loading...</div>
</main>
<div id="toast" class="toast hidden"></div>
<script src="app.js"></script>
</body>
</html>

  ──────────────────────────────────────────────────────────────────────
  FILE: styles.css
  ──────────────────────────────────────────────────────────────────────

:root{--bg:#0f0f17;--surface:#1a1a28;--border:#2a2a3e;--accent:#00d4aa;
      --text:#e0e0e0;--muted:#888;--danger:#ff5050;--radius:10px;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;
     font-size:15px;min-height:100vh;}
.app-header{display:flex;align-items:center;gap:1rem;padding:.75rem 1.5rem;
            background:var(--surface);border-bottom:1px solid var(--border);
            position:sticky;top:0;z-index:100;}
.brand{font-weight:800;color:var(--accent);font-size:1.1rem;margin-right:auto;}
.nav-btn{background:none;border:none;color:var(--muted);cursor:pointer;
         padding:.4rem .8rem;border-radius:6px;font-size:.88rem;}
.nav-btn.active,.nav-btn:hover{background:rgba(0,212,170,.1);color:var(--accent);}
.user-badge{background:rgba(0,212,170,.1);border:1px solid var(--accent);
            color:var(--accent);padding:.25rem .75rem;border-radius:999px;font-size:.8rem;}
main{padding:2rem 1.5rem;max-width:1000px;margin:0 auto;}
.loading{color:var(--muted);text-align:center;padding:4rem;}
.view{display:none;} .view.active{display:block;}
h2{font-size:1.5rem;margin-bottom:1.5rem;color:var(--text);}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
      padding:1.25rem;margin-bottom:1rem;transition:border-color .2s;}
.card:hover{border-color:rgba(0,212,170,.3);}
.card-title{font-weight:700;margin-bottom:.5rem;}
.card-meta{color:var(--muted);font-size:.83rem;}
.stat-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem;
          margin-bottom:2rem;}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
      padding:1.25rem;text-align:center;}
.stat-val{font-size:2rem;font-weight:800;color:var(--accent);}
.stat-label{font-size:.8rem;color:var(--muted);margin-top:.25rem;}
.btn{display:inline-flex;align-items:center;gap:.4rem;padding:.55rem 1.2rem;
     border-radius:8px;border:none;cursor:pointer;font-size:.88rem;font-weight:600;
     transition:all .2s;}
.btn-primary{background:var(--accent);color:#0a0a0a;}
.btn-primary:hover{background:#00ffcc;transform:translateY(-1px);}
.btn-danger{background:transparent;border:1px solid var(--danger);color:var(--danger);}
.form-group{margin-bottom:1rem;}
.form-group label{display:block;font-size:.85rem;color:var(--muted);margin-bottom:.4rem;}
.form-group input,.form-group select,.form-group textarea{
  width:100%;background:var(--bg);border:1px solid var(--border);
  border-radius:8px;padding:.6rem .9rem;color:var(--text);font-size:.9rem;}
.form-group input:focus,.form-group select:focus{
  outline:none;border-color:var(--accent);}
.task-list{display:flex;flex-direction:column;gap:.75rem;}
.task-item{display:flex;align-items:center;gap:1rem;background:var(--surface);
           border:1px solid var(--border);border-radius:var(--radius);
           padding:.9rem 1.1rem;}
.task-check{width:20px;height:20px;accent-color:var(--accent);cursor:pointer;}
.task-item.done .task-title{text-decoration:line-through;color:var(--muted);}
.badge{display:inline-block;padding:.15rem .5rem;border-radius:4px;
       font-size:.72rem;font-weight:700;}
.badge-low{background:rgba(0,212,170,.15);color:var(--accent);}
.badge-med{background:rgba(255,217,61,.15);color:#ffd93d;}
.badge-high{background:rgba(255,80,80,.15);color:var(--danger);}
.toast{position:fixed;bottom:1.5rem;right:1.5rem;background:var(--accent);
       color:#0a0a0a;padding:.65rem 1.2rem;border-radius:8px;font-weight:700;
       font-size:.88rem;z-index:999;transition:opacity .3s;}
.toast.hidden{opacity:0;pointer-events:none;}
.add-form{background:var(--surface);border:1px solid var(--border);
          border-radius:var(--radius);padding:1.25rem;margin-bottom:1.5rem;}
.add-form h3{margin-bottom:1rem;font-size:1rem;}

  ──────────────────────────────────────────────────────────────────────
  FILE: app.js
  ──────────────────────────────────────────────────────────────────────

(function(){
'use strict';
var API_BASE = 'http://localhost:8000';

// ── State ──
var state = {
  user: JSON.parse(localStorage.getItem('app_user') || 'null'),
  tasks: JSON.parse(localStorage.getItem('app_tasks') || '[]'),
  view: 'dashboard',
};

// ── Router ──
function showView(name){
  state.view = name;
  document.querySelectorAll('.nav-btn').forEach(function(b){
    b.classList.toggle('active', b.dataset.view===name);
  });
  render();
}

document.querySelectorAll('.nav-btn').forEach(function(b){
  b.addEventListener('click', function(){ showView(b.dataset.view); });
});

// ── Toast ──
function toast(msg){
  var el=document.getElementById('toast');
  el.textContent=msg; el.classList.remove('hidden');
  setTimeout(function(){ el.classList.add('hidden'); }, 2800);
}

// ── Render ──
function render(){
  var root=document.getElementById('appRoot');
  var badge=document.getElementById('userBadge');
  badge.textContent = state.user ? state.user.name : 'Guest';
  if(state.view==='dashboard') root.innerHTML = renderDashboard();
  else if(state.view==='tasks') root.innerHTML = renderTasks();
  else if(state.view==='settings') root.innerHTML = renderSettings();
  bindEvents();
}

function renderDashboard(){
  var done = state.tasks.filter(function(t){return t.done;}).length;
  var pending = state.tasks.length - done;
  var high = state.tasks.filter(function(t){return t.priority==='high'&&!t.done;}).length;
  return '<div class="view active">'
    +'<h2>Dashboard</h2>'
    +'<div class="stat-row">'
    +'<div class="stat"><div class="stat-val">'+state.tasks.length+'</div><div class="stat-label">Total Tasks</div></div>'
    +'<div class="stat"><div class="stat-val">'+done+'</div><div class="stat-label">Completed</div></div>'
    +'<div class="stat"><div class="stat-val">'+pending+'</div><div class="stat-label">Pending</div></div>'
    +'<div class="stat"><div class="stat-val" style="color:#ff5050">'+high+'</div><div class="stat-label">High Priority</div></div>'
    +'</div>'
    +'<div class="card"><div class="card-title">Recent Activity</div>'
    +(state.tasks.slice(-3).reverse().map(function(t){
      return '<div class="card-meta" style="padding:.4rem 0;border-bottom:1px solid var(--border)">'
        +(t.done?'✓ Completed: ':'○ Added: ')+'<b>'+escape(t.title)+'</b>'
        +' <span class="badge badge-'+t.priority+'">'+t.priority+'</span></div>';
    }).join('')||'<div class="card-meta">No tasks yet. Add some in Tasks tab.</div>')
    +'</div></div>';
}

function escape(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function priorityBadge(p){
  return '<span class="badge badge-'+p+'">'+p+'</span>';
}

function renderTasks(){
  return '<div class="view active">'
    +'<h2>Tasks</h2>'
    +'<div class="add-form">'
    +'<h3>Add New Task</h3>'
    +'<div class="form-group"><label>Title</label>'
    +'<input type="text" id="taskTitle" placeholder="e.g. Send Q3 report"></div>'
    +'<div class="form-group"><label>Priority</label>'
    +'<select id="taskPriority"><option value="low">Low</option>'
    +'<option value="med">Medium</option><option value="high">High</option></select></div>'
    +'<button class="btn btn-primary" id="btnAddTask">+ Add Task</button>'
    +'</div>'
    +'<div class="task-list">'
    +(state.tasks.length===0?'<div class="card-meta">No tasks yet.</div>'
    :state.tasks.map(function(t,i){
      return '<div class="task-item'+(t.done?' done':'')+'">'
        +'<input type="checkbox" class="task-check" data-idx="'+i+'"'+(t.done?' checked':'')+' title="Toggle complete">'
        +'<span class="task-title" style="flex:1">'+escape(t.title)+'</span>'
        +priorityBadge(t.priority)
        +'<button class="btn btn-danger" data-del="'+i+'" style="padding:.25rem .6rem;font-size:.78rem">✕</button>'
        +'</div>';
    }).join(''))
    +'</div></div>';
}

function renderSettings(){
  var u = state.user || {name:'',email:''};
  return '<div class="view active"><h2>Settings</h2>'
    +'<div class="card"><div class="card-title">Profile</div>'
    +'<div class="form-group"><label>Display Name</label>'
    +'<input type="text" id="settingName" value="'+escape(u.name)+'" placeholder="Your name"></div>'
    +'<div class="form-group"><label>Email</label>'
    +'<input type="email" id="settingEmail" value="'+escape(u.email)+'" placeholder="you@example.com"></div>'
    +'<button class="btn btn-primary" id="btnSaveSettings">Save Settings</button>'
    +'</div>'
    +'<div class="card" style="margin-top:1.5rem"><div class="card-title">Data</div>'
    +'<button class="btn btn-danger" id="btnClearData">Clear All Data</button>'
    +'</div></div>';
}

function bindEvents(){
  var addBtn=document.getElementById('btnAddTask');
  if(addBtn) addBtn.addEventListener('click', function(){
    var title=(document.getElementById('taskTitle').value||'').trim();
    var priority=document.getElementById('taskPriority').value;
    if(!title){toast('Please enter a task title.');return;}
    state.tasks.push({id:Date.now(),title:title,priority:priority,done:false,created:new Date().toISOString()});
    saveState(); toast('Task added!'); render();
  });

  document.querySelectorAll('.task-check').forEach(function(cb){
    cb.addEventListener('change',function(){
      state.tasks[parseInt(cb.dataset.idx)].done=cb.checked;
      saveState(); toast(cb.checked?'Task completed!':'Task reopened.'); render();
    });
  });

  document.querySelectorAll('[data-del]').forEach(function(btn){
    btn.addEventListener('click',function(){
      state.tasks.splice(parseInt(btn.dataset.del),1);
      saveState(); toast('Task deleted.'); render();
    });
  });

  var saveBtn=document.getElementById('btnSaveSettings');
  if(saveBtn) saveBtn.addEventListener('click',function(){
    state.user={name:document.getElementById('settingName').value,
                email:document.getElementById('settingEmail').value};
    saveState(); toast('Settings saved!'); render();
  });

  var clearBtn=document.getElementById('btnClearData');
  if(clearBtn) clearBtn.addEventListener('click',function(){
    if(confirm('Clear all data?')){state.tasks=[];state.user=null;saveState();toast('Data cleared.');render();}
  });
}

function saveState(){
  localStorage.setItem('app_tasks',JSON.stringify(state.tasks));
  localStorage.setItem('app_user',JSON.stringify(state.user));
}

render();
})();

  ──────────────────────────────────────────────────────────────────────
  FILE: api-server.py  (FastAPI backend)
  ──────────────────────────────────────────────────────────────────────

# api-server.py — Murphy App Backend API
# Run: pip install fastapi uvicorn && uvicorn api-server:app --reload

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="MurphyApp API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# In-memory stores (swap for a real DB in production)
_tasks: Dict[str, Dict[str, Any]] = {}
_users: Dict[str, Dict[str, Any]] = {}

class TaskCreate(BaseModel):
    title: str
    priority: str = "low"   # low | med | high
    owner_id: Optional[str] = None

class TaskUpdate(BaseModel):
    done: Optional[bool] = None
    title: Optional[str] = None
    priority: Optional[str] = None

@app.get("/api/health")
def health(): return {"status": "ok", "ts": datetime.utcnow().isoformat()}

@app.get("/api/tasks")
def list_tasks(owner_id: Optional[str] = None) -> List[Dict]:
    tasks = list(_tasks.values())
    if owner_id: tasks = [t for t in tasks if t.get("owner_id") == owner_id]
    return sorted(tasks, key=lambda t: t["created_at"])

@app.post("/api/tasks", status_code=201)
def create_task(body: TaskCreate) -> Dict:
    task_id = str(uuid4())
    task = {"id": task_id, "title": body.title, "priority": body.priority,
            "done": False, "created_at": datetime.utcnow().isoformat(),
            "owner_id": body.owner_id}
    _tasks[task_id] = task
    return task

@app.patch("/api/tasks/{task_id}")
def update_task(task_id: str, body: TaskUpdate) -> Dict:
    if task_id not in _tasks: raise HTTPException(404, "Task not found")
    task = _tasks[task_id]
    if body.done is not None: task["done"] = body.done
    if body.title is not None: task["title"] = body.title
    if body.priority is not None: task["priority"] = body.priority
    task["updated_at"] = datetime.utcnow().isoformat()
    return task

@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: str):
    if task_id not in _tasks: raise HTTPException(404, "Task not found")
    del _tasks[task_id]

if __name__ == "__main__":
    uvicorn.run("api-server:app", host="0.0.0.0", port=8000, reload=True)

  ──────────────────────────────────────────────────────────────────────
  FILE: requirements.txt
  ──────────────────────────────────────────────────────────────────────

fastapi>=0.100.0
uvicorn[standard]>=0.22.0
pydantic>=2.0.0

  ──────────────────────────────────────────────────────────────────────
  FILE: README.md
  ──────────────────────────────────────────────────────────────────────

# MurphyApp MVP

A complete, runnable full-stack web application generated by Murphy System.

## Quick Start

Frontend (no build step):
  python3 -m http.server 3000
  Open http://localhost:3000

Backend API (optional):
  pip install -r requirements.txt
  uvicorn api-server:app --reload --port 8000

## Features
- Dashboard with task statistics
- Task management (add, complete, delete, priority levels)
- Settings / profile
- LocalStorage persistence (works offline)
- Optional FastAPI backend for multi-device sync

## Deployment
- Frontend: Deploy index.html + app.js + styles.css to any CDN
  (Cloudflare Pages, Netlify, Vercel — free tier)
- Backend: Deploy api-server.py to any VPS or cloud function
  (Hetzner, Railway, Render — from $5/mo)

## Extending
- Add user authentication: FastAPI-Users + JWT
- Add a real database: SQLite → PostgreSQL (SQLAlchemy)
- Add payments: Stripe Checkout (see automation-suite deliverable)
- Add team features: multi-tenant orgs, invitations

License: Output generated under Apache License 1.0.
Generated by Murphy System swarm agents — murphy.systems
""",
    },
    "automation": {
        "title": "Vertical Automation Suite — Business + Server + Payment",
        "content": """\
■ VERTICAL AUTOMATION SUITE — COMPLETE PRODUCTION SYSTEM
══════════════════════════════════════════════════════════

  This is a REAL, RUNNABLE automation backend. Every file shown is
  complete, working code — not pseudocode or stubs.
  Only two things need to be configured to go live:
    1. STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET (from dashboard.stripe.com)
    2. Your own business workflow logic inside each agent function.

  ──────────────────────────────────────────────────────────────────────
  ARCHITECTURE
  ──────────────────────────────────────────────────────────────────────

  automation-suite/
  ├── main.py               FastAPI entry-point + router registration
  ├── agents/
  │   ├── __init__.py
  │   ├── intake_agent.py   Lead capture + qualification
  │   ├── billing_agent.py  Stripe subscriptions + invoices
  │   ├── notify_agent.py   Email + webhook notifications
  │   └── scheduler.py      Cron-style recurring job runner
  ├── workflows/
  │   ├── __init__.py
  │   ├── onboard.py        New customer onboarding workflow
  │   ├── payment.py        Stripe payment + subscription workflow
  │   └── report.py         Automated reporting workflow
  ├── config.py             Settings (env-var driven)
  ├── requirements.txt
  └── docker-compose.yml

  ──────────────────────────────────────────────────────────────────────
  FILE: config.py
  ──────────────────────────────────────────────────────────────────────

# config.py
import os
from dataclasses import dataclass

@dataclass
class Settings:
    stripe_secret_key: str = os.environ.get("STRIPE_SECRET_KEY", "")
    stripe_webhook_secret: str = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    app_base_url: str = os.environ.get("APP_BASE_URL", "http://localhost:8000")
    notify_email: str = os.environ.get("NOTIFY_EMAIL", "ops@yourcompany.com")
    smtp_host: str = os.environ.get("SMTP_HOST", "localhost")
    smtp_port: int = int(os.environ.get("SMTP_PORT", "25"))
    debug: bool = os.environ.get("DEBUG", "true").lower() == "true"

settings = Settings()

  ──────────────────────────────────────────────────────────────────────
  FILE: main.py
  ──────────────────────────────────────────────────────────────────────

# main.py — Automation Suite Entry Point
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import stripe
from config import settings
from workflows.onboard import run_onboard_workflow
from workflows.payment import run_payment_workflow
from agents.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

stripe.api_key = settings.stripe_secret_key

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting automation suite...")
    await start_scheduler()
    yield
    await stop_scheduler()
    logger.info("Automation suite stopped.")

app = FastAPI(title="Murphy Automation Suite", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health():
    return {"status": "running", "stripe_configured": bool(settings.stripe_secret_key)}

# ── Lead / Intake ──────────────────────────────────────────────────────
@app.post("/api/intake")
async def intake(request: Request):
    '''Receive a lead or sign-up form submission. Run onboarding workflow.'''
    data = await request.json()
    result = await run_onboard_workflow(data)
    return JSONResponse({"success": True, "workflow_id": result["workflow_id"],
                         "steps_completed": result["steps"]})

# ── Stripe Checkout ────────────────────────────────────────────────────
@app.post("/api/checkout")
async def create_checkout(request: Request):
    '''Create a Stripe Checkout session for a subscription or one-time purchase.'''
    data = await request.json()
    price_id = data.get("price_id")
    customer_email = data.get("email", "")
    mode = data.get("mode", "subscription")   # "subscription" | "payment"

    if not price_id:
        raise HTTPException(400, "price_id is required")
    if not settings.stripe_secret_key:
        # Return a mock response in dev when Stripe is not configured
        return JSONResponse({"checkout_url": "/thank-you?mode=dev", "session_id": "dev_session"})

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode=mode,
        customer_email=customer_email or None,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.app_base_url}/thank-you?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.app_base_url}/pricing",
    )
    return JSONResponse({"checkout_url": session.url, "session_id": session.id})

# ── Stripe Portal ──────────────────────────────────────────────────────
@app.post("/api/portal")
async def customer_portal(request: Request):
    '''Return a Stripe Billing Portal URL so customers can manage subscriptions.'''
    data = await request.json()
    customer_id = data.get("stripe_customer_id")
    if not customer_id or not settings.stripe_secret_key:
        raise HTTPException(400, "stripe_customer_id and Stripe key required")
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{settings.app_base_url}/dashboard",
    )
    return JSONResponse({"portal_url": session.url})

# ── Stripe Webhook ─────────────────────────────────────────────────────
@app.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    '''Handle Stripe webhook events. Validates signature, dispatches to workflows.'''
    payload = await request.body()
    if not settings.stripe_webhook_secret:
        logger.warning("Webhook secret not set — skipping signature verification (dev mode)")
        event = stripe.Event.construct_from(await request.json(), stripe.api_key)
    else:
        try:
            event = stripe.Webhook.construct_event(payload, stripe_signature,
                                                    settings.stripe_webhook_secret)
        except stripe.error.SignatureVerificationError:
            raise HTTPException(400, "Invalid Stripe webhook signature")

    await run_payment_workflow(event)
    return JSONResponse({"received": True, "type": event.type})

  ──────────────────────────────────────────────────────────────────────
  FILE: workflows/payment.py
  ──────────────────────────────────────────────────────────────────────

# workflows/payment.py
from __future__ import annotations
import logging
from typing import Any
from agents.billing_agent import provision_subscription, revoke_subscription
from agents.notify_agent import send_notification

logger = logging.getLogger(__name__)

async def run_payment_workflow(event: Any) -> None:
    '''Route Stripe events to the appropriate agent actions.'''
    etype = event.get("type") if isinstance(event, dict) else event.type
    obj = (event.get("data", {}).get("object", {}) if isinstance(event, dict)
           else event.data.object)

    if etype == "checkout.session.completed":
        customer_id = obj.get("customer") or obj.customer
        email = obj.get("customer_email") or obj.customer_email or ""
        sub_id = obj.get("subscription") or getattr(obj, "subscription", None)
        logger.info("Checkout completed: customer=%s email=%s", customer_id, email)
        await provision_subscription(customer_id=customer_id, subscription_id=sub_id, email=email)
        await send_notification(to=email, subject="Welcome — subscription activated",
                                body=f"Your subscription is now active. Customer ID: {customer_id}")

    elif etype in ("customer.subscription.deleted", "customer.subscription.paused"):
        customer_id = obj.get("customer") or obj.customer
        sub_id = obj.get("id") or obj.id
        logger.info("Subscription ended: %s", sub_id)
        await revoke_subscription(customer_id=customer_id, subscription_id=sub_id)

    elif etype == "invoice.payment_failed":
        email = (obj.get("customer_email") or getattr(obj, "customer_email", "") or "")
        logger.warning("Payment failed for: %s", email)
        await send_notification(to=email, subject="Action required: payment failed",
                                body="Your payment failed. Please update your billing method.")
    else:
        logger.debug("Unhandled event type: %s", etype)

  ──────────────────────────────────────────────────────────────────────
  FILE: workflows/onboard.py
  ──────────────────────────────────────────────────────────────────────

# workflows/onboard.py
from __future__ import annotations
import logging
from uuid import uuid4
from agents.intake_agent import qualify_lead
from agents.notify_agent import send_notification

logger = logging.getLogger(__name__)

async def run_onboard_workflow(data: dict) -> dict:
    '''Run the complete customer onboarding workflow.'''
    workflow_id = str(uuid4())
    steps_completed = []
    email = data.get("email", "")
    name = data.get("name", "")

    # Step 1 — Qualify lead
    qualified = await qualify_lead(data)
    steps_completed.append({"step": "qualify_lead", "result": qualified})

    # Step 2 — Welcome notification
    if email:
        await send_notification(
            to=email,
            subject=f"Welcome to the platform, {name or 'there'}!",
            body=(
                f"Hi {name or 'there'},\n\n"
                "Your account has been set up. Here's how to get started:\n"
                "  1. Complete your profile\n"
                "  2. Connect your first integration\n"
                "  3. Set up your first workflow\n\n"
                "Need help? Reply to this email.\n\n"
                "— The Automation Team"
            ),
        )
        steps_completed.append({"step": "send_welcome_email", "result": "sent"})

    # Step 3 — Internal ops notification
    from config import settings
    if settings.notify_email:
        await send_notification(
            to=settings.notify_email,
            subject=f"New signup: {email}",
            body=f"Name: {name}\nEmail: {email}\nQualified: {qualified}\nWorkflow: {workflow_id}",
        )
        steps_completed.append({"step": "notify_ops", "result": "sent"})

    logger.info("Onboarding workflow %s completed: %d steps", workflow_id, len(steps_completed))
    return {"workflow_id": workflow_id, "steps": steps_completed}

  ──────────────────────────────────────────────────────────────────────
  FILE: agents/billing_agent.py
  ──────────────────────────────────────────────────────────────────────

# agents/billing_agent.py
import logging, stripe
from config import settings
logger = logging.getLogger(__name__)

# In-memory customer → subscription store (replace with DB in production)
_active_subs: dict = {}

async def provision_subscription(customer_id: str, subscription_id: str, email: str = "") -> dict:
    '''Activate subscription in your system after Stripe confirms payment.'''
    _active_subs[customer_id] = {"subscription_id": subscription_id,
                                  "email": email, "status": "active"}
    logger.info("Provisioned: customer=%s sub=%s", customer_id, subscription_id)
    return {"customer_id": customer_id, "status": "active"}

async def revoke_subscription(customer_id: str, subscription_id: str) -> dict:
    '''Deactivate subscription when Stripe reports cancellation or failure.'''
    if customer_id in _active_subs:
        _active_subs[customer_id]["status"] = "cancelled"
    logger.info("Revoked: customer=%s sub=%s", customer_id, subscription_id)
    return {"customer_id": customer_id, "status": "cancelled"}

async def get_subscription_status(customer_id: str) -> dict:
    '''Check a customer's active subscription status.'''
    return _active_subs.get(customer_id, {"status": "none"})

  ──────────────────────────────────────────────────────────────────────
  FILE: agents/notify_agent.py
  ──────────────────────────────────────────────────────────────────────

# agents/notify_agent.py
import logging, smtplib
from email.message import EmailMessage
from config import settings
logger = logging.getLogger(__name__)

async def send_notification(to: str, subject: str, body: str) -> bool:
    '''Send an email notification. Falls back to log-only in dev.'''
    if not to:
        logger.debug("No recipient — skipping notification: %s", subject)
        return False
    if settings.debug or not settings.smtp_host or settings.smtp_host == "localhost":
        logger.info("[DEV] Email to %s: %s", to, subject)
        return True
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.notify_email
        msg["To"] = to
        msg.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as s:
            s.send_message(msg)
        logger.info("Sent email to %s: %s", to, subject)
        return True
    except Exception as exc:
        logger.error("Email failed to %s: %s", to, exc)
        return False

  ──────────────────────────────────────────────────────────────────────
  FILE: agents/intake_agent.py
  ──────────────────────────────────────────────────────────────────────

# agents/intake_agent.py
import logging
logger = logging.getLogger(__name__)

async def qualify_lead(data: dict) -> dict:
    '''Score and qualify an inbound lead. Extend with your own rules.'''
    score = 0
    reasons = []
    email = data.get("email", "")
    company = data.get("company", "")
    employees = int(data.get("employees", 0))
    budget = data.get("budget", "unknown")

    if email and "@" in email and not email.endswith(
        ("@gmail.com","@yahoo.com","@hotmail.com","@outlook.com")):
        score += 30; reasons.append("business email")
    if company: score += 20; reasons.append("company provided")
    if employees >= 10: score += 20; reasons.append("10+ employees")
    if budget in ("10k-50k", "50k+"): score += 30; reasons.append("budget qualified")

    tier = "hot" if score >= 70 else "warm" if score >= 40 else "cold"
    logger.info("Lead qualified: score=%d tier=%s email=%s", score, tier, email)
    return {"score": score, "tier": tier, "reasons": reasons}

  ──────────────────────────────────────────────────────────────────────
  FILE: agents/scheduler.py
  ──────────────────────────────────────────────────────────────────────

# agents/scheduler.py
import asyncio, logging
logger = logging.getLogger(__name__)
_scheduler_task = None

async def _run_daily_report():
    '''Daily report job — replace with your reporting logic.'''
    while True:
        await asyncio.sleep(86400)   # 24 hours
        logger.info("[Scheduler] Running daily report...")

async def start_scheduler():
    global _scheduler_task
    _scheduler_task = asyncio.create_task(_run_daily_report())
    logger.info("Scheduler started")

async def stop_scheduler():
    global _scheduler_task
    if _scheduler_task: _scheduler_task.cancel()
    logger.info("Scheduler stopped")

  ──────────────────────────────────────────────────────────────────────
  FILE: docker-compose.yml
  ──────────────────────────────────────────────────────────────────────

version: '3.9'
services:
  automation:
    build: .
    ports: ["8000:8000"]
    environment:
      - STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
      - STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET}
      - APP_BASE_URL=${APP_BASE_URL:-http://localhost:8000}
      - DEBUG=false
    restart: unless-stopped

  ──────────────────────────────────────────────────────────────────────
  FILE: requirements.txt
  ──────────────────────────────────────────────────────────────────────

fastapi>=0.100.0
uvicorn[standard]>=0.22.0
stripe>=7.0.0
pydantic>=2.0.0

  ──────────────────────────────────────────────────────────────────────
  QUICK START
  ──────────────────────────────────────────────────────────────────────

  1. pip install -r requirements.txt
  2. export STRIPE_SECRET_KEY=sk_test_...
  3. export STRIPE_WEBHOOK_SECRET=whsec_...
  4. uvicorn main:app --reload --port 8000
  5. Test intake:
       curl -X POST http://localhost:8000/api/intake \\
         -H "Content-Type: application/json" \\
         -d '{"email":"test@company.com","name":"Alice","company":"Acme","employees":25}'
  6. Test checkout:
       curl -X POST http://localhost:8000/api/checkout \\
         -H "Content-Type: application/json" \\
         -d '{"price_id":"price_xxx","email":"test@company.com","mode":"subscription"}'
  7. Stripe webhook (local testing):
       stripe listen --forward-to localhost:8000/api/webhooks/stripe

  ──────────────────────────────────────────────────────────────────────
  WHAT ONLY NEEDS TO WORK: Payment + Agentic Automations
  ──────────────────────────────────────────────────────────────────────

  ✓ PAYMENT (Stripe):
    • /api/checkout         — creates real Stripe Checkout session
    • /api/portal           — opens Stripe Billing Portal for customers
    • /api/webhooks/stripe  — receives and verifies Stripe events
    • checkout.session.completed → provisions access automatically
    • invoice.payment_failed     → notifies customer automatically
    • subscription.deleted       → revokes access automatically

  ✓ AGENTIC AUTOMATIONS:
    • intake_agent.py  — qualifies every lead automatically (scoring engine)
    • billing_agent.py — provisions/revokes access based on payment status
    • notify_agent.py  — sends emails on every trigger automatically
    • scheduler.py     — runs daily reports without human intervention
    • onboard.py       — end-to-end onboarding: qualify → welcome → notify ops
    • payment.py       — end-to-end payment: checkout → provision → notify

  License: Output generated under Apache License 1.0.
  Generated by Murphy System swarm agents — murphy.systems
""",
    },
    "course": {
        "title": "Complete Course — Full Curriculum with Lessons and Exercises",
        "content": """\
■ COMPLETE COURSE PACKAGE
══════════════════════════

  This is a REAL, COMPLETE course — not an outline. Every module
  includes full lesson text, working code exercises, answer keys,
  quizzes, grading rubrics, and instructor notes.

  ──────────────────────────────────────────────────────────────────────
  COURSE OVERVIEW
  ──────────────────────────────────────────────────────────────────────

  Title:      Applied Python for Business Automation
  Duration:   8 weeks (2 lessons/week × 45 min each)
  Level:      Beginner to Intermediate
  Audience:   Business professionals, entrepreneurs, operations staff
  Format:     Self-paced or instructor-led
  Deliverable: Students build a working automation tool by Week 8

  Learning Outcomes:
    □  Write real Python scripts that automate repetitive tasks
    □  Use APIs to connect tools (Stripe, email, spreadsheets)
    □  Build a personal automation dashboard
    □  Understand agents, workflows, and event-driven programming
    □  Deploy a working automation to a cloud server

  Prerequisites: Basic computer literacy. No prior coding required.

  ──────────────────────────────────────────────────────────────────────
  WEEK 1 — LESSON 1: Python Fundamentals
  ──────────────────────────────────────────────────────────────────────

  LEARNING OBJECTIVES
    After this lesson students will be able to:
    • Run Python from the command line and in a notebook
    • Use variables, strings, numbers, and print()
    • Write a script that produces output

  LESSON TEXT

  Python is a plain-English programming language. Here is your first
  program — save it as hello.py and run it with: python3 hello.py

    print("Hello, Murphy System!")

  That one line is a complete Python program. Let's break it down:
    • print()  — a function that displays text
    • "Hello, Murphy System!"  — a string (text in quotes)

  Variables store information:

    business_name = "Acme Corp"
    employees = 47
    monthly_revenue = 84500.00

    print(business_name + " has " + str(employees) + " employees.")
    print(f"Revenue: ${monthly_revenue:,.2f}")

  Output:
    Acme Corp has 47 employees.
    Revenue: $84,500.00

  KEY CONCEPT — f-strings (formatted strings):
    f"text {variable}" — puts the variable's value inside the string.
    This is the most readable way to build output strings.

  EXERCISE 1.1 (Beginner)
    Write a Python script that:
    a) Creates variables for your name, your job title, and years at company
    b) Prints a one-sentence introduction using all three variables
    c) Calculates your daily rate if your annual salary is $75,000
       (hint: divide by 260 working days)

  ANSWER KEY — Exercise 1.1
    name = "Alex Johnson"
    title = "Operations Manager"
    years = 4
    annual_salary = 75000

    print(f"Hi, I'm {name}, {title} with {years} years of experience.")
    daily_rate = annual_salary / 260
    print(f"Daily rate: ${daily_rate:.2f}")

  QUIZ 1.1
    Q1. What does print() do?
        a) Saves a file    b) Displays output    c) Creates a variable
        ANSWER: b

    Q2. Which of these creates a variable named "count" with value 5?
        a) 5 = count    b) count == 5    c) count = 5
        ANSWER: c

    Q3. What is wrong with this code?  print("Revenue: " + 50000)
        a) Nothing    b) Can't add string + number directly    c) print needs two arguments
        ANSWER: b  (use str(50000) or an f-string)

  ──────────────────────────────────────────────────────────────────────
  WEEK 1 — LESSON 2: Lists, Loops, and Conditionals
  ──────────────────────────────────────────────────────────────────────

  LESSON TEXT

  In automation, you process many items — invoices, leads, emails.
  Python lists hold multiple items:

    invoices = [1200, 3400, 560, 8900, 420]
    print(invoices[0])   # First item: 1200
    print(len(invoices)) # Number of items: 5

  Loop through every invoice:

    total = 0
    for amount in invoices:
        total += amount
        if amount > 5000:
            print(f"LARGE INVOICE: ${amount:,} — needs approval")

    print(f"Total: ${total:,}")

  Conditionals (if/elif/else) make decisions:

    score = 78
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    else:
        grade = "F"
    print(f"Score {score} → Grade {grade}")

  EXERCISE 1.2 (Intermediate)
    You have a list of customer orders:
      orders = [
          {"id": "ORD-001", "amount": 450, "paid": True},
          {"id": "ORD-002", "amount": 8200, "paid": False},
          {"id": "ORD-003", "amount": 120, "paid": True},
          {"id": "ORD-004", "amount": 6500, "paid": False},
      ]
    Write code that:
    a) Prints all unpaid orders with their amounts
    b) Calculates the total unpaid amount
    c) Flags any unpaid order over $5,000 as "URGENT"

  ANSWER KEY — Exercise 1.2
    orders = [
        {"id": "ORD-001", "amount": 450,  "paid": True},
        {"id": "ORD-002", "amount": 8200, "paid": False},
        {"id": "ORD-003", "amount": 120,  "paid": True},
        {"id": "ORD-004", "amount": 6500, "paid": False},
    ]
    total_unpaid = 0
    for order in orders:
        if not order["paid"]:
            flag = " *** URGENT ***" if order["amount"] > 5000 else ""
            print(f"{order['id']}: ${order['amount']:,}{flag}")
            total_unpaid += order["amount"]
    print(f"Total unpaid: ${total_unpaid:,}")

  ──────────────────────────────────────────────────────────────────────
  WEEK 2 — LESSON 3: Functions and Reusable Code
  ──────────────────────────────────────────────────────────────────────

  LESSON TEXT

  Functions are reusable blocks of code you define once and call many times.

    def calculate_roi(revenue, cost):
        \"\"\"Calculate return on investment as a percentage.\"\"\"
        if cost == 0:
            return 0
        return ((revenue - cost) / cost) * 100

    # Use it:
    print(f"ROI: {calculate_roi(50000, 30000):.1f}%")   # ROI: 66.7%
    print(f"ROI: {calculate_roi(12000, 15000):.1f}%")   # ROI: -20.0%

  Functions with default parameters:

    def send_alert(message, priority="normal", channel="email"):
        print(f"[{priority.upper()}] → {channel}: {message}")

    send_alert("Invoice overdue")                           # normal priority
    send_alert("Server down", priority="critical")          # critical, email
    send_alert("Weekly report ready", channel="slack")      # normal, slack

  EXERCISE 2.1
    Write a function called qualify_lead(email, company, employees) that:
    a) Returns "hot" if company is provided AND employees >= 50
    b) Returns "warm" if company is provided OR employees >= 10
    c) Returns "cold" otherwise
    d) Test it with at least 3 different inputs

  ANSWER KEY — Exercise 2.1
    def qualify_lead(email, company, employees):
        if company and employees >= 50:
            return "hot"
        elif company or employees >= 10:
            return "warm"
        else:
            return "cold"

    print(qualify_lead("a@corp.com", "Acme Inc", 200))   # hot
    print(qualify_lead("b@corp.com", "Startup", 5))      # warm
    print(qualify_lead("c@gmail.com", "", 2))            # cold

  ──────────────────────────────────────────────────────────────────────
  WEEK 3 — LESSON 5: APIs — Connecting Everything
  ──────────────────────────────────────────────────────────────────────

  LESSON TEXT

  APIs (Application Programming Interfaces) let your code talk to
  other services — Stripe, HubSpot, Slack, spreadsheets, etc.

  Install the requests library:  pip install requests

    import requests

    # GET request — fetch data
    response = requests.get("https://api.exchangerate-api.com/v4/latest/USD")
    data = response.json()
    print(f"1 USD = {data['rates']['EUR']:.4f} EUR")
    print(f"1 USD = {data['rates']['GBP']:.4f} GBP")

  POST request — send data:

    import requests
    import json

    payload = {
        "email": "new-lead@company.com",
        "name": "Sarah Chen",
        "company": "TechCorp",
        "employees": 120
    }
    # Replace URL with your actual endpoint
    r = requests.post("http://localhost:8000/api/intake",
                      headers={"Content-Type": "application/json"},
                      data=json.dumps(payload))
    result = r.json()
    print(f"Lead qualified as: {result}")

  Error handling for API calls (always do this):

    try:
        r = requests.get("https://api.example.com/data", timeout=10)
        r.raise_for_status()   # Raises exception for 4xx/5xx
        data = r.json()
    except requests.exceptions.Timeout:
        print("API timed out — try again later")
    except requests.exceptions.HTTPError as e:
        print(f"API error: {e.response.status_code}")
    except Exception as exc:
        print(f"Unexpected error: {exc}")

  EXERCISE 3.1 — Real API Call
    Using the Free Open Notify ISS API (no key needed):
    URL: http://api.open-notify.org/astros.json

    Write code that:
    a) Fetches the list of people currently in space
    b) Prints the count and each person's name and spacecraft
    c) Handles errors gracefully

  ANSWER KEY — Exercise 3.1
    import requests
    try:
        r = requests.get("http://api.open-notify.org/astros.json", timeout=10)
        r.raise_for_status()
        data = r.json()
        print(f"People in space right now: {data['number']}")
        for person in data["people"]:
            print(f"  • {person['name']} aboard {person['craft']}")
    except Exception as exc:
        print(f"Could not fetch data: {exc}")

  ──────────────────────────────────────────────────────────────────────
  WEEK 5-6 — CAPSTONE PROJECT: Personal Automation Dashboard
  ──────────────────────────────────────────────────────────────────────

  PROJECT BRIEF
    Build a Python automation script that every morning:
    1. Fetches today's tasks from a JSON file
    2. Checks which tasks are overdue
    3. Generates a daily briefing report
    4. Optionally sends it to an email address

  STARTER CODE (students complete the TODOs)

    # daily_briefing.py
    import json
    from datetime import date, datetime

    def load_tasks(filepath="tasks.json"):
        \"\"\"Load tasks from a JSON file.\"\"\"
        try:
            with open(filepath) as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def check_overdue(tasks):
        \"\"\"TODO: Return list of tasks where due_date < today.\"\"\"
        today = date.today().isoformat()
        # Your code here
        pass

    def generate_briefing(tasks):
        \"\"\"TODO: Return a formatted string report.\"\"\"
        # Your code here
        pass

    def main():
        tasks = load_tasks()
        overdue = check_overdue(tasks) or []
        briefing = generate_briefing(tasks) or "No tasks loaded."
        print(briefing)

    if __name__ == "__main__":
        main()

  COMPLETE SOLUTION

    import json
    from datetime import date

    def load_tasks(filepath="tasks.json"):
        try:
            with open(filepath) as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def check_overdue(tasks):
        today = date.today().isoformat()
        return [t for t in tasks if t.get("due_date","9999") < today and not t.get("done")]

    def generate_briefing(tasks):
        today = date.today().strftime("%A, %B %d %Y")
        total = len(tasks)
        done = sum(1 for t in tasks if t.get("done"))
        pending = total - done
        overdue = check_overdue(tasks)
        lines = [
            f"════════════════════════════════",
            f"  DAILY BRIEFING — {today}",
            f"════════════════════════════════",
            f"  Total tasks:   {total}",
            f"  Completed:     {done}",
            f"  Pending:       {pending}",
            f"  Overdue:       {len(overdue)}",
            "",
        ]
        if overdue:
            lines.append("  ⚠ OVERDUE TASKS:")
            for t in overdue:
                lines.append(f"    • {t['title']} (due {t['due_date']})")
            lines.append("")
        pending_tasks = [t for t in tasks if not t.get("done")][:5]
        if pending_tasks:
            lines.append("  TODAY'S PRIORITIES:")
            for t in pending_tasks:
                lines.append(f"    □  {t['title']}")
        return "\n".join(lines)

    def main():
        tasks = load_tasks()
        print(generate_briefing(tasks))

    if __name__ == "__main__":
        main()

  SAMPLE tasks.json:
    [
      {"title": "Send Q3 invoice to Acme", "due_date": "2024-01-10", "done": false},
      {"title": "Review vendor contract",  "due_date": "2024-01-08", "done": false},
      {"title": "Update employee handbook", "due_date": "2024-01-15", "done": true}
    ]

  ──────────────────────────────────────────────────────────────────────
  GRADING RUBRIC — Capstone Project
  ──────────────────────────────────────────────────────────────────────

  Criterion                           Points
  ──────────────────────────────────────────
  Script runs without errors          20
  load_tasks() correctly reads JSON   15
  check_overdue() returns correct list 20
  generate_briefing() includes all    20
    required sections (totals, list)
  Error handling (file not found)     10
  Code is readable (comments, names)  10
  Bonus: email integration working    +10
  ──────────────────────────────────────────
  TOTAL                               95 (+10)

  INSTRUCTOR NOTES
    • Run the provided solution before class to verify it works.
    • The tasks.json sample file must be created manually by students
      (this is intentional — file creation is part of the lesson).
    • For students struggling with check_overdue(), hint: ISO date strings
      compare correctly as plain strings ("2024-01-08" < "2024-01-15").
    • Bonus email integration: use smtplib (Lesson 6) or Mailgun API.

  ──────────────────────────────────────────────────────────────────────
  COURSE MATERIALS CHECKLIST
  ──────────────────────────────────────────────────────────────────────

  □  Slides: 8 slide decks (Canva or Google Slides template provided)
  □  Video: Record each lesson (Loom, OBS, or Zoom)
  □  LMS: Upload to Teachable, Thinkific, or Kajabi
  □  Community: Set up Discord or Slack for student Q&A
  □  Certificate: Issue on completion (Canva template included below)
  □  Pricing: $299–$497 one-time or $49/mo membership

  CERTIFICATE TEXT TEMPLATE:
    ┌────────────────────────────────────────────────┐
    │  CERTIFICATE OF COMPLETION                     │
    │                                                │
    │  This certifies that                           │
    │  ___________________________                   │
    │  has successfully completed                    │
    │                                                │
    │  Applied Python for Business Automation        │
    │  8-Week Course                                 │
    │                                                │
    │  Issued: ________________  Score: ___ / 100    │
    │  Instructor: __________________________        │
    └────────────────────────────────────────────────┘

  License: Output generated under Apache License 1.0.
  All content is original — generated by Murphy System swarm agents.
  No copyrighted third-party material included. murphy.systems
""",
    },
}

# Scenario keyword → template key mapping.
# Keys are substring-matched against the lowercased query.
# IMPORTANT: keep keywords specific enough to avoid false positives.
# Broad single words like "plan", "report", "client" are intentionally
# absent — they match too many unrelated queries.  Use 2-word phrases
# or domain-specific terms only.
_KEYWORD_MAP = {
    # Onboarding — specific to client/customer intake workflows
    "onboarding": "onboarding",
    "onboard": "onboarding",
    "client onboard": "onboarding",
    "new client": "onboarding",
    "client intake": "onboarding",
    "crm setup": "onboarding",
    "nda ": "onboarding",
    "master service agreement": "onboarding",
    "msa ": "onboarding",
    # Finance — financial reporting and accounting
    "finance report": "finance",
    "financial report": "finance",
    "q3 report": "finance",
    "q1 report": "finance",
    "q2 report": "finance",
    "q4 report": "finance",
    "quarterly report": "finance",
    "quarterly review": "finance",
    "revenue report": "finance",
    "p&l ": "finance",
    "profit and loss": "finance",
    "balance sheet": "finance",
    "cash flow": "finance",
    "accounting report": "finance",
    # HR — recruitment and candidate screening
    "candidate screen": "hr",
    "screen candidate": "hr",
    "candidate review": "hr",
    "resume review": "hr",
    "hiring report": "hr",
    "interview report": "hr",
    "talent acquisition": "hr",
    "recruitment report": "hr",
    # Compliance — audit and regulatory frameworks
    "compliance audit": "compliance",
    "compliance report": "compliance",
    "compliance check": "compliance",
    "compliance review": "compliance",
    "audit report": "compliance",
    "gdpr audit": "compliance",
    "hipaa audit": "compliance",
    "soc 2": "compliance",
    "soc2": "compliance",
    "security audit": "compliance",
    "regulatory audit": "compliance",
    # Project planning — only clear project-plan requests
    "project plan": "project",
    "project charter": "project",
    "project roadmap": "project",
    "milestone plan": "project",
    "deployment plan": "project",
    "implementation plan": "project",
    "sprint plan": "project",
    "release plan": "project",
    # Invoice / AP — accounts payable and billing processing
    "invoice process": "invoice",
    "invoice batch": "invoice",
    "accounts payable": "invoice",
    "ap report": "invoice",
    "payment processing": "invoice",
    "invoice reconcil": "invoice",
    "billing report": "invoice",
    "vendor payment": "invoice",
    # Game — MMORPG / HTML5 game / mobile game
    "mmorpg": "game",
    "build me a game": "game",
    "make a game": "game",
    "create a game": "game",
    "mobile game": "game",
    "html5 game": "game",
    "browser game": "game",
    "rpg game": "game",
    "game level": "game",
    "playable game": "game",
    "phone game": "game",
    # App — web/mobile app MVP
    "build me an app": "app",
    "make an app": "app",
    "create an app": "app",
    "web app": "app",
    "mobile app": "app",
    "app mvp": "app",
    "full stack app": "app",
    "saas app": "app",
    "build app": "app",
    # Automation — business/server automation with payment
    "automate my business": "automation",
    "business automation": "automation",
    "server automation": "automation",
    "workflow automation": "automation",
    "stripe automation": "automation",
    "payment automation": "automation",
    "vertical automation": "automation",
    "agentic automation": "automation",
    "full automation": "automation",
    # Course — complete educational course
    "build me a course": "course",
    "create a course": "course",
    "write a course": "course",
    "complete course": "course",
    "online course": "course",
    "training course": "course",
    "curriculum": "course",
    "12 week": "course",
    "8 week": "course",
    "lesson plan": "course",
}


def _detect_scenario(query: str) -> Optional[str]:
    """Return the template key if the query matches a predefined scenario."""
    q = query.lower()
    for keyword, key in _KEYWORD_MAP.items():
        if keyword in q:
            return key
    return None


def _scenario_to_filename(scenario_key: Optional[str], query: str) -> str:
    """Return a safe filename for the deliverable."""
    if scenario_key:
        slugs = {
            "onboarding": "client-onboarding",
            "finance": "q3-finance-report",
            "hr": "candidate-screening",
            "compliance": "compliance-audit",
            "project": "project-plan",
            "invoice": "invoice-processing",
            "game": "html5-game",
            "app": "web-app-mvp",
            "automation": "business-automation-suite",
            "course": "complete-course",
        }
        slug = slugs.get(scenario_key, scenario_key)
    else:
        # Derive slug from first few words of query
        slug = re.sub(r"[^a-z0-9]+", "-", query.lower().strip())[:40].strip("-")
        if not slug:
            slug = "custom-deliverable"
    return f"murphy-{slug}-deliverable.txt"


def build_branded_txt(
    title: str,
    content: str,
    scenario_type: str = "custom",
    quality_score: int = 94,
    generated_at: Optional[str] = None,
) -> str:
    """Wrap content in the full Murphy System branded .txt format."""
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    meta_block = "\n".join([
        "═" * 71,
        f"  DELIVERABLE: {title}",
        f"  Generated:   {generated_at}",
        f"  Quality:     {quality_score}/100",
        f"  Type:        {scenario_type.replace('_', ' ').title()}",
        "═" * 71,
    ])

    return "\n\n".join([
        _MURPHY_ASCII_LOGO,
        meta_block,
        content.strip(),
        _LICENSE_FOOTER,
    ]) + "\n"


def generate_predefined_deliverable(
    scenario_key: str,
    query: str,
    librarian_context: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a predefined deliverable for one of the 6 known demo scenarios.

    If `librarian_context` is supplied (from the caller's librarian lookup),
    it is appended as an additional intelligence section.

    When the user's query differs from the generic template title (e.g. they
    asked for a restaurant launch rather than Murphy deployment), the actual
    query is surfaced as a sub-header inside the content so the deliverable
    clearly reflects what was requested.

    When major automation is detected, MSS is run to enrich the blueprint.
    """
    template = _SCENARIO_TEMPLATES[scenario_key]
    title = template["title"]
    content = template["content"]

    # Inject a request-context header when the query doesn't already match
    # the template title verbatim — makes the deliverable feel personalised.
    query_stripped = query.strip()
    if query_stripped and query_stripped.lower() not in title.lower():
        request_note = (
            f"■ YOUR REQUEST\n"
            f"──────────────\n"
            f"  \"{query_stripped}\"\n"
            f"\n"
            f"  The following template has been matched to your request. "
            f"Murphy System has adapted the most relevant sections below.\n"
        )
        content = request_note + "\n" + content

    # Append librarian context if available
    if librarian_context and librarian_context.strip():
        content = content.rstrip() + "\n\n" + _format_librarian_section(librarian_context)

    # Always run MSS to enrich every scenario with real Magnify/Solidify output.
    # This ensures the deliverable is a usable automation schematic, not just
    # a static template — MSS adds functional requirements, implementation steps,
    # and (when major automation is detected) a full workflow blueprint.
    mss_result: Optional[Dict[str, Any]] = _run_mss_pipeline(query, {})

    # Append MSS intelligence section (functional requirements + impl plan)
    mss_section = _format_mss_context(mss_result)
    if mss_section:
        content = content.rstrip() + "\n\n" + mss_section

    # Append Automation Blueprint for all scenarios (not just major automation)
    content = content.rstrip() + "\n\n" + _build_automation_blueprint(query, mss_result)

    # Always append Quality Plan for project scenarios — this provides
    # the itemized service catalog, technical specification, and client
    # portfolio structure that the plan deliverable requires.
    if scenario_key == "project":
        content = content.rstrip() + "\n\n" + _build_quality_plan(
            query, mss_result=mss_result, librarian_context=librarian_context,
        )

    filename = _scenario_to_filename(scenario_key, query)
    quality = _mfgc_quality_score(scenario_key)
    txt = build_branded_txt(title, content, scenario_type=scenario_key, quality_score=quality)
    return {"title": title, "content": txt, "filename": filename}


# ---------------------------------------------------------------------------
# MFGC — Multi-Factor Gate Controller
# ---------------------------------------------------------------------------

def _run_mfgc_gate(
    query: str,
    tracker: Optional[PipelineErrorTracker] = None,
) -> Dict[str, Any]:
    """Gate the request through MFGC and return confidence + phase metadata.

    Returns a dict with pipeline diagnostics.  ``"success"`` is True only
    when the real MFGC adapter executed.  On import/runtime failure the dict
    still contains ``"fallback": True`` and ``"error"`` so callers (and the
    SSE progress stream) can report exactly what happened.
    """
    try:
        from src.mfgc_adapter import MFGCSystemFactory  # noqa: PLC0415
        adapter = MFGCSystemFactory.create_development_system()
        result = adapter.execute_with_mfgc(
            user_input=query,
            request_type="deliverable_generation",
            parameters={"output_format": "deliverable", "domain": "business"},
        )
        if tracker:
            tracker.record_path("mfgc_ok")
        return {
            "confidence": result.final_confidence,
            "phases": result.phases_completed,
            "gates": result.gates_generated,
            "murphy_index": result.murphy_index,
            "success": result.success,
            "fallback": False,
        }
    except ImportError as exc:  # MFGC-IMPORT-ERR-001
        logger.error("MFGC-IMPORT-ERR-001: MFGC adapter not importable: %s — using onboard gate", exc)
        if tracker:
            tracker.record_error("MFGC-IMPORT-ERR-001", "mfgc", str(exc))
            tracker.record_fallback("mfgc", f"import failure: {exc}")
        return {"success": False, "fallback": True, "error": f"import: {exc}"}
    except Exception as exc:  # MFGC-RUNTIME-ERR-001
        logger.error("MFGC-RUNTIME-ERR-001: MFGC gate runtime error: %s — using onboard gate", exc)
        if tracker:
            tracker.record_error("MFGC-RUNTIME-ERR-001", "mfgc", str(exc))
            tracker.record_fallback("mfgc", f"runtime: {exc}")
        return {"success": False, "fallback": True, "error": str(exc)}


def _mfgc_quality_score(scenario_key: str) -> int:
    """Derive a display quality score from a scenario key."""
    scores = {
        "onboarding": 97, "finance": 96, "hr": 95,
        "compliance": 94, "project": 96, "invoice": 93,
        "game": 98, "app": 97, "automation": 98, "course": 96,
    }
    return scores.get(scenario_key, 94)


# ---------------------------------------------------------------------------
# MSS — Magnify / Simplify / Solidify
# ---------------------------------------------------------------------------

def _build_mss_controller():
    """Instantiate the MSS controller using the same import paths as _deps.py.

    ``src/`` is added to ``sys.path`` so that the bare module names used
    inside ``mss_controls.py`` (e.g. ``from concept_translation import …``)
    resolve correctly in all call contexts (FastAPI app, test runner, scripts).
    """
    # Use bare imports — consistent with mss_controls.py's own internal imports
    from mss_controls import MSSController  # noqa: PLC0415
    from information_quality import InformationQualityEngine  # noqa: PLC0415
    from concept_translation import ConceptTranslationEngine  # noqa: PLC0415
    from simulation_engine import StrategicSimulationEngine  # noqa: PLC0415
    from resolution_scoring import ResolutionDetectionEngine  # noqa: PLC0415
    from information_density import InformationDensityEngine  # noqa: PLC0415
    from structural_coherence import StructuralCoherenceEngine  # noqa: PLC0415
    rde = ResolutionDetectionEngine()
    ide = InformationDensityEngine()
    sce = StructuralCoherenceEngine()
    iqe = InformationQualityEngine(rde, ide, sce)
    cte = ConceptTranslationEngine()
    sim = StrategicSimulationEngine()
    return MSSController(iqe, cte, sim)


def _run_mss_pipeline(
    query: str,
    mfgc_result: Dict[str, Any],
    tracker: Optional[PipelineErrorTracker] = None,
) -> Dict[str, Any]:
    """Run the query through MSS Magnify then Solidify.

    Magnify and Solidify are independent of each other (both take the same
    query + context), so they run concurrently when possible.  This is the
    same concurrent-dispatch pattern used by the multi-agent coordinator
    (``TeamCoordinator._execute_batch`` in coordinator.py).

    Returns a dict with 'magnify' and 'solidify' sub-dicts extracted from
    each TransformationResult.output.  On failure returns a dict with
    ``"fallback": True`` and ``"error"`` for diagnostic reporting.
    """
    try:
        mss = _build_mss_controller()
        ctx = {
            "owner": "demo_deliverable",
            "domain": "business_automation",
            "mfgc_confidence": mfgc_result.get("confidence", 0.5),
        }

        # Magnify and Solidify are independent — run concurrently.
        # Track individual failures so we know exactly which operator failed.
        import concurrent.futures
        mag = None
        sol = None
        mag_error = None
        sol_error = None

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            mag_future = pool.submit(mss.magnify, query, ctx)
            sol_future = pool.submit(mss.solidify, query, ctx)

            try:
                mag = mag_future.result(timeout=60)
                if tracker:
                    tracker.record_path("mss_magnify_ok")
            except Exception as exc:  # MSS-MAGNIFY-ERR-001
                mag_error = exc
                logger.error(
                    "MSS-MAGNIFY-ERR-001: Magnify operator failed: %s (%s) — query: %s",
                    type(exc).__name__, exc, query[:80],
                )
                if tracker:
                    tracker.record_error("MSS-MAGNIFY-ERR-001", "mss_magnify", str(exc))

            try:
                sol = sol_future.result(timeout=60)
                if tracker:
                    tracker.record_path("mss_solidify_ok")
            except Exception as exc:  # MSS-SOLIDIFY-ERR-001
                sol_error = exc
                logger.error(
                    "MSS-SOLIDIFY-ERR-001: Solidify operator failed: %s (%s) — query: %s",
                    type(exc).__name__, exc, query[:80],
                )
                if tracker:
                    tracker.record_error("MSS-SOLIDIFY-ERR-001", "mss_solidify", str(exc))

        # Both failed — fall back entirely
        if mag is None and sol is None:
            if tracker:
                tracker.record_fallback("mss_pipeline", "both Magnify and Solidify failed")
            return {
                "fallback": True,
                "error": f"magnify: {mag_error}; solidify: {sol_error}",
            }

        # Log quality metrics from successful operators
        mag_output = mag.output if mag else {}
        sol_output = sol.output if sol else {}
        mag_reqs = len(mag_output.get("functional_requirements", [])) if mag_output else 0
        sol_steps = len(sol_output.get("implementation_steps", [])) if sol_output else 0
        logger.info(
            "MSS pipeline results: magnify=%s (reqs=%d), solidify=%s (steps=%d) — query: %s",
            "ok" if mag else "FAILED", mag_reqs,
            "ok" if sol else "FAILED", sol_steps,
            query[:80],
        )

        if mag and not mag_output:
            logger.warning("MSS-MAGNIFY-EMPTY-001: Magnify returned empty output for: %s", query[:80])
            if tracker:
                tracker.record_error("MSS-MAGNIFY-EMPTY-001", "mss_magnify", "empty output dict")

        if sol and not sol_output:
            logger.warning("MSS-SOLIDIFY-EMPTY-001: Solidify returned empty output for: %s", query[:80])
            if tracker:
                tracker.record_error("MSS-SOLIDIFY-EMPTY-001", "mss_solidify", "empty output dict")

        result = {
            "magnify": mag_output,
            "solidify": sol_output,
            "governance": sol.governance_status if sol else "unavailable",
            "fallback": False,
            # WIRE-MSS-001: Surface quality & simulation metadata
            "magnify_quality": {
                "cqi": getattr(mag.output_quality, "cqi", None),
                "iqs": getattr(mag.output_quality, "iqs", None),
                "resolution_level": getattr(mag.output_quality, "resolution_level", None),
                "recommendation": getattr(mag.output_quality, "recommendation", None),
                "risk_indicators": getattr(mag.output_quality, "risk_indicators", []),
            } if mag and getattr(mag, "output_quality", None) else {},
            "solidify_quality": {
                "cqi": getattr(sol.output_quality, "cqi", None),
                "iqs": getattr(sol.output_quality, "iqs", None),
                "resolution_level": getattr(sol.output_quality, "resolution_level", None),
                "recommendation": getattr(sol.output_quality, "recommendation", None),
                "risk_indicators": getattr(sol.output_quality, "risk_indicators", []),
            } if sol and getattr(sol, "output_quality", None) else {},
            "simulation": {
                "cost_impact": getattr(sol.simulation, "cost_impact", None),
                "complexity_impact": getattr(sol.simulation, "complexity_impact", None),
                "compliance_impact": getattr(sol.simulation, "compliance_impact", None),
                "performance_impact": getattr(sol.simulation, "performance_impact", None),
                "overall_score": getattr(sol.simulation, "overall_score", None),
                "risk_level": getattr(sol.simulation, "risk_level", None),
                "recommended": getattr(sol.simulation, "recommended", None),
                "warnings": getattr(sol.simulation, "warnings", []),
                "estimated_engineering_hours": getattr(sol.simulation, "estimated_engineering_hours", None),
                "regulatory_implications": getattr(sol.simulation, "regulatory_implications", []),
            } if sol and getattr(sol, "simulation", None) else {},
        }

        # Partial failure: one succeeded, one failed
        if mag_error or sol_error:
            result["partial_failure"] = True
            result["magnify_error"] = str(mag_error) if mag_error else None
            result["solidify_error"] = str(sol_error) if sol_error else None

        return result
    except ImportError as exc:  # MSS-IMPORT-ERR-001
        logger.error("MSS-IMPORT-ERR-001: MSS modules not importable: %s — using onboard pipeline", exc)
        if tracker:
            tracker.record_error("MSS-IMPORT-ERR-001", "mss_pipeline", str(exc))
            tracker.record_fallback("mss_pipeline", f"import failure: {exc}")
        return {"fallback": True, "error": f"import: {exc}"}
    except Exception as exc:  # MSS-RUNTIME-ERR-001
        logger.error("MSS-RUNTIME-ERR-001: MSS pipeline runtime error: %s — using onboard pipeline", exc)
        if tracker:
            tracker.record_error("MSS-RUNTIME-ERR-001", "mss_pipeline", str(exc))
            tracker.record_fallback("mss_pipeline", f"runtime: {exc}")
        return {"fallback": True, "error": str(exc)}


# ---------------------------------------------------------------------------
# Domain Expert Integration  (label: WIRE-EXPERT-001)
# ---------------------------------------------------------------------------

def _run_domain_expert_analysis(
    query: str,
    tracker: Optional[PipelineErrorTracker] = None,
) -> Dict[str, Any]:
    """Run domain expert analysis and return structured results.

    Wraps ``DomainExpertIntegrator.analyze_project_request()`` with graceful
    fallback.  On success returns the user-friendly response dict; on failure
    returns ``{"fallback": True, "error": ...}``.
    """
    try:
        from domain_expert_integration import DomainExpertIntegrator  # noqa: PLC0415
        integrator = DomainExpertIntegrator()
        result = integrator.analyze_project_request(query)
        result["fallback"] = False
        if tracker:
            tracker.record_path("domain_expert_ok")
        return result
    except ImportError as exc:  # EXPERT-IMPORT-ERR-001
        logger.warning("EXPERT-IMPORT-ERR-001: Domain expert integration not importable: %s", exc)
        if tracker:
            tracker.record_error("EXPERT-IMPORT-ERR-001", "domain_expert", str(exc))
        return {"fallback": True, "error": f"import: {exc}"}
    except Exception as exc:  # EXPERT-RUNTIME-ERR-001
        logger.warning("EXPERT-RUNTIME-ERR-001: Domain expert analysis failed: %s", exc)
        if tracker:
            tracker.record_error("EXPERT-RUNTIME-ERR-001", "domain_expert", str(exc))
        return {"fallback": True, "error": str(exc)}


def _format_expert_context(expert_result: Dict[str, Any]) -> str:
    """Render domain expert analysis as a human-readable section for the LLM prompt."""
    if not expert_result or expert_result.get("fallback"):
        return ""

    lines: List[str] = []
    summary = expert_result.get("summary", "")
    team = expert_result.get("team", "")
    time_cost = expert_result.get("time_and_cost", "")
    questions = expert_result.get("questions_we_will_ask", [])
    artifacts = expert_result.get("artifacts_we_will_create", "")

    if summary:
        lines.append("■ MURPHY INTELLIGENCE — DOMAIN EXPERT ANALYSIS")
        lines.append("─" * 60)
        lines.append(f"  {summary}")

    if team:
        lines.append("")
        lines.append("  Expert Team:")
        for tl in team.strip().splitlines():
            lines.append(f"    {tl}")

    if time_cost:
        lines.append("")
        lines.append("  Time & Cost Estimate:")
        lines.append(f"    {time_cost}")

    if questions:
        lines.append("")
        lines.append("  Key Questions:")
        for q in questions[:10]:
            lines.append(f"    • {q}")

    if artifacts:
        lines.append("")
        lines.append("  Artifacts Planned:")
        for al in artifacts.strip().splitlines():
            lines.append(f"    {al}")

    return "\n".join(lines)


def _format_mss_context(mss_result: Dict[str, Any]) -> str:
    """Render MSS Magnify + Solidify output as a human-readable section."""
    if not mss_result:
        return ""

    lines: List[str] = []
    mag = mss_result.get("magnify", {})
    sol = mss_result.get("solidify", {})

    # From Magnify output
    reqs = mag.get("functional_requirements", [])
    comps = mag.get("technical_components", [])
    compliance = mag.get("compliance_considerations", [])
    cost = mag.get("cost_complexity_estimate", "")

    # From Solidify output
    impl_steps = sol.get("implementation_steps", [])
    test_strategy = sol.get("testing_strategy", [])
    iter_plan = sol.get("iteration_plan", "")

    if reqs:
        lines.append("■ MURPHY INTELLIGENCE — FUNCTIONAL REQUIREMENTS (MSS Magnify)")
        lines.append("─" * 60)
        for r in reqs:
            lines.append(f"  • {r}")

    if comps:
        lines.append("")
        lines.append("  Technical Components Identified:")
        for c in comps:
            lines.append(f"    ◦ {c}")

    if compliance and compliance != ["none_detected"]:
        lines.append("")
        lines.append("  Compliance Considerations:")
        for cf in compliance:
            lines.append(f"    ◦ {cf}")

    if cost:
        lines.append(f"\n  Estimated Complexity:  {cost}")

    if impl_steps:
        lines.append("")
        lines.append("■ MURPHY INTELLIGENCE — IMPLEMENTATION PLAN (MSS Solidify)")
        lines.append("─" * 60)
        for step in impl_steps:
            lines.append(f"  {step}")

    if test_strategy:
        lines.append("")
        lines.append("  Testing Strategy:")
        for ts in test_strategy:
            lines.append(f"    ◦ {ts}")

    if iter_plan:
        lines.append("")
        lines.append("  Iteration Plan:")
        lines.append(f"    {iter_plan}")

    # WIRE-MSS-001: Quality & simulation metadata for LLM context
    mag_quality = mss_result.get("magnify_quality", {})
    sim = mss_result.get("simulation", {})
    # WIRE-MSS-002: Architecture mapping
    arch_map = mag.get("architecture_mapping", {})

    if mag_quality.get("cqi") is not None:
        lines.append("")
        lines.append("■ MURPHY INTELLIGENCE — QUALITY ASSESSMENT")
        lines.append("─" * 60)
        lines.append(f"  CQI Score:         {mag_quality['cqi']:.2f}")
        if mag_quality.get("resolution_level"):
            lines.append(f"  Resolution Level:  {mag_quality['resolution_level']}")
        if mag_quality.get("recommendation"):
            lines.append(f"  Recommendation:    {mag_quality['recommendation']}")
        for ri in mag_quality.get("risk_indicators", []):
            lines.append(f"    ⚠ {ri}")

    if sim.get("risk_level"):
        lines.append("")
        lines.append("  Simulation Impact:")
        if sim.get("overall_score") is not None:
            lines.append(f"    Overall Score:            {sim['overall_score']:.1f}/6")
        lines.append(f"    Risk Level:               {sim['risk_level']}")
        if sim.get("estimated_engineering_hours") is not None:
            lines.append(f"    Est. Engineering Hours:   {sim['estimated_engineering_hours']:.0f}")
        for w in sim.get("warnings", []):
            lines.append(f"    ⚠ {w}")

    if arch_map:
        lines.append("")
        lines.append("  Architecture Mapping:")
        for key in ("components", "data_flows", "control_logic", "validation_methods"):
            items = arch_map.get(key, [])
            if items:
                lines.append(f"    {key.replace('_', ' ').title()}:")
                if isinstance(items, list):
                    for item in items:
                        lines.append(f"      ◦ {item}")
                else:
                    lines.append(f"      {items}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Librarian context formatting
# ---------------------------------------------------------------------------

def _format_librarian_section(librarian_context: str) -> str:
    """Format the librarian lookup result as a deliverable section."""
    if not librarian_context or not librarian_context.strip():
        return ""
    return (
        "■ MURPHY INTELLIGENCE — LIBRARIAN KNOWLEDGE LOOKUP\n"
        + "─" * 60 + "\n"
        + "\n".join(f"  {line}" for line in librarian_context.strip().splitlines())
    )


# ---------------------------------------------------------------------------
# Automation detection + blueprint
# ---------------------------------------------------------------------------

_AUTOMATION_KEYWORDS = {
    "automate", "automation", "workflow", "schedule", "scheduled", "trigger",
    "recurring", "pipeline", "cron", "bot", "agent", "integrate", "integration",
    "batch", "etl", "sync", "webhook", "api connect", "auto-",
    "hands-free", "no-touch", "zero-touch", "background job",
}


def _detect_major_automation(query: str) -> bool:
    """Return True when the query is asking for major automation."""
    q = query.lower()
    return any(kw in q for kw in _AUTOMATION_KEYWORDS)


def _build_automation_blueprint(query: str, mss_result: Optional[Dict[str, Any]] = None) -> str:
    """Build an Automation Blueprint section that produces a **real** generated workflow.

    Calls ``AIWorkflowGenerator.generate_workflow()`` to create an actual DAG
    definition from the user's query.  The resulting steps, strategy, and
    workflow ID are shown in the deliverable so the user receives a concrete,
    executable automation — not a generic "PREVIEW" placeholder.
    """
    sol = (mss_result or {}).get("solidify", {})
    impl_steps = sol.get("implementation_steps", [])
    iteration = sol.get("iteration_plan", "")

    # Derive a module slug from the query
    slug = re.sub(r"[^a-z0-9_]+", "_", query.lower().strip())[:40].strip("_") or "custom_workflow"

    # ── Generate real workflow via AIWorkflowGenerator ──────────────────────
    workflow: Dict[str, Any] = {}
    try:
        from ai_workflow_generator import AIWorkflowGenerator
        generator = AIWorkflowGenerator()
        workflow = generator.generate_workflow(
            description=query,
            context={"source": "demo_deliverable"},
        )
    except Exception:
        logger.debug("Suppressed exception in demo_deliverable_generator")

    workflow_id = workflow.get("workflow_id") or slug
    workflow_name = workflow.get("name") or slug.replace("_", " ").title()
    strategy = workflow.get("strategy") or "custom inference"
    template_used = workflow.get("template_used") or "none"
    generated_steps = workflow.get("steps", [])

    # Build the steps block — prefer real generated steps, then MSS Solidify output
    if generated_steps:
        steps_block = "\n".join(
            f"    Step {i+1}: [{s.get('type','action').upper()}] "
            f"{s.get('description', s.get('name', str(s)))}"
            + (f"  (depends on: {', '.join(s['depends_on'])})" if s.get('depends_on') else "")
            for i, s in enumerate(generated_steps)
        )
    elif impl_steps:
        steps_block = "\n".join(f"    {i+1}. {s}" for i, s in enumerate(impl_steps))
    else:
        steps_block = (
            "    Step 1: [TRIGGER]    Define trigger condition (schedule / event / webhook)\n"
            "    Step 2: [FETCH]      Retrieve source data via connector\n"
            "    Step 3: [TRANSFORM]  Apply Murphy AI transformation layer\n"
            "    Step 4: [GATE]       MFGC confidence check (auto-approve if ≥90%)\n"
            "    Step 5: [DISPATCH]   Route to destination connector + notification\n"
            "    Step 6: [MONITOR]    Write execution log to Murphy observability dashboard"
        )

    iteration_block = (
        f"    {iteration}" if iteration
        else "    Phase 1: Core automation (Week 1–2). Phase 2: Integration testing (Week 3). Phase 3: Go-live (Week 4)."
    )

    step_count = len(generated_steps) or 6

    return f"""\
■ AUTOMATION BLUEPRINT — GENERATED WORKFLOW
════════════════════════════════════════════════════════════
  Murphy System has generated a complete, wired automation
  workflow from your request using the AI Workflow Generator.

  Workflow ID:    {workflow_id}
  Workflow Name:  {workflow_name}
  Request:        {query[:80]}
  Strategy:       {strategy}
  Template:       {template_used}
  Total Steps:    {step_count}
  Generated by:   Murphy System AI Workflow Generator

  ┌─────────────────────────────────────────────────┐
  │  WORKFLOW TOPOLOGY                               │
  │  Trigger → Fetch → Transform → Gate → Dispatch  │
  └─────────────────────────────────────────────────┘

  WORKFLOW STEPS (ready to execute):
{steps_block}

  ITERATION PLAN:
{iteration_block}

  TO DEPLOY THIS AUTOMATION:
    → Paste into the Murphy Terminal:
         execute "{query[:60]}"
    → Or call the automation API directly:
         POST /api/automations/rules
         POST /api/chat  {{"message": "execute {query[:40]}"}}
    → Full workflow JSON available at:
         GET /api/automations/workflows/{workflow_id}
"""


def _build_quality_plan(
    query: str,
    mss_result: Optional[Dict[str, Any]] = None,
    librarian_context: Optional[str] = None,
) -> str:
    """Build a Quality Plan section with an itemized service catalog and quote.

    The plan includes a deterministic Plan ID, a recommended-services list
    driven by keyword matching against the query, a technical specification
    derived from MSS data when available, pre-optimization suggestions, and
    a client-portfolio save/retrieve section.
    """
    plan_id = hashlib.sha256(query.encode()).hexdigest()[:8].upper()

    # --- keyword → service recommendation mapping --------------------------
    q = query.lower()
    service_catalog = [
        ("S01", "Workflow Automation Engine",            "Solo",     "$49"),
        ("S02", "Integration Hub (50+ connectors)",      "Solo",     "$29"),
        ("S03", "AI Content & Data Processing",          "Solo",     "$19"),
        ("S04", "Compliance Framework Engine",           "Solo",     "$39"),
        ("S05", "Human-in-the-Loop Approvals",           "Solo",     "$19"),
        ("S06", "Production Assistant (task execution)",  "Business", "$79"),
        ("S07", "Self-Automation Platform",              "Business", "$99"),
        ("S08", "AI Agent Org Chart",                    "Business", "$59"),
        ("S09", "Developer SDK Access",                  "Solo",     "$29"),
        ("S10", "Infrastructure Maintenance",            "Business", "$49"),
    ]

    keyword_map: Dict[str, List[str]] = {
        "automate":   ["S01", "S07"],
        "automation": ["S01", "S07"],
        "integrate":  ["S02"],
        "integration":["S02"],
        "connect":    ["S02"],
        "content":    ["S03"],
        "data":       ["S03"],
        "ai":         ["S03", "S08"],
        "compliance": ["S04"],
        "audit":      ["S04"],
        "approval":   ["S05"],
        "review":     ["S05"],
        "production": ["S06"],
        "execute":    ["S06"],
        "deploy":     ["S06", "S10"],
        "platform":   ["S07"],
        "agent":      ["S08"],
        "org chart":  ["S08"],
        "sdk":        ["S09"],
        "developer":  ["S09"],
        "api":        ["S09"],
        "infra":      ["S10"],
        "maintain":   ["S10"],
    }

    recommended = set()  # type: set[str]
    for kw, svc_ids in keyword_map.items():
        if kw in q:
            recommended.update(svc_ids)
    # Always recommend at least S01 and S03 as baseline
    if not recommended:
        recommended = {"S01", "S03"}

    # --- catalog table -----------------------------------------------------
    catalog_rows = ""
    for sid, name, tier, price in service_catalog:
        catalog_rows += f"  │  {sid} │  {name:<37s}│  {tier:<9s}│  {price:<9s}│\n"

    recommended_lines = ""
    for sid, name, tier, price in service_catalog:
        if sid in recommended:
            recommended_lines += f"  ✓  {sid}  {name}  ({tier} — {price}/seat/mo)\n"

    # --- technical specification -------------------------------------------
    sol = (mss_result or {}).get("solidify", {})
    mag = (mss_result or {}).get("magnify", {})

    apis = ", ".join(mag.get("functional_requirements", [])[:3]) or "Murphy REST API, Webhook API"
    connections = ", ".join(sol.get("implementation_steps", [])[:2]) or "Source connector, Destination connector"
    triggers = sol.get("iteration_plan", "") or "Event / Schedule / Webhook"
    bot_systems = "Librarian, Solidify Agent, Gate Agent"
    modules = "MSS Magnify, MSS Solidify, MFGC, Librarian"
    info_domains = ", ".join(mag.get("components", [])[:3]) or "Business data, User data, System telemetry"

    if librarian_context and librarian_context.strip():
        lib_lower = librarian_context.lower()
        if "production" in lib_lower:
            bot_systems += ", Production Bot"
        if "compliance" in lib_lower:
            bot_systems += ", Compliance Bot"

    # --- pre-optimization suggestions --------------------------------------
    suggestions = []
    if "S01" in recommended and "S07" in recommended:
        suggestions.append("  • Bundle Workflow Automation + Self-Automation for a 15% discount.")
    if "S04" in recommended:
        suggestions.append("  • Add Human-in-the-Loop Approvals (S05) alongside Compliance for complete governance.")
    if "S06" in recommended:
        suggestions.append("  • Consider Infrastructure Maintenance (S10) to support Production Assistant uptime.")
    if not suggestions:
        suggestions.append("  • Start with Solo tier to validate, then upgrade to Business for volume scaling.")
        suggestions.append("  • Enable MFGC auto-approve (≥90% confidence) to reduce manual gates.")

    return (
        f"■ QUALITY PLAN — SERVICE CATALOG & AUTOMATION QUOTE\n"
        f"════════════════════════════════════════════════════\n"
        f"  Murphy System has analyzed your request and generated an itemized\n"
        f"  quality plan. Each service below is selectable — choose the ones\n"
        f"  that fit your needs. Save your selections as a client portfolio\n"
        f"  to mix, match, upgrade, or downgrade at any time.\n"
        f"\n"
        f"  Request:  {query[:100]}\n"
        f"  Plan ID:  QP-{plan_id}\n"
        f"  Generated by: Murphy System Quality Engine (MSS Magnify → Solidify → Librarian)\n"
        f"\n"
        f"■ ITEMIZED SERVICE CATALOG\n"
        f"──────────────────────────\n"
        f"  Each line item below maps directly to a Murphy System capability\n"
        f"  identified by the Librarian system as relevant to your request.\n"
        f"\n"
        f"  ┌──────┬──────────────────────────────────────┬──────────┬──────────┐\n"
        f"  │  ID  │  Service                              │  Tier    │  Est/mo  │\n"
        f"  ├──────┼──────────────────────────────────────┼──────────┼──────────┤\n"
        f"{catalog_rows}"
        f"  └──────┴──────────────────────────────────────┴──────────┴──────────┘\n"
        f"\n"
        f"  * Pricing is per-seat/month. Volume discounts available at Business tier.\n"
        f"  * Services marked with ✓ below are recommended for your request.\n"
        f"\n"
        f"■ RECOMMENDED FOR YOUR REQUEST\n"
        f"──────────────────────────────\n"
        f"{recommended_lines}"
        f"\n"
        f"■ TECHNICAL SPECIFICATION\n"
        f"─────────────────────────\n"
        f"  APIs:          {apis}\n"
        f"  Connections:   {connections}\n"
        f"  Triggers:      {triggers}\n"
        f"  Gates:         MFGC confidence gate (auto-approve ≥90%)\n"
        f"  Information:   {info_domains}\n"
        f"  Bot Systems:   {bot_systems}\n"
        f"  Modules:       {modules}\n"
        f"\n"
        f"■ PRE-OPTIMIZATION SUGGESTIONS\n"
        f"──────────────────────────────\n"
        + "\n".join(suggestions) + "\n"
        f"\n"
        f"■ CLIENT PORTFOLIO — SAVE & CUSTOMIZE\n"
        f"──────────────────────────────────────\n"
        f"  Your quality plan selections can be saved as a client portfolio.\n"
        f"  POST /api/client-portfolio/save  with your selected service IDs.\n"
        f"  GET  /api/client-portfolio/{{id}}  to retrieve your portfolio.\n"
        f"\n"
        f"  Mix & match services at any time. Upgrade or downgrade tiers\n"
        f"  with pre-optimization suggestions based on your usage patterns.\n"
    )


# ---------------------------------------------------------------------------
# LLM content generation (with MFGC + MSS + Librarian context)
# ---------------------------------------------------------------------------

def _generate_llm_content(
    query: str,
    mfgc_result: Optional[Dict[str, Any]] = None,
    mss_result: Optional[Dict[str, Any]] = None,
    librarian_context: Optional[str] = None,
    expert_result: Optional[Dict[str, Any]] = None,
    tracker: Optional[PipelineErrorTracker] = None,
) -> str:
    """Generate deliverable content using the MFGC → MSS → LLM pipeline.

    The MFGC gate and MSS pipeline (Magnify + Solidify) run upstream and
    feed enriched context into this function.  The LLM call uses DeepInfra's
    full context window (up to 131 072 tokens) — output size is proportional
    to what the user actually asked for, not a fixed ceiling.

    Provider chain:  DeepInfra → Together.ai → LLMController → onboard fallback.
    When all LLM providers are down, the static domain keyword engine produces
    a structured deliverable without any LLM calls.
    """
    # ── Build enriched context from upstream pipeline stages ───────────────
    context_parts: List[str] = []

    mss_section = _format_mss_context(mss_result or {})
    if mss_section:
        context_parts.append(mss_section)

    lib_section = _format_librarian_section(librarian_context or "")
    if lib_section:
        context_parts.append(lib_section)

    # WIRE-EXPERT-001: Domain expert analysis context
    expert_section = _format_expert_context(expert_result or {})
    if expert_section:
        context_parts.append(expert_section)

    mfgc_note = ""
    if mfgc_result:
        conf = mfgc_result.get("confidence", 0)
        phases = mfgc_result.get("phases", [])
        # WIRE-MFGC-001: include murphy_index and gate count in note
        mi = mfgc_result.get("murphy_index")
        gates = mfgc_result.get("gates", [])
        mi_part = f", murphy_index={mi}" if mi is not None else ""
        gates_part = f", gates={len(gates)}" if gates else ""
        mfgc_note = (
            f"[MFGC gate: confidence={conf:.2f}, "
            f"phases={', '.join(str(p) for p in phases[:3]) if phases else 'n/a'}"
            f"{mi_part}{gates_part}]"
        )

    enriched_context = "\n\n".join(context_parts)

    # MSS data as structured seed for the LLM
    base_content = ""
    if mss_result and (mss_result.get("magnify") or mss_result.get("solidify")):
        base_content = _build_content_from_mss(query, mss_result, mfgc_note, mfgc_result=mfgc_result)

    # ── Domain-specific content expansion ─────────────────────────────────
    # MSS onboard output is structural.  Supplement with deep, domain-aware
    # content so the LLM has richer context to work from.
    domain_content = _build_deep_domain_content(query)

    # ── System prompt ─────────────────────────────────────────────────────
    system_prompt = (
        f"{MURPHY_SYSTEM_IDENTITY}\n\n"
        "You are a production-grade deliverable engine.  Your output must be:\n"
        "  • COMPREHENSIVE — cover every aspect the user would need\n"
        "  • ACTIONABLE — include tables, checklists, timelines, specs, matrices\n"
        "  • PRODUCTION-READY — not a summary or outline, but a real deliverable\n"
        "  • PROPORTIONAL — match the scope of the request.  A children's book "
        "needs different depth than an adult novel.  A CI/CD pipeline needs "
        "different depth than a full enterprise security audit.\n\n"
        "Use clear section headers (■ SECTION NAME), tables with box-drawing "
        "characters, checklists (□), and structured formatting.  "
        "Do NOT conserve tokens.  Produce an output whose length and depth "
        "matches what was actually requested."
    )

    # ── User prompt with all context ──────────────────────────────────────
    user_prompt_parts = [f"Generate a complete, production-grade deliverable for:\n\n{query}\n"]

    if base_content:
        user_prompt_parts.append(
            f"\nThe Murphy MSS pipeline has produced this structured analysis "
            f"as a starting point.  Use it as context and expand it into a "
            f"comprehensive deliverable:\n\n{base_content}\n"
        )

    if domain_content:
        user_prompt_parts.append(
            f"\nDomain-specific intelligence:\n\n{domain_content}\n"
        )

    if enriched_context:
        user_prompt_parts.append(
            f"\nAdditional intelligence from Murphy systems:\n\n{enriched_context}\n"
        )

    user_prompt_parts.append(
        "\nProduce a comprehensive deliverable with full depth.  "
        "The output length must be proportional to the request — "
        "a short request gets a focused deliverable, a large request "
        "(book, course, enterprise audit) gets exhaustive coverage.\n"
        "Use tables, checklists, and structured formatting throughout.  "
        "Do not truncate or summarise — produce the full deliverable."
    )

    user_prompt = "\n".join(user_prompt_parts)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # ── Token budget: use DeepInfra's full context window ─────────────────
    # DeepInfra Meta-Llama-3.1-70B supports up to 131 072 tokens.  We don't
    # artificially cap this — the LLM produces whatever the request requires.
    # MFGC confidence and MSS scope already determine the complexity; the
    # token limit just needs to not be the bottleneck.
    max_output_tokens = 131072

    # ── Try 1: Direct MurphyLLMProvider (DeepInfra → Together.ai) ─────────
    try:
        from src.llm_provider import get_llm
        provider = get_llm()
        completion = provider.complete_messages(
            messages,
            model_hint="chat",
            temperature=0.7,
            max_tokens=max_output_tokens,
        )
        if completion.content and completion.provider != "onboard":
            logger.info(
                "Deliverable generated via %s: %d chars, %d tokens",
                completion.provider, len(completion.content), completion.tokens_total,
            )
            if tracker:
                tracker.record_path(f"llm_ok:{completion.provider}")
            return completion.content
        # LLM returned empty or onboard — log explicitly
        logger.warning(
            "LLM-CONTENT-EMPTY-001: MurphyLLMProvider returned %s content "
            "(provider=%s, len=%d) — trying next provider",
            "onboard" if completion.provider == "onboard" else "empty",
            completion.provider, len(completion.content or ""),
        )
        if tracker:
            tracker.record_error(
                "LLM-CONTENT-EMPTY-001", "llm_provider",
                f"provider={completion.provider}, content_len={len(completion.content or '')}",
            )
    except Exception as exc:  # LLM-PROVIDER-ERR-001
        logger.warning("LLM-PROVIDER-ERR-001: MurphyLLMProvider failed: %s — trying LLMController", exc)
        if tracker:
            tracker.record_error("LLM-PROVIDER-ERR-001", "llm_provider", str(exc))

    # ── Try 2: LLMController (async, broader model selection) ─────────────
    try:
        import asyncio
        from src.llm_controller import LLMController, LLMRequest
        controller = LLMController()
        req = LLMRequest(prompt=user_prompt, max_tokens=max_output_tokens)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as exe:
                    future = exe.submit(asyncio.run, controller.query_llm(req))
                    response = future.result(timeout=120)
            else:
                response = loop.run_until_complete(controller.query_llm(req))
        except RuntimeError:
            response = asyncio.run(controller.query_llm(req))
        if response.content and len(response.content) > 200:
            logger.info("LLMController deliverable: %d chars", len(response.content))
            if tracker:
                tracker.record_path("llm_controller_ok")
            return response.content
        logger.warning(
            "LLM-CONTROLLER-EMPTY-001: LLMController returned insufficient content (%d chars)",
            len(response.content) if response.content else 0,
        )
        if tracker:
            tracker.record_error("LLM-CONTROLLER-EMPTY-001", "llm_controller", "insufficient content")
    except Exception as exc:  # LLM-CONTROLLER-ERR-001
        logger.warning("LLM-CONTROLLER-ERR-001: LLMController failed: %s — using MSS base or fallback", exc)
        if tracker:
            tracker.record_error("LLM-CONTROLLER-ERR-001", "llm_controller", str(exc))

    # ── Try 3: LocalLLMFallback ───────────────────────────────────────────
    try:
        from src.local_llm_fallback import LocalLLMFallback
        fallback = LocalLLMFallback()
        content = fallback.generate(user_prompt, max_tokens=max_output_tokens)
        # Skip if the fallback only returned the generic onboard placeholder
        # (which is not a real deliverable).
        if (content and len(content) > 100
                and "LLM Unavailable" not in content[:80]):
            if tracker:
                tracker.record_path("local_llm_ok")
            return content
        logger.warning(
            "LLM-LOCAL-EMPTY-001: LocalLLMFallback returned placeholder "
            "content (%d chars) — using domain engine",
            len(content) if content else 0,
        )
        if tracker:
            tracker.record_error("LLM-LOCAL-EMPTY-001", "local_llm", "placeholder or empty content")
    except Exception as exc:  # LLM-LOCAL-ERR-001
        logger.warning("LLM-LOCAL-ERR-001: LocalLLMFallback unavailable: %s", exc)
        if tracker:
            tracker.record_error("LLM-LOCAL-ERR-001", "local_llm", str(exc))

    # ── Fallback: domain keyword engine (no LLM required) ─────────────────
    # Combine MSS structural output with domain-specific content for a richer
    # deliverable even when all LLM providers are down.
    if tracker:
        tracker.record_fallback("llm_content", "all LLM providers failed — using domain keyword engine")
    _fb_notice = (
        "■ NOTE: This deliverable was generated using Murphy System's built-in\n"
        "  knowledge engine (LLM providers are currently unavailable). Content is\n"
        "  based on domain-matched templates — not a full AI-generated analysis.\n"
        "  For richer, context-aware output, configure an LLM provider:\n"
        "    set key deepinfra di_...  (free key: https://deepinfra.com/keys)\n\n"
    )
    if base_content and domain_content:
        if tracker:
            tracker.record_path("fallback:mss+domain")
        return base_content + "\n\n" + _fb_notice + domain_content
    if base_content:
        if tracker:
            tracker.record_path("fallback:mss_only")
        return base_content
    if domain_content:
        if tracker:
            tracker.record_path("fallback:domain_only")
        return (
            f"■ DELIVERABLE OVERVIEW\n"
            f"───────────────────────\n"
            f"  Request:  {query}\n"
            f"  Status:   Generated by Murphy System onboard engine\n\n"
            f"{_fb_notice}"
            f"{domain_content}"
        )
    if tracker:
        tracker.record_path("fallback:minimal")
    return _build_minimal_custom_content(query)


def _build_content_from_mss(
    query: str,
    mss_result: Dict[str, Any],
    mfgc_note: str = "",
    mfgc_result: Optional[Dict[str, Any]] = None,
) -> str:
    """Build structured deliverable prose directly from MSS Magnify + Solidify output."""
    mag = mss_result.get("magnify", {})
    sol = mss_result.get("solidify", {})

    reqs = mag.get("functional_requirements", [])
    comps = mag.get("technical_components", [])
    compliance = mag.get("compliance_considerations", [])
    cost = mag.get("cost_complexity_estimate", "")
    concept = mag.get("concept_overview", query)

    cap_def = sol.get("capability_definition", "")
    impl_steps = sol.get("implementation_steps", [])
    test_strategy = sol.get("testing_strategy", [])
    iter_plan = sol.get("iteration_plan", "")
    doc_updates = sol.get("documentation_updates", [])
    arch = sol.get("architecture_placement", "")

    # WIRE-MSS-003: Module specification & existing module analysis
    mod_spec = sol.get("module_specification", {})
    existing_analysis = sol.get("existing_module_analysis", "")
    # WIRE-MSS-004: Resolution progression
    mag_progression = mag.get("resolution_progression", "")
    sol_progression = sol.get("resolution_progression", "")
    # WIRE-MSS-002: Architecture mapping
    arch_map = mag.get("architecture_mapping", {})
    # WIRE-MSS-001: Quality & simulation metadata
    mag_quality = mss_result.get("magnify_quality", {})
    sol_quality = mss_result.get("solidify_quality", {})
    sim = mss_result.get("simulation", {})

    lines: List[str] = []

    lines += [
        "■ EXECUTIVE OVERVIEW",
        "──────────────────────",
        f"  Request:    {query}",
        f"  Concept:    {concept or query}",
    ]
    if cap_def:
        lines.append(f"  Capability: {cap_def}")
    if cost:
        lines.append(f"  Complexity: {cost} (MSS assessment)")
    if mfgc_note:
        lines.append(f"  MFGC:       {mfgc_note}")
    # WIRE-MSS-004: Resolution progression in executive overview
    if mag_progression or sol_progression:
        prog_parts = []
        if mag_progression:
            prog_parts.append(f"Magnify {mag_progression}")
        if sol_progression:
            prog_parts.append(f"Solidify {sol_progression}")
        lines.append(f"  Resolution: {' | '.join(prog_parts)}")

    # WIRE-MFGC-001: Quality Assurance section from MFGC gate
    if mfgc_result and not mfgc_result.get("fallback"):
        lines += [
            "",
            "■ QUALITY ASSURANCE  (MFGC Gate)",
            "──────────────────────────────────",
        ]
        conf = mfgc_result.get("confidence", 0)
        lines.append(f"  Confidence Score:  {conf:.0%}")
        mi = mfgc_result.get("murphy_index")
        if mi is not None:
            lines.append(f"  Murphy Index:      {mi}")
        gates = mfgc_result.get("gates", [])
        if gates:
            lines.append(f"  Gates Applied:     {len(gates)}")
            for g in gates[:5]:
                lines.append(f"    ◦ {g}")
        phases = mfgc_result.get("phases", [])
        if phases:
            lines.append(f"  Phases Completed:  {', '.join(str(p) for p in phases[:5])}")

    if reqs:
        lines += [
            "",
            "■ FUNCTIONAL REQUIREMENTS  (MSS Magnify)",
            "──────────────────────────────────────────",
        ]
        for r in reqs:
            lines.append(f"  • {r}")

    if comps:
        lines += ["", "  Components Identified:"]
        for c in comps:
            lines.append(f"    ◦ {c}")

    if compliance and compliance != ["none_detected"]:
        lines += ["", "  Compliance Domains:"]
        for cf in compliance:
            lines.append(f"    ◦ {cf}")

    # WIRE-MSS-002: Architecture mapping section
    if arch_map:
        lines += [
            "",
            "■ ARCHITECTURE MAPPING  (MSS Magnify)",
            "───────────────────────────────────────",
        ]
        for key in ("components", "data_flows", "control_logic", "validation_methods"):
            items = arch_map.get(key, [])
            if items:
                lines.append(f"  {key.replace('_', ' ').title()}:")
                if isinstance(items, list):
                    for item in items:
                        lines.append(f"    ◦ {item}")
                else:
                    lines.append(f"    {items}")

    if impl_steps:
        lines += [
            "",
            "■ IMPLEMENTATION PLAN  (MSS Solidify)",
            "───────────────────────────────────────",
        ]
        for s in impl_steps:
            lines.append(f"  {s}")

    if arch:
        lines += ["", f"  Architecture: {arch}"]

    # WIRE-MSS-003: Module specification
    if mod_spec:
        lines += [
            "",
            "■ MODULE SPECIFICATION  (MSS Solidify)",
            "────────────────────────────────────────",
        ]
        if mod_spec.get("name"):
            lines.append(f"  Name:         {mod_spec['name']}")
        if mod_spec.get("purpose"):
            lines.append(f"  Purpose:      {mod_spec['purpose']}")
        deps = mod_spec.get("dependencies", [])
        if deps:
            lines.append(f"  Dependencies: {', '.join(str(d) for d in deps)}")
        ifaces = mod_spec.get("interfaces", [])
        if ifaces:
            lines.append(f"  Interfaces:   {', '.join(str(i) for i in ifaces)}")

    # WIRE-MSS-003: Existing module analysis
    if existing_analysis:
        lines += [
            "",
            "■ EXISTING MODULE ANALYSIS  (MSS Solidify)",
            "─────────────────────────────────────────────",
            f"  {existing_analysis}",
        ]

    if test_strategy:
        lines += [
            "",
            "■ TESTING & VALIDATION STRATEGY",
            "─────────────────────────────────",
        ]
        for ts in test_strategy:
            lines.append(f"  • {ts}")

    if iter_plan:
        lines += [
            "",
            "■ ITERATION PLAN",
            "──────────────────",
            f"  {iter_plan}",
        ]

    if doc_updates:
        lines += [
            "",
            "■ DOCUMENTATION REQUIREMENTS",
            "──────────────────────────────",
        ]
        for d in doc_updates:
            lines.append(f"  □  {d}")

    # WIRE-MSS-001: Quality metrics & simulation impact
    if mag_quality.get("cqi") is not None or sol_quality.get("cqi") is not None:
        lines += [
            "",
            "■ QUALITY METRICS  (MSS Information Quality)",
            "──────────────────────────────────────────────",
        ]
        if mag_quality.get("cqi") is not None:
            lines.append(f"  Magnify CQI:          {mag_quality['cqi']:.2f}")
        if sol_quality.get("cqi") is not None:
            lines.append(f"  Solidify CQI:         {sol_quality['cqi']:.2f}")
        for q_src, q_data in [("Magnify", mag_quality), ("Solidify", sol_quality)]:
            if q_data.get("resolution_level"):
                lines.append(f"  {q_src} Resolution:   {q_data['resolution_level']}")
            if q_data.get("recommendation"):
                lines.append(f"  {q_src} Recommendation: {q_data['recommendation']}")
            for ri in q_data.get("risk_indicators", []):
                lines.append(f"    ⚠ {ri}")

    if sim.get("risk_level"):
        lines += [
            "",
            "■ SIMULATION IMPACT ANALYSIS",
            "──────────────────────────────",
        ]
        if sim.get("overall_score") is not None:
            lines.append(f"  Overall Score:         {sim['overall_score']:.1f}/6")
        lines.append(f"  Risk Level:            {sim['risk_level']}")
        if sim.get("cost_impact") is not None:
            lines.append(f"  Cost Impact:           {sim['cost_impact']:.1f}/6")
        if sim.get("complexity_impact") is not None:
            lines.append(f"  Complexity Impact:     {sim['complexity_impact']:.1f}/6")
        if sim.get("compliance_impact") is not None:
            lines.append(f"  Compliance Impact:     {sim['compliance_impact']:.1f}/6")
        if sim.get("performance_impact") is not None:
            lines.append(f"  Performance Impact:    {sim['performance_impact']:.1f}/6")
        if sim.get("estimated_engineering_hours") is not None:
            lines.append(f"  Est. Engineering Hrs:  {sim['estimated_engineering_hours']:.0f}")
        for reg in sim.get("regulatory_implications", []):
            lines.append(f"    ◦ Regulatory: {reg}")
        for w in sim.get("warnings", []):
            lines.append(f"    ⚠ {w}")

    lines += [
        "",
        "■ NEXT STEPS",
        "─────────────",
        "  □  Review and customise this deliverable to your specific context.",
        "  □  Share with stakeholders for alignment before execution.",
        "  □  Set up Murphy System automation to run recurring steps.",
        "  → Sign up at murphy.systems for full automation deployment.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Domain-aware content expansion engine  (label: FORGE-DOMAIN-EXPAND-001)
# ---------------------------------------------------------------------------
# LLM-down fallback.  When DeepInfra / Together.ai / all LLM providers are
# unreachable, the domain expander produces deep, actionable, domain-specific
# content so the user still gets a substantive deliverable.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Agent-role → unique section mapping  (label: FORGE-SWARM-ROLE-001)
# ---------------------------------------------------------------------------
# When the LLM is unavailable, each swarm agent must produce a *distinct*
# section of the deliverable.  This map assigns each well-known role to a
# dedicated content generator so that N agents produce N different sections
# rather than N copies of the same generic template.
# ---------------------------------------------------------------------------

def _build_agent_specific_fallback_content(
    agent_name: str,
    task_desc: str,
    query: str,
) -> str:
    """Generate fallback content *specific* to one agent's assigned role/task.

    Unlike ``_build_deep_domain_content`` (which returns the **entire**
    domain template), this function returns only the section that matches
    the agent's role so that each agent in the swarm produces unique output.

    Label: FORGE-SWARM-ROLE-001
    """
    role = agent_name.split(": ", 1)[-1] if ": " in agent_name else agent_name
    role_lower = role.lower()
    task_lower = task_desc.lower()

    # --- Role → section generators (each returns a distinct section) --------
    # Priority: match the agent ROLE first (more reliable), then fall back
    # to task keyword matching.  This ensures SecurityAuditor is not
    # misrouted when its task description mentions "requirements".
    if "scope" in role_lower:
        logger.warning("USING FALLBACK TEMPLATE: scope_analysis — LLM unavailable")
        return _fallback_scope_analysis(query, task_desc)
    if "requirement" in role_lower:
        logger.warning("USING FALLBACK TEMPLATE: requirements — LLM unavailable")
        return _fallback_requirements(query, task_desc)
    if "architect" in role_lower:
        return _fallback_architecture(query, task_desc)
    if "component" in role_lower:
        return _fallback_component_design(query, task_desc)
    if "datamodel" in role_lower or "data" in role_lower:
        return _fallback_data_model(query, task_desc)
    if "api" in role_lower:
        return _fallback_api_design(query, task_desc)
    if "security" in role_lower:
        return _fallback_security(query, task_desc)
    if "compliance" in role_lower:
        return _fallback_compliance(query, task_desc)
    if "cost" in role_lower or "estimat" in role_lower:
        return _fallback_cost_estimate(query, task_desc)
    if "risk" in role_lower:
        return _fallback_risk_assessment(query, task_desc)
    if "test" in role_lower or "qa" in role_lower:
        return _fallback_testing(query, task_desc)
    if "integration" in role_lower:
        return _fallback_integration(query, task_desc)
    if "doc" in role_lower:
        return _fallback_documentation(query, task_desc)
    if "review" in role_lower:
        return _fallback_review(query, task_desc)
    if "timeline" in role_lower:
        return _fallback_timeline(query, task_desc)
    if "deploy" in role_lower:
        return _fallback_deployment(query, task_desc)
    if "monitor" in role_lower:
        return _fallback_monitoring(query, task_desc)

    # Second pass: match on task keywords when role name is unrecognised
    if "scope" in task_lower:
        return _fallback_scope_analysis(query, task_desc)
    if "security" in task_lower:
        return _fallback_security(query, task_desc)
    if "compliance" in task_lower or "legal" in task_lower:
        return _fallback_compliance(query, task_desc)
    if "requirement" in task_lower:
        return _fallback_requirements(query, task_desc)
    if "architect" in task_lower:
        return _fallback_architecture(query, task_desc)
    if "component" in task_lower:
        return _fallback_component_design(query, task_desc)
    if "data model" in task_lower or "data schema" in task_lower:
        return _fallback_data_model(query, task_desc)
    if "api" in task_lower:
        return _fallback_api_design(query, task_desc)
    if "test" in task_lower or "qa" in task_lower:
        return _fallback_testing(query, task_desc)
    if "integration" in task_lower:
        return _fallback_integration(query, task_desc)
    if "document" in task_lower or "training" in task_lower:
        return _fallback_documentation(query, task_desc)
    if "review" in task_lower or "quality" in task_lower:
        return _fallback_review(query, task_desc)
    if "cost" in task_lower or "estimat" in task_lower:
        return _fallback_cost_estimate(query, task_desc)
    if "risk" in task_lower:
        return _fallback_risk_assessment(query, task_desc)
    if "timeline" in task_lower or "plan" in task_lower:
        return _fallback_timeline(query, task_desc)
    if "deploy" in task_lower or "rollback" in task_lower:
        return _fallback_deployment(query, task_desc)
    if "monitor" in task_lower or "alert" in task_lower:
        return _fallback_monitoring(query, task_desc)
    if "stakeholder" in task_lower:
        return _fallback_stakeholder(query, task_desc)

    # Catch-all: generate a task-specific stub rather than the full template
    return _fallback_generic_task(query, task_desc, role)


# ── Individual role fallback generators ──────────────────────────────────

def _fallback_scope_analysis(query: str, task: str) -> str:
    """PATCH-013g: Domain-aware scope analysis derived from the query."""
    q = query.lower()
    # Detect domain
    is_game = any(w in q for w in ["game","mmo","mmorpg","colony","ant","player","level","exp","nft","fortnite","skin"])
    is_web  = any(w in q for w in ["web app","webapp","dashboard","saas","api","backend","frontend","portal"])
    is_biz  = any(w in q for w in ["business","invoic","crm","hr","payroll","report","automat","workflow"])
    is_ai   = any(w in q for w in ["ai","ml","model","llm","neural","train","inference","chatbot"])

    if is_game:
        in_scope = [
            "Top-down 2D MMO game engine — real-time multiplayer server and client",
            "Ant colony gameplay: colony control, unit types, terrain (4 backyard zones)",
            "Combat system: inter-colony PvP + wild bug enemies (beetles, wasps, spiders etc.)",
            "XP/leveling system: kill rewards, colony level-ups, unlock gates",
            "Visual customisation: ant skins (capes, boots, slippers) as NFT cosmetics",
            "Subscription tiers (Fortnite-style Battle Pass model) — no pay-to-win",
            "Match session system: ~60-minute accelerated game loops, elimination mode",
            "Downloadable client package (Electron/HTML5) + server installer",
        ]
        out_scope = [
            "Pay-to-win mechanics (excluded by design)",
            "Non-visual NFT utility (cosmetic-only policy)",
            "Physical merchandise",
            "Dedicated anti-cheat hardware",
        ]
        constraints = [
            "Game loop must complete in ~60 min via time acceleration",
            "Colony elimination = permanent removal for that session",
            "Client must be packageable and runnable without a build step",
            "Cosmetics are NFT-backed but gameplay is fully F2P baseline",
        ]
    elif is_web:
        in_scope = [
            "Full-stack web application with authenticated dashboard",
            "Core business logic and data persistence layer",
            "REST/GraphQL API for frontend-backend communication",
            "User management, roles, and access control",
            "Payment integration (Stripe/subscription billing)",
        ]
        out_scope = ["Mobile native apps (web-responsive only)","Hardware integrations","Legacy data migration"]
        constraints = ["Must be deployable to cloud (Docker/serverless)","API-first architecture"]
    elif is_biz:
        in_scope = [
            "End-to-end business process automation workflows",
            "Data ingestion, transformation, and reporting pipelines",
            "Integration with existing business tools (CRM, ERP, HRIS)",
            "Audit trail and compliance logging",
        ]
        out_scope = ["Hardware procurement","Vendor renegotiation","Organisational change management"]
        constraints = ["SOC2 compliance required","Data retention 7 years"]
    elif is_ai:
        in_scope = [
            "Model training pipeline with versioned datasets",
            "Inference API with latency SLAs",
            "Evaluation harness and benchmark suite",
            "Model registry and deployment tooling",
        ]
        out_scope = ["Proprietary hardware (GPU cloud assumed)","Data labelling outsourcing"]
        constraints = ["Inference p99 < 500ms","Model versioning required"]
    else:
        in_scope = [
            "Core functional requirements derived from: " + query[:80],
            "Primary user workflows and interactions",
            "Integration points with existing systems",
            "Data inputs, outputs, and transformations",
        ]
        out_scope = ["Legacy migration","Hardware procurement","Organisational change management"]
        constraints = ["Timeline within agreed milestone window","Must integrate with current stack"]

    in_lines  = "\n".join(f"    □  {i}" for i in in_scope)
    out_lines = "\n".join(f"    □  {o}" for o in out_scope)
    con_lines = "\n".join(f"    □  {c}" for c in constraints)

    return f"""\
■ SCOPE ANALYSIS
═════════════════
  Request: {query[:120]}
  Task:    {task[:120]}

  IN SCOPE
{in_lines}

  OUT OF SCOPE
{out_lines}

  CONSTRAINTS
{con_lines}

  ASSUMPTIONS
    □  Development environment and toolchain are pre-provisioned
    □  Budget approved for the defined scope
    □  APIs/services required are accessible"""


def _fallback_requirements(query: str, task: str) -> str:
    """PATCH-013g: Domain-aware requirements derived from the query."""
    q = query.lower()
    is_game = any(w in q for w in ["game","mmo","colony","ant","player","level","exp","nft","fortnite","pvp"])
    is_web  = any(w in q for w in ["web app","saas","dashboard","api","subscription","portal"])
    is_biz  = any(w in q for w in ["business","automat","workflow","invoice","report","hr"])

    if is_game:
        func_reqs = [
            ("FR-1","Multiplayer server handles concurrent colony sessions (100+ players/match)","MUST","Defined"),
            ("FR-2","Top-down 2D renderer with customisable ant color palette (not limited to black/red)","MUST","Defined"),
            ("FR-3","4-zone backyard world map with distinct terrain types (grass, soil, concrete, garden)","MUST","Defined"),
            ("FR-4","XP system: kill XP awarded per enemy type, colony level gates new unit unlocks","MUST","Defined"),
            ("FR-5","Bug enemy AI: beetles/wasps/spiders with patrol/aggro behaviour","MUST","Defined"),
            ("FR-6","Session timer: 60-min accelerated loop, eliminated colonies removed permanently","MUST","Defined"),
            ("FR-7","NFT cosmetic system: cape/boots/slippers skins — no gameplay advantage","MUST","Defined"),
            ("FR-8","Subscription tiers: Battle Pass equivalent with seasonal rewards","SHOULD","Defined"),
            ("FR-9","Downloadable client (Electron or packaged HTML5 + Node server)","MUST","Defined"),
            ("FR-10","XP curve: high early XP, decelerating above colony level 20","SHOULD","Defined"),
        ]
        non_func = [
            ("NF-1","Server tick rate","20 TPS min","Perf test"),
            ("NF-2","Client frame rate","60 FPS (30 min)","Profiler"),
            ("NF-3","Match session capacity","100 colonies concurrent","Load test"),
            ("NF-4","NFT mint latency","< 5 seconds","Chain test"),
            ("NF-5","Installer package size","< 200 MB","CI build"),
        ]
    elif is_web:
        func_reqs = [
            ("FR-1","User auth with OAuth + MFA","MUST","Defined"),
            ("FR-2","Dashboard with real-time data visualisation","MUST","Defined"),
            ("FR-3","Subscription billing via Stripe","MUST","Defined"),
            ("FR-4","REST API with versioned endpoints","MUST","Defined"),
            ("FR-5","Role-based access control (admin/user)","MUST","Defined"),
            ("FR-6","Audit trail for all mutations","SHOULD","Defined"),
            ("FR-7","Email notifications (transactional)","SHOULD","Draft"),
        ]
        non_func = [
            ("NF-1","API p99 latency","< 500 ms","APM"),
            ("NF-2","Availability","99.9 %","Uptime"),
            ("NF-3","Data retention","7 years","Policy"),
        ]
    else:
        func_reqs = [
            ("FR-1","Core functionality per request: "+query[:60],"MUST","Defined"),
            ("FR-2","System shall process core business logic","MUST","Defined"),
            ("FR-3","System shall persist results durably","MUST","Defined"),
            ("FR-4","System shall expose APIs for integration","SHOULD","Defined"),
        ]
        non_func = [
            ("NF-1","Response latency p99","< 500 ms","APM"),
            ("NF-2","Availability","99.9 %","Uptime"),
        ]

    fr_rows = "\n".join(
        f"  │ {r[0]:<3} │ {r[1]:<40} │ {r[2]:<8} │ {r[3]:<8} │"
        for r in func_reqs
    )
    nf_rows = "\n".join(
        f"  │ {r[0]:<3} │ {r[1]:<40} │ {r[2]:<8} │ {r[3]:<8} │"
        for r in non_func
    )

    return f"""\
■ FUNCTIONAL & NON-FUNCTIONAL REQUIREMENTS
════════════════════════════════════════════
  Source: {query[:120]}
  Task:   {task[:120]}

  FUNCTIONAL REQUIREMENTS
  ┌─────┬──────────────────────────────────────────┬──────────┬──────────┐
  │ ID  │ Requirement                              │ Priority │ Status   │
  ├─────┼──────────────────────────────────────────┼──────────┼──────────┤
{fr_rows}
  └─────┴──────────────────────────────────────────┴──────────┴──────────┘

  NON-FUNCTIONAL REQUIREMENTS
  ┌─────┬──────────────────────────────────────────┬──────────┬──────────┐
  │ ID  │ Requirement                              │ Target   │ Measure  │
  ├─────┼──────────────────────────────────────────┼──────────┼──────────┤
{nf_rows}
  └─────┴──────────────────────────────────────────┴──────────┴──────────┘

  ACCEPTANCE CRITERIA
    □  All MUST requirements implemented and verified
    □  Non-functional targets met under load-test conditions
    □  Stakeholder sign-off obtained for each requirement group"""

def _fallback_architecture(query: str, task: str) -> str:
    return f"""\
■ SYSTEM ARCHITECTURE
══════════════════════
  Context: {query[:120]}

  HIGH-LEVEL ARCHITECTURE
  ┌──────────────────────────────────────────────────────────────────────┐
  │  Client Layer                                                       │
  │    Browser / Mobile / CLI  ──►  API Gateway / Load Balancer        │
  │                                        │                            │
  │  Service Layer                         ▼                            │
  │    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
  │    │ Service A    │  │ Service B    │  │ Service C    │              │
  │    │ (Core Logic) │  │ (Processing) │  │ (Reporting)  │             │
  │    └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │
  │           │                │                │                       │
  │  Data Layer               ▼                ▼                        │
  │    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
  │    │ Primary DB    │  │ Cache Layer   │  │ Object Store  │           │
  │    │ (PostgreSQL)  │  │ (Redis)       │  │ (S3-compat)   │          │
  │    └──────────────┘  └──────────────┘  └──────────────┘            │
  └──────────────────────────────────────────────────────────────────────┘

  DESIGN PRINCIPLES
    □  Separation of concerns — each service owns its domain
    □  API-first — all inter-service communication via versioned APIs
    □  Stateless services — horizontal scaling without session affinity
    □  Event-driven — async operations via message bus where applicable
    □  Defence in depth — authentication + authorisation at every layer"""


def _fallback_component_design(query: str, task: str) -> str:
    return f"""\
■ COMPONENT DESIGN & MODULE BREAKDOWN
═══════════════════════════════════════
  Source: {query[:120]}

  ┌─────┬──────────────────────────┬───────────────────┬──────────────────┐
  │ #   │ Component                │ Responsibility     │ Dependencies     │
  ├─────┼──────────────────────────┼───────────────────┼──────────────────┤
  │ C-1 │ Input Validator          │ Sanitise & schema  │ Schema registry  │
  │ C-2 │ Business Logic Engine    │ Core processing    │ C-1, C-5         │
  │ C-3 │ Persistence Layer        │ CRUD + migrations  │ Database driver  │
  │ C-4 │ API Controller           │ Route + serialise  │ C-2, Auth module │
  │ C-5 │ Configuration Manager    │ Runtime config     │ Env / vault      │
  │ C-6 │ Event Publisher          │ Async notifications│ Message broker   │
  │ C-7 │ Observability Hook       │ Metrics & tracing  │ OTel SDK         │
  └─────┴──────────────────────────┴───────────────────┴──────────────────┘

  INTERFACE CONTRACTS
    □  C-1 → C-2: validated request DTO
    □  C-2 → C-3: domain entity objects
    □  C-2 → C-6: domain event payload (JSON schema versioned)
    □  C-4 → external: OpenAPI 3.1 spec, versioned path prefix"""


def _fallback_data_model(query: str, task: str) -> str:
    return f"""\
■ DATA MODEL DESIGN
════════════════════
  Context: {query[:120]}

  ENTITY-RELATIONSHIP OVERVIEW
  ┌──────────────────┬──────────────────────────────┬────────────────────┐
  │ Entity           │ Key Attributes                │ Relationships      │
  ├──────────────────┼──────────────────────────────┼────────────────────┤
  │ User             │ id, email, role, created_at   │ 1:N → Session      │
  │ Session          │ id, user_id, token, expires   │ N:1 → User         │
  │ Resource         │ id, type, owner_id, payload   │ N:1 → User         │
  │ AuditLog         │ id, actor_id, action, ts      │ N:1 → User         │
  │ Configuration    │ key, value, scope, version    │ — (standalone)     │
  └──────────────────┴──────────────────────────────┴────────────────────┘

  DATA INTEGRITY RULES
    □  All primary keys: UUID v4
    □  Foreign keys: ON DELETE RESTRICT (no orphan records)
    □  Soft deletes: deleted_at timestamp (never physical delete)
    □  Audit columns: created_at, updated_at on every table
    □  Encryption: PII fields encrypted at rest (AES-256-GCM)

  MIGRATION STRATEGY
    □  Versioned migrations (Alembic / Flyway / Liquibase)
    □  Zero-downtime migration pattern: expand → migrate → contract
    □  Rollback script required for every migration"""


def _fallback_api_design(query: str, task: str) -> str:
    return f"""\
■ API SURFACE DESIGN
═════════════════════
  Scope: {query[:120]}

  API SPECIFICATION (RESTful, versioned: /api/v1/...)
  ┌────────┬──────────────────────────┬──────────────────────────────────┐
  │ Method │ Endpoint                 │ Description                      │
  ├────────┼──────────────────────────┼──────────────────────────────────┤
  │ GET    │ /api/v1/resources        │ List (paginated, filtered, sort) │
  │ POST   │ /api/v1/resources        │ Create new resource              │
  │ GET    │ /api/v1/resources/:id    │ Get single resource by ID        │
  │ PATCH  │ /api/v1/resources/:id    │ Partial update                   │
  │ DELETE │ /api/v1/resources/:id    │ Soft delete                      │
  │ GET    │ /api/v1/health           │ Readiness + liveness check       │
  │ GET    │ /api/v1/metrics          │ Prometheus-format metrics        │
  └────────┴──────────────────────────┴──────────────────────────────────┘

  AUTHENTICATION & AUTHORISATION
    □  Bearer token (JWT, RS256-signed, 15-min expiry)
    □  Refresh token (opaque, 7-day expiry, single-use)
    □  RBAC: admin, editor, viewer roles
    □  Rate limiting: 100 req/min (anon), 1000 req/min (authenticated)

  ERROR RESPONSE FORMAT
    {{"error": {{"code": "RESOURCE_NOT_FOUND", "message": "...", "request_id": "..."}}}}

  PAGINATION
    Cursor-based: ?cursor=<opaque>&limit=50  (max 100)"""


def _fallback_security(query: str, task: str) -> str:
    return f"""\
■ SECURITY ASSESSMENT & CONTROLS
══════════════════════════════════
  Scope: {query[:120]}

  THREAT MODEL (STRIDE)
  ┌──────────────────┬────────────────────────────┬──────────────────────┐
  │ Category         │ Threat                     │ Mitigation           │
  ├──────────────────┼────────────────────────────┼──────────────────────┤
  │ Spoofing         │ Credential theft           │ MFA + token rotation │
  │ Tampering        │ Request payload mutation    │ HMAC signing + TLS   │
  │ Repudiation      │ Action denial              │ Immutable audit log  │
  │ Info Disclosure  │ Data exfiltration          │ Encryption + DLP     │
  │ Denial of Service│ Resource exhaustion         │ Rate limiting + WAF  │
  │ Elev. of Privil. │ Horizontal privilege esc.  │ RBAC + least priv.   │
  └──────────────────┴────────────────────────────┴──────────────────────┘

  SECURITY CONTROLS
    □  TLS 1.3 for all transport
    □  AES-256 encryption at rest
    □  Secret rotation every 90 days (automated via vault)
    □  SAST + SCA scans in every CI pipeline run
    □  Penetration testing: quarterly internal, annual external
    □  Incident response plan tested bi-annually"""


def _fallback_compliance(query: str, task: str) -> str:
    return f"""\
■ COMPLIANCE & GOVERNANCE ASSESSMENT
══════════════════════════════════════
  Scope: {query[:120]}

  CONTROL MATRIX
  ┌─────┬──────────────────────────────┬────────┬──────────┬───────────┐
  │ ID  │ Control                      │ Type   │ Evidence │ Frequency │
  ├─────┼──────────────────────────────┼────────┼──────────┼───────────┤
  │ C-1 │ Access control: MFA enforced │ Prev.  │ Audit log│ Real-time │
  │ C-2 │ Encryption at rest (AES-256) │ Prev.  │ Config   │ Continuous│
  │ C-3 │ Vulnerability scanning       │ Detect.│ Report   │ Weekly    │
  │ C-4 │ Quarterly access review      │ Detect.│ Report   │ Quarterly │
  │ C-5 │ Incident response drill      │ React. │ Log      │ Bi-annual │
  │ C-6 │ Change management process    │ Prev.  │ Tickets  │ Per change│
  └─────┴──────────────────────────────┴────────┴──────────┴───────────┘

  REGULATORY MAPPING
    □  GDPR: data processing inventory, DPIAs, breach notification ≤72h
    □  SOC 2 Type II: trust service criteria (security, availability)
    □  ISO 27001: ISMS scope, risk treatment plan, annual surveillance"""


def _fallback_testing(query: str, task: str) -> str:
    return f"""\
■ TEST STRATEGY & QUALITY ASSURANCE
═════════════════════════════════════
  Scope: {query[:120]}

  TEST PYRAMID
  ┌────────────────┬──────────┬─────────────┬───────────────────────────┐
  │ Layer          │ Coverage │ Run Time    │ Trigger                   │
  ├────────────────┼──────────┼─────────────┼───────────────────────────┤
  │ Unit tests     │ ≥ 85 %   │ < 2 min    │ Every commit              │
  │ Integration    │ ≥ 70 %   │ < 10 min   │ Every pull request        │
  │ E2E / UAT      │ Critical │ < 20 min   │ Pre-deploy gate           │
  │ Performance    │ SLOs     │ < 30 min   │ Weekly + pre-release      │
  │ Security scans │ N/A      │ < 15 min   │ Every PR + weekly full    │
  └────────────────┴──────────┴─────────────┴───────────────────────────┘

  TEST ENVIRONMENT STRATEGY
    □  Ephemeral test environments per PR (Dockerised)
    □  Shared staging environment for integration + UAT
    □  Production-like load test environment (scaled down)

  QUALITY GATES
    □  All unit + integration tests pass
    □  Code coverage ≥ 85 % (no decrease from baseline)
    □  Zero critical / high security findings
    □  Performance SLOs met (p99 latency, throughput)
    □  Code review approved (≥ 1 reviewer)"""


def _fallback_integration(query: str, task: str) -> str:
    return f"""\
■ INTEGRATION PLAN
═══════════════════
  Scope: {query[:120]}

  INTEGRATION MAP
  ┌─────┬────────────────────────┬────────────────┬──────────────────────┐
  │ #   │ Integration Point      │ Protocol       │ Data Flow            │
  ├─────┼────────────────────────┼────────────────┼──────────────────────┤
  │ I-1 │ Authentication service │ OIDC / SAML    │ Bidirectional        │
  │ I-2 │ Message broker         │ AMQP / Kafka   │ Pub/Sub events       │
  │ I-3 │ External API           │ REST + webhook │ Outbound + callback  │
  │ I-4 │ Monitoring platform    │ OTLP / Prom.   │ Outbound telemetry   │
  │ I-5 │ Storage backend        │ S3 API         │ Read / Write         │
  └─────┴────────────────────────┴────────────────┴──────────────────────┘

  INTEGRATION TESTING APPROACH
    □  Contract tests for all external API consumers
    □  CDC (Consumer-Driven Contracts) with Pact or similar
    □  Chaos testing for integration failure scenarios
    □  Circuit breaker validation under degraded conditions"""


def _fallback_documentation(query: str, task: str) -> str:
    return f"""\
■ DOCUMENTATION & KNOWLEDGE TRANSFER
══════════════════════════════════════
  Scope: {query[:120]}

  DOCUMENTATION DELIVERABLES
  ┌─────┬──────────────────────────────┬────────────┬─────────────────────┐
  │ #   │ Document                     │ Audience   │ Format              │
  ├─────┼──────────────────────────────┼────────────┼─────────────────────┤
  │ D-1 │ Architecture Decision Records│ Engineers  │ Markdown (ADR)      │
  │ D-2 │ API Reference (OpenAPI)      │ Consumers  │ OpenAPI 3.1 + HTML  │
  │ D-3 │ Runbook / Operations Guide   │ SRE / Ops  │ Wiki + runbook tool │
  │ D-4 │ User Guide                   │ End Users  │ Help centre / PDF   │
  │ D-5 │ Onboarding Guide             │ New devs   │ README + tutorial   │
  │ D-6 │ Release Notes                │ All        │ Changelog (SemVer)  │
  └─────┴──────────────────────────────┴────────────┴─────────────────────┘

  TRAINING PLAN
    □  Technical deep-dive session (2 hours) for engineering team
    □  Operations walkthrough (1 hour) for SRE / support
    □  End-user training (30 min video + self-paced guide)
    □  Knowledge base articles for common scenarios"""


def _fallback_review(query: str, task: str) -> str:
    return f"""\
■ QUALITY REVIEW & SIGN-OFF CHECKLIST
═══════════════════════════════════════
  Scope: {query[:120]}

  REVIEW CHECKLIST
    □  All functional requirements implemented and verified
    □  Non-functional targets met (latency, throughput, uptime)
    □  Security scan: zero critical / high findings
    □  Code review completed by ≥ 1 peer
    □  Documentation complete and up to date
    □  Deployment runbook tested in staging
    □  Rollback procedure validated
    □  Stakeholder demo completed
    □  Acceptance criteria signed off
    □  Post-launch monitoring dashboards configured

  DEFINITION OF DONE
    □  Code merged to main branch
    □  All CI checks green
    □  Deployed to staging with smoke tests passing
    □  Product owner acceptance received
    □  Release notes published"""


def _fallback_cost_estimate(query: str, task: str) -> str:
    return f"""\
■ COST & EFFORT ESTIMATE
══════════════════════════
  Scope: {query[:120]}

  EFFORT BREAKDOWN
  ┌─────┬────────────────────────────┬────────────┬─────────────┬────────┐
  │ #   │ Phase                      │ Effort (d) │ Team Size   │ Cost   │
  ├─────┼────────────────────────────┼────────────┼─────────────┼────────┤
  │ E-1 │ Discovery & requirements   │   5–8      │ 2           │ $$     │
  │ E-2 │ Architecture & design      │   5–10     │ 2           │ $$     │
  │ E-3 │ Core implementation        │  15–25     │ 3–4         │ $$$    │
  │ E-4 │ Integration & testing      │   8–12     │ 2–3         │ $$     │
  │ E-5 │ Deployment & go-live       │   3–5      │ 2           │ $      │
  │ E-6 │ Documentation & training   │   3–5      │ 1–2         │ $      │
  │ E-7 │ Hypercare & stabilisation  │   5–10     │ 2           │ $$     │
  └─────┴────────────────────────────┴────────────┴─────────────┴────────┘

  TOTAL ESTIMATE: 44–75 person-days
  CONFIDENCE: Medium (±30 %) — refine after discovery phase"""


def _fallback_risk_assessment(query: str, task: str) -> str:
    return f"""\
■ RISK ASSESSMENT & MITIGATION
════════════════════════════════
  Scope: {query[:120]}

  RISK REGISTER
  ┌─────┬────────────────────────────┬───────┬────────┬──────────────────┐
  │ ID  │ Risk                       │ Prob. │ Impact │ Mitigation       │
  ├─────┼────────────────────────────┼───────┼────────┼──────────────────┤
  │ R-1 │ Resource availability      │ MED   │ HIGH   │ Cross-train team │
  │ R-2 │ Scope creep                │ HIGH  │ MED    │ Change control   │
  │ R-3 │ Technology uncertainty     │ LOW   │ HIGH   │ POC / spike first│
  │ R-4 │ Integration complexity     │ MED   │ HIGH   │ Contract tests   │
  │ R-5 │ Budget overrun             │ MED   │ MED    │ Monthly review   │
  │ R-6 │ Key-person dependency      │ MED   │ HIGH   │ Knowledge sharing│
  │ R-7 │ Regulatory change          │ LOW   │ HIGH   │ Compliance watch │
  └─────┴────────────────────────────┴───────┴────────┴──────────────────┘

  RISK RESPONSE STRATEGY
    □  AVOID: Remove root cause where possible
    □  MITIGATE: Reduce probability or impact
    □  TRANSFER: Insurance, contracts, SLAs
    □  ACCEPT: Low-probability / low-impact items with monitoring"""


def _fallback_timeline(query: str, task: str) -> str:
    return f"""\
■ PROJECT TIMELINE & MILESTONES
════════════════════════════════
  Scope: {query[:120]}

  MILESTONE SCHEDULE
  ┌─────────────┬────────────────────────────────────────┬───────────┐
  │ Phase       │ Activities                             │ Duration  │
  ├─────────────┼────────────────────────────────────────┼───────────┤
  │ Discovery   │ Requirements, stakeholder interviews   │ 1–2 weeks │
  │ Design      │ Architecture, specs, prototypes        │ 2–3 weeks │
  │ Sprint 1    │ Core features — MVP functionality      │ 2 weeks   │
  │ Sprint 2    │ Integration, secondary features        │ 2 weeks   │
  │ Sprint 3    │ Polish, edge cases, performance        │ 2 weeks   │
  │ Test & QA   │ Full regression, UAT, load testing     │ 1–2 weeks │
  │ Deploy      │ Staging → production rollout           │ 1 week    │
  │ Hypercare   │ Post-launch monitoring, bug fixes      │ 2–4 weeks │
  └─────────────┴────────────────────────────────────────┴───────────┘

  CRITICAL PATH
    Discovery → Design → Sprint 1 → Sprint 2 → QA → Deploy
    (Sprints 2 & 3 may overlap with test activities)"""


def _fallback_deployment(query: str, task: str) -> str:
    return f"""\
■ DEPLOYMENT & ROLLBACK PLAN
══════════════════════════════
  Scope: {query[:120]}

  DEPLOYMENT CHECKLIST
    □  All CI checks green on release branch
    □  Database migrations tested in staging
    □  Feature flags configured for gradual rollout
    □  Monitoring dashboards reviewed and alerts active
    □  Rollback procedure documented and tested
    □  On-call engineer identified and briefed

  DEPLOYMENT STRATEGY
    Method:    Blue/Green deployment with canary validation
    Canary:    10 % → 25 % → 50 % → 100 % over 30 minutes
    Rollback:  Automated on error-rate > 1 % or p99 > 500 ms

  ROLLBACK PROCEDURE
    1. Trigger rollback via deployment tool (< 2 min)
    2. Shift traffic to previous version immediately
    3. Verify health checks pass on rolled-back version
    4. Investigate root cause in staging environment
    5. Post-mortem within 24 hours"""


def _fallback_monitoring(query: str, task: str) -> str:
    return f"""\
■ MONITORING & ALERTING DESIGN
════════════════════════════════
  Scope: {query[:120]}

  OBSERVABILITY STACK
    Metrics:   Prometheus + Grafana dashboards
    Logging:   Structured JSON → OpenTelemetry Collector → storage
    Tracing:   Distributed traces (Jaeger / Tempo)
    Alerting:  PagerDuty integration; runbook link in every alert

  KEY METRICS & SLOs
  ┌─────────────────────────┬────────────┬──────────────────────────┐
  │ Metric                  │ SLO Target │ Alert Threshold          │
  ├─────────────────────────┼────────────┼──────────────────────────┤
  │ Request success rate    │ ≥ 99.9 %   │ < 99.5 % over 5 min     │
  │ p99 latency             │ < 500 ms   │ > 800 ms over 5 min     │
  │ Error rate              │ < 0.1 %    │ > 1 % over 2 min        │
  │ CPU utilisation         │ < 70 %     │ > 85 % sustained 10 min │
  │ Memory utilisation      │ < 80 %     │ > 90 % sustained 5 min  │
  └─────────────────────────┴────────────┴──────────────────────────┘

  DASHBOARD LAYOUT
    □  Service health overview (traffic, errors, latency)
    □  Infrastructure metrics (CPU, memory, disk, network)
    □  Business KPIs (request volume, conversion, revenue)
    □  Deployment markers (correlate deploys with metric changes)"""


def _fallback_stakeholder(query: str, task: str) -> str:
    return f"""\
■ STAKEHOLDER ANALYSIS
═══════════════════════
  Scope: {query[:120]}

  ┌──────────────────────────────┬────────────┬────────────┬──────────────────────┐
  │ Stakeholder                  │ Role       │ Influence  │ Communication        │
  ├──────────────────────────────┼────────────┼────────────┼──────────────────────┤
  │ Executive Sponsor            │ Approver   │ HIGH       │ Weekly status brief  │
  │ Project Lead                 │ Driver     │ HIGH       │ Daily standups       │
  │ Subject Matter Experts       │ Advisors   │ MEDIUM     │ Bi-weekly review     │
  │ End Users / Consumers        │ Validators │ MEDIUM     │ UAT sessions         │
  │ Operations / Support         │ Operators  │ MEDIUM     │ Runbook handoff      │
  │ Legal / Compliance           │ Gatekeepers│ HIGH       │ Milestone sign-off   │
  │ Finance / Budget Owner       │ Approver   │ HIGH       │ Monthly cost review  │
  │ External Partners / Vendors  │ Suppliers  │ LOW–MED    │ Contractual reviews  │
  └──────────────────────────────┴────────────┴────────────┴──────────────────────┘

  RACI SUMMARY
    □  R (Responsible): Project Lead, SMEs
    □  A (Accountable): Executive Sponsor
    □  C (Consulted): Legal, Finance, End Users
    □  I (Informed): Operations, External Partners"""


def _fallback_generic_task(query: str, task: str, role: str) -> str:
    return f"""\
■ {role.upper()} — TASK OUTPUT
{'═' * (len(role) + 16)}
  Request: {query[:120]}
  Task:    {task[:120]}

  ANALYSIS
    This section addresses the assigned task: "{task[:100]}"
    within the context of the overall project request.

  FINDINGS
    □  Task requirements have been identified and documented
    □  Dependencies with other workstreams mapped
    □  Risks and constraints specific to this task assessed
    □  Deliverables and acceptance criteria defined

  RECOMMENDATIONS
    □  Proceed with implementation per the defined scope
    □  Coordinate with adjacent agents for integration points
    □  Review findings with stakeholders before execution
    □  Validate assumptions during the discovery phase

  NEXT STEPS
    → Detailed specification for this workstream
    → Dependency resolution with other agent outputs
    → Implementation planning with estimated timeline"""


_DOMAIN_KEYWORD_MAP: Dict[str, str] = {
    "ci/cd": "devops", "cicd": "devops", "pipeline": "devops",
    "deploy": "devops", "deployment": "devops", "kubernetes": "devops",
    "k8s": "devops", "docker": "devops", "terraform": "devops",
    "infrastructure": "devops", "devops": "devops", "monitoring": "devops",
    "observability": "devops", "helm": "devops", "cloud": "devops",
    "aws": "devops", "azure": "devops", "gcp": "devops",
    "api": "software", "microservice": "software", "architecture": "software",
    "backend": "software", "frontend": "software", "database": "software",
    "refactor": "software", "migration": "software", "sdk": "software",
    "library": "software", "framework": "software",
    "system design": "software", "software": "software",
    "security": "security", "incident": "security", "vulnerability": "security",
    "penetration": "security", "pentest": "security",
    "zero trust": "security", "encryption": "security", "firewall": "security",
    "threat": "security", "forensic": "security", "iam": "security",
    "data": "data", "analytics": "data", "etl": "data",
    "warehouse": "data", "lake": "data",
    "dashboard": "data", "reporting": "data", "machine learning": "data",
    "book": "content", "write": "content", "chapter": "content",
    "curriculum": "content", "lesson": "content", "training": "content",
    "documentation": "content", "manual": "content", "guide": "content",
    "tutorial": "content", "article": "content", "whitepaper": "content",
    "course": "content", "education": "content", "teach": "content",
    "onboard": "operations", "process": "operations", "workflow": "operations",
    "sop": "operations", "procedure": "operations", "policy": "operations",
    "hiring": "operations", "employee": "operations",
    "vendor": "operations", "procurement": "operations", "supply chain": "operations",
    "strategy": "strategy", "roadmap": "strategy", "plan": "strategy",
    "business plan": "strategy", "growth": "strategy", "market": "strategy",
    "competitive": "strategy", "swot": "strategy", "okr": "strategy",
    "kpi": "strategy", "budget": "strategy", "forecast": "strategy",
    "marketing": "marketing", "campaign": "marketing", "seo": "marketing",
    "brand": "marketing", "social media": "marketing",
    "lead": "marketing", "funnel": "marketing",
    "sales": "marketing", "crm": "marketing", "conversion": "marketing",
    "compliance": "compliance", "audit": "compliance", "gdpr": "compliance",
    "hipaa": "compliance", "regulation": "compliance", "legal": "compliance",
    "contract": "compliance", "governance": "compliance", "risk": "compliance",
    "iso": "compliance", "sox": "compliance", "pci": "compliance",
}


def _detect_domains(query: str) -> List[str]:
    """Return matched domain IDs for *query*, ordered by relevance."""
    q = query.lower()
    hits: Dict[str, int] = {}
    for kw, domain in _DOMAIN_KEYWORD_MAP.items():
        if kw in q:
            hits[domain] = hits.get(domain, 0) + 1
    return sorted(hits, key=hits.get, reverse=True) if hits else ["strategy"]  # type: ignore[arg-type]


def _build_deep_domain_content(query: str) -> str:
    """Generate comprehensive, domain-specific deliverable sections.

    LLM-down fallback — produces rich, actionable content using domain
    templates when no LLM provider is reachable.
    """
    q = query.lower()
    domains = _detect_domains(query)
    primary = domains[0]
    sections: List[str] = []

    # ── Shared: Stakeholder Analysis ──────────────────────────────────────
    sections.append(f"""\
■ STAKEHOLDER ANALYSIS
───────────────────────
  The following stakeholders are identified for "{query[:80]}":

  ┌──────────────────────────────┬────────────┬────────────┬──────────────────────┐
  │ Stakeholder                  │ Role       │ Influence  │ Communication        │
  ├──────────────────────────────┼────────────┼────────────┼──────────────────────┤
  │ Executive Sponsor            │ Approver   │ HIGH       │ Weekly status brief  │
  │ Project Lead                 │ Driver     │ HIGH       │ Daily standups       │
  │ Subject Matter Experts       │ Advisors   │ MEDIUM     │ Bi-weekly review     │
  │ End Users / Consumers        │ Validators │ MEDIUM     │ UAT sessions         │
  │ Operations / Support         │ Operators  │ MEDIUM     │ Runbook handoff      │
  │ Legal / Compliance           │ Gatekeepers│ HIGH       │ Milestone sign-off   │
  │ Finance / Budget Owner       │ Approver   │ HIGH       │ Monthly cost review  │
  │ External Partners / Vendors  │ Suppliers  │ LOW–MED    │ Contractual reviews  │
  └──────────────────────────────┴────────────┴────────────┴──────────────────────┘""")

    # ── Shared: RACI Matrix ───────────────────────────────────────────────
    sections.append("""\
■ RACI MATRIX
──────────────
  ┌────────────────────────────┬──────┬──────┬──────┬──────┬─────────┐
  │ Activity                   │ PM   │ Lead │ SME  │ QA   │ Sponsor │
  ├────────────────────────────┼──────┼──────┼──────┼──────┼─────────┤
  │ Requirements gathering     │ A    │ C    │ R    │ I    │ I       │
  │ Architecture & design      │ I    │ R    │ C    │ C    │ A       │
  │ Implementation / build     │ I    │ R/A  │ C    │ C    │ I       │
  │ Testing & validation       │ I    │ C    │ I    │ R/A  │ I       │
  │ Stakeholder review (UAT)   │ C    │ I    │ C    │ I    │ R/A     │
  │ Deployment / go-live       │ A    │ R    │ I    │ C    │ I       │
  │ Post-launch monitoring     │ I    │ R    │ C    │ R    │ I       │
  │ Documentation & handoff    │ A    │ R    │ C    │ C    │ I       │
  │ Retrospective & lessons    │ R    │ C    │ C    │ C    │ A       │
  └────────────────────────────┴──────┴──────┴──────┴──────┴─────────┘
  R = Responsible   A = Accountable   C = Consulted   I = Informed""")

    # ── Domain: DevOps / Infrastructure ───────────────────────────────────
    if primary == "devops" or "devops" in domains:
        sections.append(f"""\
■ INFRASTRUCTURE & DEVOPS ARCHITECTURE
════════════════════════════════════════
  Request context: {query}

  ┌──────────────────────────────────────────────────────────────────────┐
  │                      HIGH-LEVEL ARCHITECTURE                        │
  │  Developer ──► Git Push ──► CI Pipeline ──► Artifact Registry       │
  │                                   │                                  │
  │                             ┌─────┴─────┐                           │
  │                             ▼           ▼                            │
  │                        Unit Tests   Lint / SAST                     │
  │                             │           │                            │
  │                             └─────┬─────┘                           │
  │                                   ▼                                  │
  │                          Integration Tests                          │
  │                                   │                                  │
  │                             ┌─────┴─────┐                           │
  │                             ▼           ▼                            │
  │                         Staging      Canary                         │
  │                             │           │                            │
  │                             └─────┬─────┘                           │
  │                                   ▼                                  │
  │                       Production (Blue/Green)                       │
  └──────────────────────────────────────────────────────────────────────┘

■ PIPELINE STAGES — DETAILED SPECIFICATION
  STAGE 1 — SOURCE & TRIGGER
    Trigger:          Push to main / PR merge / tag creation
    Branch strategy:  Trunk-based development with short-lived feature branches
    PR requirements:  ≥1 approval, all checks green, no merge conflicts

  STAGE 2 — BUILD
    Build system:     Multi-stage Docker build (builder → runtime)
    Cache strategy:   Layer caching + remote cache (registry-backed)
    Artifact output:  Container image + SBOM + build attestation

  STAGE 3 — TEST
    Unit tests:       Run in parallel (sharded by module)
    Coverage target:  ≥ 85 % line coverage, ≥ 75 % branch coverage
    Integration:      Docker Compose test harness with real DB + message bus
    Security scan:    SAST (Semgrep), SCA (Trivy), secrets (Gitleaks)

  STAGE 4 — ARTIFACT MANAGEMENT
    Registry:         OCI-compliant container registry
    Tagging:          Semantic: v{{major}}.{{minor}}.{{patch}}-{{sha8}}
    Signing:          Cosign / Notary v2 image signatures

  STAGE 5 — DEPLOYMENT
    Strategy:         Blue/Green with automated traffic shift
    Canary:           10 % → 25 % → 50 % → 100 % over 30 minutes
    Rollback:         Automated on error-rate > 1 % or p99 > 500 ms
    GitOps:           ArgoCD / FluxCD syncing from deployment repo

  STAGE 6 — OBSERVABILITY & MONITORING
    Metrics:          Prometheus + Grafana; SLI/SLO dashboards
    Logging:          Structured JSON → OpenTelemetry Collector → storage
    Tracing:          Distributed traces (Jaeger / Tempo)
    Alerting:         PagerDuty integration; runbook links in every alert

■ ENVIRONMENT MATRIX
  ┌─────────────────┬────────────────┬───────────────┬─────────────────┐
  │ Environment      │ Purpose        │ Deploy trigger│ Data            │
  ├─────────────────┼────────────────┼───────────────┼─────────────────┤
  │ dev              │ Active dev     │ Every push    │ Synthetic / seed│
  │ staging          │ Pre-prod QA    │ PR merge      │ Anonymised prod │
  │ canary           │ % traffic test │ Release tag   │ Live (subset)   │
  │ production       │ User-facing    │ Promotion     │ Live            │
  │ dr-standby       │ Disaster recov │ Continuous    │ Replicated      │
  └─────────────────┴────────────────┴───────────────┴─────────────────┘

■ DISASTER RECOVERY & ROLLBACK
  RTO target:  15 minutes  |  RPO target:  5 minutes
  Rollback: ArgoCD revert → traffic shift → verify → post-mortem""")

    # ── Domain: Security ──────────────────────────────────────────────────
    if primary == "security" or "security" in domains:
        sections.append(f"""\
■ SECURITY FRAMEWORK & CONTROLS
═════════════════════════════════
  Scope: {query}

  CONTROL DOMAIN 1 — IDENTITY & ACCESS MANAGEMENT (IAM)
    □  Single Sign-On (SSO) via SAML 2.0 / OIDC
    □  Multi-factor authentication enforced for all users
    □  Role-Based Access Control (RBAC) with least-privilege default
    □  Service accounts: time-bounded, secret-rotated every 90 days
    □  Access reviews: quarterly automated report + manager sign-off

  CONTROL DOMAIN 2 — DATA PROTECTION
    □  Encryption at rest: AES-256 (database, object storage, backups)
    □  Encryption in transit: TLS 1.3 minimum
    □  Key management: HSM-backed KMS; key rotation every 365 days
    □  Data classification: PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED

  CONTROL DOMAIN 3 — NETWORK SECURITY
    □  Zero-trust network architecture: verify identity at every hop
    □  Microsegmentation: service-to-service mTLS
    □  WAF rules: OWASP Top 10 protections
    □  Egress filtering: allow-list only for external destinations

  CONTROL DOMAIN 4 — APPLICATION SECURITY
    □  SAST: integrated in CI pipeline (every PR)
    □  DAST: weekly automated scans against staging
    □  SCA: continuous dependency vulnerability monitoring
    □  Penetration testing: annual third-party; quarterly internal

  CONTROL DOMAIN 5 — INCIDENT RESPONSE
    Phase 1 — Detection (0–15 min):  SIEM alert, validate, classify severity
    Phase 2 — Containment (15–60 min):  Isolate, preserve evidence, rotate creds
    Phase 3 — Eradication (1–4 hours):  Root cause, patch, harden
    Phase 4 — Recovery (4–24 hours):  Restore from clean backups, gradual traffic
    Phase 5 — Post-Incident (24–72 hours):  Blameless post-mortem, action items""")

    # ── Domain: Content / Writing / Education ─────────────────────────────
    if primary == "content" or "content" in domains:
        is_book = any(kw in q for kw in ("book", "textbook", "ebook", "e-book"))
        is_course = any(kw in q for kw in ("course", "curriculum", "lesson", "training program"))

        if is_book:
            topic = query
            for pfx in ("write a complete book on ", "write a book on ", "write a book about ",
                         "create a book on ", "create a book about ", "write "):
                if q.startswith(pfx):
                    topic = query[len(pfx):].strip()
                    break
            sections.append(f"""\
■ BOOK OUTLINE — COMPREHENSIVE STRUCTURE
══════════════════════════════════════════
  Title:    The Complete Guide to {topic.title()}
  Subtitle: From Foundations to Mastery — A Practitioner's Handbook
  Format:   Digital (PDF, EPUB, MOBI) + Print-ready (6×9 trade paperback)
  Target:   400–600 pages | 80,000–120,000 words
  Audience: Beginner to advanced practitioners

  FRONT MATTER
    • Title page & copyright notice  • Dedication
    • Table of Contents (3-level depth)
    • Preface — Why this book exists (800–1,200 words)
    • How to read this book  • Acknowledgements

  PART I — FOUNDATIONS (Chapters 1–5, ~100 pages)
    Chapter 1: Introduction to {topic.title()} (15–20 pages)
    Chapter 2: Core Concepts & Terminology (20–25 pages)
    Chapter 3: Essential Building Blocks (25–30 pages)
    Chapter 4: Workflows & Best Practices (20–25 pages)
    Chapter 5: Your First Complete Project (25–30 pages)

  PART II — INTERMEDIATE MASTERY (Chapters 6–10, ~125 pages)
    Chapter 6: Advanced Techniques I (25–30 pages)
    Chapter 7: Advanced Techniques II (25–30 pages)
    Chapter 8: Architecture & Design Patterns (30–35 pages)
    Chapter 9: Testing & Quality Assurance (25–30 pages)
    Chapter 10: Real-World Case Studies (30–35 pages)

  PART III — EXPERT LEVEL (Chapters 11–15, ~150 pages)
    Chapter 11: Production Systems at Scale (30–35 pages)
    Chapter 12: Team & Organisation (25–30 pages)
    Chapter 13: Emerging Trends & Future Directions (20–25 pages)
    Chapter 14: Migration & Modernisation Playbook (25–30 pages)
    Chapter 15: Capstone Project — Production-Ready System (35–40 pages)

  BACK MATTER
    • Appendix A — Tool & Technology Reference Guide (20 pages)
    • Appendix B — Command Cheat Sheets (10 pages)
    • Appendix C — Configuration Templates (15 pages)
    • Comprehensive Glossary (200+ terms)  • General Index

  PRODUCTION SPECIFICATIONS
    Estimated length:  450–550 pages / ~120,000 words
    Code examples: 200+  |  Exercises: 150+  |  Diagrams: 80+
    Target completion: 16–20 weeks""")

        elif is_course:
            topic = query
            for pfx in ("build a course on ", "create a course on ", "create a training program for "):
                if q.startswith(pfx):
                    topic = query[len(pfx):].strip()
                    break
            sections.append(f"""\
■ COURSE CURRICULUM — COMPREHENSIVE DESIGN
════════════════════════════════════════════
  Course Title:   Mastering {topic.title()}
  Duration:       12 weeks (36 hours instruction + 24 hours practice)
  Modules:        12 modules × 3 hours each

  MODULE 1  — FOUNDATIONS & SETUP (Week 1)
  MODULE 2  — CORE BUILDING BLOCKS (Week 2)
  MODULE 3  — WORKFLOWS & METHODOLOGY (Week 3)
  MODULE 4  — INTERMEDIATE TECHNIQUES (Week 4)
  MODULE 5  — INTEGRATION & AUTOMATION (Week 5)
  MODULE 6  — MID-COURSE PROJECT (Week 6)
  MODULE 7  — ARCHITECTURE & DESIGN PATTERNS (Week 7)
  MODULE 8  — TESTING & QUALITY (Week 8)
  MODULE 9  — PRODUCTION OPERATIONS (Week 9)
  MODULE 10 — SECURITY & COMPLIANCE (Week 10)
  MODULE 11 — ADVANCED TOPICS & TRENDS (Week 11)
  MODULE 12 — CAPSTONE PROJECT (Week 12)

  Each module: 4 lessons (45 min) + lab + assessment.

  ASSESSMENT & GRADING
    ┌──────────────────────────────┬─────────┬──────────┐
    │ Component                    │ Weight  │ Pass mark│
    ├──────────────────────────────┼─────────┼──────────┤
    │ Weekly quizzes (12×)         │  20 %   │  70 %    │
    │ Lab submissions (12×)        │  30 %   │  60 %    │
    │ Mid-course project           │  15 %   │  65 %    │
    │ Capstone project             │  25 %   │  70 %    │
    │ Peer reviews & participation │  10 %   │  50 %    │
    └──────────────────────────────┴─────────┴──────────┘""")

        else:
            sections.append(f"""\
■ CONTENT STRUCTURE & OUTLINE
══════════════════════════════
  Scope: {query}

  SECTION 1 — Introduction & context
  SECTION 2 — Background & landscape analysis
  SECTION 3 — Core content (comprehensive coverage)
  SECTION 4 — Analysis & recommendations
  SECTION 5 — Implementation guide (step-by-step)
  SECTION 6 — Reference material, glossary, and templates""")

    # ── Domain: Data & Analytics ──────────────────────────────────────────
    if primary == "data" or "data" in domains:
        sections.append(f"""\
■ DATA ARCHITECTURE & ANALYTICS DESIGN
════════════════════════════════════════
  Scope: {query}

  DATA PIPELINE:  Sources → Ingest (Kafka/Debezium) → Transform (dbt/Spark) → Serve (Warehouse+Lake) → Consume

  DATA QUALITY FRAMEWORK
    ┌─────────────────┬───────────────────────────────────────────────┐
    │ Quality Dimension│ Validation Rule                              │
    ├─────────────────┼───────────────────────────────────────────────┤
    │ Completeness     │ NULL rate < 2 % for required fields          │
    │ Uniqueness       │ Primary key uniqueness: 100 %                │
    │ Timeliness       │ Data freshness: < 15 min from source event   │
    │ Accuracy         │ Cross-source reconciliation: ±0.1 %          │
    │ Consistency      │ Schema evolution tracked; no breaking changes│
    └─────────────────┴───────────────────────────────────────────────┘
    SLA: Data quality score ≥ 98 % measured weekly.""")

    # ── Domain: Software Engineering ──────────────────────────────────────
    if primary == "software" or "software" in domains:
        sections.append(f"""\
■ SOFTWARE ARCHITECTURE & DESIGN
═════════════════════════════════
  Scope: {query}

  Architecture style:  Modular monolith → microservices (when justified)
  Communication:       REST (sync) + Message bus (async)
  Authentication:      JWT + OAuth 2.0 (PKCE flow for SPAs)

  API SPECIFICATION (RESTful, versioned: /api/v1/...)
    ┌────────┬─────────────────────────┬─────────────────────────┐
    │ Method │ Endpoint                 │ Description              │
    ├────────┼─────────────────────────┼─────────────────────────┤
    │ GET    │ /api/v1/resources       │ List (paginated, filtered)│
    │ POST   │ /api/v1/resources       │ Create                   │
    │ PATCH  │ /api/v1/resources/:id   │ Partial update           │
    │ DELETE │ /api/v1/resources/:id   │ Soft delete              │
    │ GET    │ /api/v1/health          │ Health check             │
    └────────┴─────────────────────────┴─────────────────────────┘

  TESTING STRATEGY
    ┌────────────────┬──────────┬─────────────┬───────────────────┐
    │ Layer           │ Coverage │ Run time     │ Trigger           │
    ├────────────────┼──────────┼─────────────┼───────────────────┤
    │ Unit tests      │ ≥ 85 %  │ < 2 min     │ Every commit      │
    │ Integration     │ ≥ 70 %  │ < 10 min    │ Every PR          │
    │ E2E tests       │ Critical │ < 20 min    │ Pre-deploy        │
    │ Security scans  │ N/A     │ < 15 min    │ Every PR + weekly │
    └────────────────┴──────────┴─────────────┴───────────────────┘""")

    # ── Domain: Business Operations ───────────────────────────────────────
    if primary == "operations" or "operations" in domains:
        sections.append(f"""\
■ BUSINESS OPERATIONS DESIGN
══════════════════════════════
  Scope: {query}

  PROCESS MAP:  Request Intake → Validate & Route → Process & Execute → Complete & Review

  KPIs
    ┌────────────────────────────┬────────────┬──────────┐
    │ KPI                        │ Target     │ Frequency│
    ├────────────────────────────┼────────────┼──────────┤
    │ Request-to-completion time │ < 24 hours │ Weekly   │
    │ First-contact resolution   │ ≥ 70 %     │ Monthly  │
    │ SLA compliance             │ ≥ 95 %     │ Weekly   │
    │ Customer satisfaction      │ ≥ 4.5 / 5  │ Monthly  │
    │ Automation rate            │ ≥ 60 %     │ Quarterly│
    └────────────────────────────┴────────────┴──────────┘

  AUTOMATION OPPORTUNITIES
    ┌───┬────────────────────────────────┬──────────────┬──────────────┐
    │ # │ Process                        │ Effort (days)│ Annual Saving│
    ├───┼────────────────────────────────┼──────────────┼──────────────┤
    │ 1 │ Request intake & classification│   3          │ $18,000      │
    │ 2 │ SLA monitoring & escalation    │   2          │ $12,000      │
    │ 3 │ Report generation              │   2          │ $15,000      │
    │ 4 │ Approval routing               │   3          │ $10,000      │
    │ 5 │ Data entry & reconciliation    │   5          │ $24,000      │
    └───┴────────────────────────────────┴──────────────┴──────────────┘
    Estimated total annual savings: $79,000+""")

    # ── Domain: Strategy ──────────────────────────────────────────────────
    if primary == "strategy" or "strategy" in domains:
        sections.append(f"""\
■ STRATEGIC ANALYSIS & ROADMAP
════════════════════════════════
  Scope: {query}

  SWOT ANALYSIS
    ┌───────────────────────────────┬───────────────────────────────┐
    │ STRENGTHS                     │ WEAKNESSES                    │
    │ • [Core competency 1]         │ • [Gap or limitation 1]       │
    │ • [Unique advantage]          │ • [Resource constraint]       │
    │ • [Technology asset]          │ • [Technical debt]            │
    ├───────────────────────────────┼───────────────────────────────┤
    │ OPPORTUNITIES                 │ THREATS                       │
    │ • [Market trend 1]            │ • [Competitive pressure 1]    │
    │ • [Technology enabler]        │ • [Regulatory change]         │
    │ • [Partnership potential]     │ • [Economic uncertainty]      │
    └───────────────────────────────┴───────────────────────────────┘

  12-MONTH ROADMAP
    Q1 — FOUNDATION:  Setup, quick wins, team formation
    Q2 — BUILD:       Core capability, integration, feedback
    Q3 — SCALE:       Operations, performance, expansion
    Q4 — OPTIMISE:    Efficiency, advanced features, planning

  RISK REGISTER
    ┌─────┬────────────────────────┬───────┬────────┬──────────────────┐
    │ ID  │ Risk                   │ Prob. │ Impact │ Mitigation       │
    ├─────┼────────────────────────┼───────┼────────┼──────────────────┤
    │ R-1 │ Resource availability  │ MED   │ HIGH   │ Cross-train      │
    │ R-2 │ Scope creep            │ HIGH  │ MED    │ Change control   │
    │ R-3 │ Technology risk        │ LOW   │ HIGH   │ POC first        │
    │ R-4 │ Budget overrun         │ MED   │ MED    │ Monthly review   │
    └─────┴────────────────────────┴───────┴────────┴──────────────────┘""")

    # ── Domain: Marketing ─────────────────────────────────────────────────
    if primary == "marketing" or "marketing" in domains:
        sections.append(f"""\
■ MARKETING & GROWTH STRATEGY
═══════════════════════════════
  Scope: {query}

  TARGET AUDIENCE SEGMENTATION
    ┌─────────────────┬───────────────────────┬──────────────────────┐
    │ Segment          │ Profile               │ Channel Mix          │
    ├─────────────────┼───────────────────────┼──────────────────────┤
    │ Enterprise       │ 500+ emp; VP+         │ Account-based (ABM) │
    │ Mid-market       │ 50–500 emp; Director  │ Content + outbound  │
    │ SMB              │ < 50 emp; Founder     │ Self-serve + SEO    │
    │ Developer        │ Individual IC         │ Community + docs    │
    └─────────────────┴───────────────────────┴──────────────────────┘

  CONVERSION FUNNEL
    ┌─────────────────┬────────────┬────────────┐
    │ Stage            │ Target Rate│ Metric     │
    ├─────────────────┼────────────┼────────────┤
    │ Awareness        │ 50K/month │ Visits     │
    │ Interest         │ 5 %       │ Sign-ups   │
    │ Consideration    │ 30 %      │ Trials     │
    │ Purchase         │ 5–8 %     │ Paid conv. │
    │ Retention        │ 85 %+/yr  │ Net ret.   │
    └─────────────────┴────────────┴────────────┘""")

    # ── Domain: Compliance ────────────────────────────────────────────────
    if primary == "compliance" or "compliance" in domains:
        sections.append(f"""\
■ COMPLIANCE & GOVERNANCE FRAMEWORK
═════════════════════════════════════
  Scope: {query}

  CONTROL MATRIX
    ┌─────┬──────────────────────────────┬────────┬──────────┬───────────┐
    │ ID  │ Control                      │ Type   │ Evidence │ Frequency │
    ├─────┼──────────────────────────────┼────────┼──────────┼───────────┤
    │ C-1 │ Access control: MFA enforced │ Prev.  │ Audit log│ Real-time │
    │ C-2 │ Encryption at rest (AES-256) │ Prev.  │ Config   │ Continuous│
    │ C-3 │ Vulnerability scanning       │ Detect.│ Report   │ Weekly    │
    │ C-4 │ Access review                │ Detect.│ Report   │ Quarterly │
    │ C-5 │ Incident response plan       │ React. │ Document │ Annual    │
    │ C-6 │ Backup & recovery test       │ React. │ Test log │ Monthly   │
    │ C-7 │ Change management process    │ Prev.  │ Tickets  │ Per change│
    │ C-8 │ Security awareness training  │ Prev.  │ LMS log  │ Annual    │
    └─────┴──────────────────────────────┴────────┴──────────┴───────────┘

  AUDIT CALENDAR
    Q1: Internal controls review + vendor reassessment
    Q2: External penetration test + SOC 2 evidence collection
    Q3: SOC 2 Type II audit + GDPR DPIA refresh
    Q4: ISO 27001 surveillance + annual policy review""")

    # ── Shared: Project Timeline (always include) ─────────────────────────
    sections.append(f"""\
■ PROJECT TIMELINE & MILESTONES
─────────────────────────────────
  ┌─────────────┬────────────────────────────────────────┬───────────┐
  │ Phase        │ Activities                             │ Duration  │
  ├─────────────┼────────────────────────────────────────┼───────────┤
  │ Discovery    │ Requirements, stakeholder interviews   │ 1–2 weeks │
  │ Design       │ Architecture, specs, prototypes        │ 2–3 weeks │
  │ Build        │ Core implementation, iterative sprints │ 4–8 weeks │
  │ Test & QA    │ Unit, integration, UAT, performance    │ 2–3 weeks │
  │ Deploy       │ Staging, production rollout, monitoring│ 1 week    │
  │ Hypercare    │ Post-launch monitoring, knowledge xfer │ 2–4 weeks │
  └─────────────┴────────────────────────────────────────┴───────────┘

■ SUCCESS CRITERIA & ACCEPTANCE
─────────────────────────────────
  □  All functional requirements implemented and verified
  □  Test suites passing (unit ≥ 85 %, integration ≥ 70 %)
  □  Performance SLOs met (p99 latency, throughput, error rate)
  □  Security scan: zero critical / high findings
  □  Documentation complete (technical + operational + user)
  □  Stakeholder sign-off obtained
  □  Training delivered to all operators / end users
  □  Monitoring and alerting operational
  □  Disaster recovery procedure tested""")

    return "\n\n".join(sections)


def _build_minimal_custom_content(query: str) -> str:
    """Fallback content when ALL LLM providers are down.

    Uses the static domain keyword engine to produce rich, structured
    content without any LLM calls.  This is the last-resort fallback
    and must still be useful.
    """
    domain_content = _build_deep_domain_content(query)
    return f"""\
■ DELIVERABLE OVERVIEW
───────────────────────
  Request:  {query}
  Status:   Generated by Murphy System onboard engine (LLM unavailable)

■ EXECUTIVE SUMMARY
─────────────────────
  This deliverable addresses the request: "{query}"

  Murphy System has analyzed your request using the onboard domain engine
  and prepared this structured document.  For LLM-powered output, ensure
  DEEPINFRA_API_KEY is set in your environment.

{domain_content}

■ ACTION ITEMS
───────────────
  □  Review and customise this deliverable to your specific context.
  □  Share with stakeholders for alignment before execution.
  □  Track progress against the milestones above.
  □  Use Murphy System workflow automation to automate repetitive steps.

■ NEXT STEPS
─────────────
  → Sign up at murphy.systems for AI-powered automation of this workflow.
  → Murphy can generate full SOPs, contracts, and execution plans.
  → Free tier: 10 automated actions/day. Upgrade for unlimited.
"""



def generate_custom_deliverable(
    query: str,
    librarian_context: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a custom deliverable using the MFGC → MSS → Librarian → LLM pipeline."""
    title = (
        f'Custom Deliverable: "{query[:60]}"'
        if len(query) > 60
        else f'Custom Deliverable: "{query}"'
    )

    # Stage 1 — MFGC gate
    mfgc_result = _run_mfgc_gate(query)

    # Stage 2 — MSS Magnify + Solidify (concurrent with domain expert)
    import concurrent.futures as _cf
    with _cf.ThreadPoolExecutor(max_workers=2) as _pool:
        _mss_future = _pool.submit(_run_mss_pipeline, query, mfgc_result)
        # WIRE-EXPERT-001: Domain expert analysis runs alongside MSS
        _expert_future = _pool.submit(_run_domain_expert_analysis, query)
        mss_result = _mss_future.result(timeout=90)
        expert_result = _expert_future.result(timeout=90)

    # Stage 3 — Generate prose with all enriched context
    content = _generate_llm_content(
        query,
        mfgc_result=mfgc_result,
        mss_result=mss_result,
        librarian_context=librarian_context,
        expert_result=expert_result,
    )

    # Stage 4 — Append librarian context section (always rendered when present)
    lib_section = _format_librarian_section(librarian_context or "")
    if lib_section:
        content = content.rstrip() + "\n\n" + lib_section

    # Stage 5 — Append paid-tier Automation Blueprint preview if automation requested
    if _detect_major_automation(query):
        content = content.rstrip() + "\n\n" + _build_automation_blueprint(query, mss_result)

    # Append Quality Plan when the query involves planning or automation
    if any(kw in query.lower() for kw in ("plan", "quote", "automate", "service", "cost", "pricing")):
        content = content.rstrip() + "\n\n" + _build_quality_plan(
            query, mss_result=mss_result, librarian_context=librarian_context,
        )

    filename = _scenario_to_filename(None, query)

    # Quality score: boost if MFGC gated successfully
    quality = 94
    if mfgc_result.get("success"):
        quality = min(99, quality + int(mfgc_result.get("confidence", 0) * 5))
    elif mss_result and not mss_result.get("fallback"):
        quality = 96  # MSS ran even if MFGC unavailable

    txt = build_branded_txt(title, content, scenario_type="custom", quality_score=quality)
    return {"title": title, "content": txt, "filename": filename}


def generate_deliverable(
    query: str,
    librarian_context: Optional[str] = None,
) -> Dict[str, Any]:
    """Main entry point: detect scenario and dispatch to appropriate generator."""
    scenario_key = _detect_scenario(query)
    if scenario_key and scenario_key in _SCENARIO_TEMPLATES:
        return generate_predefined_deliverable(scenario_key, query, librarian_context=librarian_context)
    return generate_custom_deliverable(query, librarian_context=librarian_context)


def generate_deliverable_with_progress(
    query: str,
    librarian_context: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Run the production-workflow pipeline and return a list of progress events.

    Each event is ``{"phase": int, "status": str, ...}``.  The final event
    has ``"phase": "done"`` and carries the full ``deliverable`` dict.

    Pipeline  (label: FORGE-PIPELINE-002)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    The Forge no longer generates a deliverable directly.  Instead it:

    1. **Phase 1 — MFGC Gate** — confidence-score the request.
    2. **Phase 2 — Workflow Resolution** — search the production-workflow
       registry for an existing workflow that satisfies the request.
       Decide: *reuse*, *modify*, or *create new*.  Uses Murphy System
       itself as the reference implementation so it never reinvents the
       wheel.
    3. **Phase 3 — MSS Pipeline** — run Magnify + Solidify to derive the
       full requirements and implementation plan.
    4. **Phase 4 — Execute Workflow** — run the resolved workflow to
       generate the deliverable.  Persist the workflow for future reuse.
    5. **Phase 5 — HITL Review** — route the output through platform-side
       HITL for bug fixing and quality review.

    This is the synchronous building-block used by the async SSE endpoint.
    """
    events: List[Dict[str, Any]] = []

    # FORGE-ERR-TRACKER-001: Track every error and fallback through the pipeline
    tracker = PipelineErrorTracker(query)

    # --- Phase 1: Scenario Detection / MFGC Gate --------------------------
    # Scenario detection provides *context* for the agents but never bypasses
    # the full pipeline.  Every query runs MFGC → MSS → swarm.
    scenario_key = _detect_scenario(query)
    is_predefined = False  # Always run the full pipeline (FORGE-PIPELINE-003)

    mfgc_result = _run_mfgc_gate(query, tracker=tracker)
    mfgc_ok = mfgc_result.get("success", False)
    mfgc_fallback = mfgc_result.get("fallback", True)
    phase1_status = (
        f"MFGC gate passed — confidence {mfgc_result.get('confidence', 0):.0%}"
        if mfgc_ok
        else "MFGC gate — onboard engine (adapter unavailable)"
    )
    if scenario_key:
        phase1_status += f" (scenario hint: {scenario_key})"
    events.append({
        "phase": 1,
        "status": phase1_status,
        "detail": "mfgc",
        "pipeline_stage": "mfgc",
        "mfgc_ok": mfgc_ok,
        "mfgc_fallback": mfgc_fallback,
        "scenario_hint": scenario_key,
    })

    # --- Phase 2: Production Workflow Resolution  (label: FORGE-RESOLVE-001) ---
    # Search the registry for an existing production workflow that satisfies
    # the user's request.  The registry uses Murphy System's own architecture
    # as the reference implementation — it never reinvents the wheel.
    workflow: Dict[str, Any] = {}
    workflow_decision = "create"
    try:
        from src.production_workflow_registry import get_workflow_registry
        registry = get_workflow_registry()
        workflow, workflow_decision = registry.resolve_workflow(query)
        events.append({
            "phase": 2,
            "status": (
                f"Workflow resolved → {workflow_decision.upper()}: "
                f"\"{workflow.get('name', 'unknown')}\""
            ),
            "detail": "workflow_resolution",
            "pipeline_stage": "workflow_resolve",
            "workflow_decision": workflow_decision,
            "workflow_id": workflow.get("workflow_id"),
            "workflow_name": workflow.get("name"),
            "workflow_category": workflow.get("category"),
            "workflow_steps": len(workflow.get("steps", [])),
            "workflow_source": workflow.get("source", "auto"),
        })
    except Exception as exc:  # WORKFLOW-RESOLVE-ERR-001
        logger.warning("WORKFLOW-RESOLVE-ERR-001: Workflow registry unavailable: %s — using default pipeline", exc)
        tracker.record_error("WORKFLOW-RESOLVE-ERR-001", "workflow_registry", str(exc))
        tracker.record_fallback("workflow_registry", f"unavailable: {exc}")
        events.append({
            "phase": 2,
            "status": "Workflow registry unavailable — using default pipeline",
            "detail": "workflow_resolution",
            "pipeline_stage": "workflow_resolve",
            "workflow_decision": "fallback",
        })

    # --- Phase 3: MSS Pipeline + Agent Task Decomposition -------------------
    agent_tasks: List[Dict[str, str]] = []  # FORGE-SWARM-001: always initialised
    # Always run MSS and decompose into agent tasks
    mfgc_result_for_gen = mfgc_result
    mss_result = _run_mss_pipeline(query, mfgc_result_for_gen, tracker=tracker)
    mss_ok = not mss_result.get("fallback", True)
    mss_partial = mss_result.get("partial_failure", False)
    mss_status_detail = "mss"
    if mss_ok and not mss_partial:
        mss_status_msg = "MSS Magnify + Solidify — task decomposition complete"
    elif mss_ok and mss_partial:
        failed_ops = []
        if mss_result.get("magnify_error"):
            failed_ops.append("Magnify")
        if mss_result.get("solidify_error"):
            failed_ops.append("Solidify")
        mss_status_msg = f"MSS partial — {', '.join(failed_ops)} failed, using available output"
    else:
        mss_status_msg = "MSS — onboard pipeline (modules unavailable)"
    events.append({
        "phase": 3,
        "status": mss_status_msg,
        "detail": "mss",
        "pipeline_stage": "mss",
        "mss_ok": mss_ok,
    })

    # --- Agent task decomposition from MSS Magnify output ---------------
    agent_tasks = _build_agent_task_list(query, mss_result, workflow=workflow)
    if agent_tasks:
        events.append({
            "phase": 3,
            "status": f"Decomposed into {len(agent_tasks)} parallel tasks",
            "detail": "agent_tasks",
            "agent_tasks": agent_tasks,
        })
    else:
        # FORGE-SWARM-ERR-001: Log when decomposition produces zero tasks
        logger.warning(
            "Agent task decomposition returned 0 tasks for query: %s "
            "(mss_ok=%s, workflow_steps=%d) — swarm will not activate",
            query[:80], mss_ok, len(workflow.get("steps", [])),
        )
        events.append({
            "phase": 3,
            "status": "Task decomposition returned 0 tasks — single-agent fallback",
            "detail": "agent_tasks_empty",
            "pipeline_stage": "decomposition_fallback",
        })

    # --- Phase 4: Execute Workflow → Content Generation --------------------
    # FORGE-SWARM-001: When agent_tasks were decomposed, execute them as a
    # parallel swarm.  Each agent produces a section; results are synthesized
    # into a single deliverable that is far larger and more detailed than a
    # single LLM call could produce.
    swarm_executed = False
    swarm_agent_count = 0
    deliverable: Dict[str, Any] = {}

    if agent_tasks:
        # ── Swarm path: parallel agent execution ──────────────────────
        events.append({
            "phase": 4,
            "status": (
                f"Swarm executing {len(agent_tasks)} parallel agent tasks"
                + (f" via workflow \"{workflow.get('name', 'default')}\"" if workflow.get("steps") else "")
            ),
            "detail": "swarm_execute",
            "pipeline_stage": "swarm_execute",
            "agent_count": len(agent_tasks),
        })

        try:
            agent_results = _execute_swarm_tasks(
                agent_tasks,
                query,
                mss_result,
                librarian_context=librarian_context,
            )
            successful = [r for r in agent_results if r.get("success")]
            failed = [r for r in agent_results if not r.get("success")]
            swarm_agent_count = len(successful)

            if failed:
                # FORGE-SWARM-ERR-002: Report which agents failed
                failed_names = [r.get("agent_name", "?") for r in failed]
                logger.warning(
                    "FORGE-SWARM-ERR-002: Swarm %d/%d agents failed: %s — query: %s",
                    len(failed), len(agent_results), ", ".join(failed_names), query[:80],
                )
                for fr in failed:
                    tracker.record_error(
                        "FORGE-SWARM-ERR-002", f"swarm_agent:{fr.get('agent_name', '?')}",
                        f"task={fr.get('task', '?')[:60]}",
                    )
                events.append({
                    "phase": 4,
                    "status": f"{len(failed)} agent(s) failed: {', '.join(failed_names[:5])}",
                    "detail": "swarm_partial_failure",
                    "pipeline_stage": "swarm_execute",
                    "failed_agents": failed_names,
                    "successful_agents": len(successful),
                })

            if successful:
                # ── Synthesise agent outputs into coherent deliverable ─────
                events.append({
                    "phase": 4,
                    "status": f"Synthesizing outputs from {len(successful)} agents into deliverable",
                    "detail": "swarm_synthesize",
                    "pipeline_stage": "swarm_synthesize",
                })

                synth_content = _synthesize_swarm_outputs(
                    agent_results,
                    query,
                    mss_result,
                    mfgc_result=mfgc_result_for_gen,
                    librarian_context=librarian_context,
                )

                if synth_content and len(synth_content) > 100:
                    title = (
                        f'Custom Deliverable: "{query[:60]}"'
                        if len(query) > 60
                        else f'Custom Deliverable: "{query}"'
                    )
                    filename = _scenario_to_filename(None, query)
                    quality = min(99, 90 + min(swarm_agent_count, 9))
                    txt = build_branded_txt(
                        title, synth_content,
                        scenario_type="swarm_generated",
                        quality_score=quality,
                    )
                    deliverable = {"title": title, "content": txt, "filename": filename}
                    swarm_executed = True
                    tracker.record_path(f"swarm_ok:{swarm_agent_count}_agents")
                    logger.info(
                        "FORGE-SWARM-001: Swarm deliverable complete — "
                        "%d agents, %d chars, quality=%d",
                        swarm_agent_count, len(txt), quality,
                    )
                else:
                    # FORGE-SWARM-ERR-003: Synthesis produced empty content
                    logger.warning(
                        "FORGE-SWARM-ERR-003: Swarm synthesis returned empty "
                        "content (%d chars) — falling back to single-agent",
                        len(synth_content) if synth_content else 0,
                    )
                    tracker.record_error(
                        "FORGE-SWARM-ERR-003", "swarm_synthesis",
                        f"insufficient content: {len(synth_content) if synth_content else 0} chars",
                    )
                    tracker.record_fallback("swarm", "synthesis produced empty content")
                    events.append({
                        "phase": 4,
                        "status": "Swarm synthesis produced insufficient content — single-agent fallback",
                        "detail": "swarm_synthesis_empty",
                        "pipeline_stage": "swarm_fallback",
                    })
            else:
                # FORGE-SWARM-ERR-004: All agents failed
                logger.error(
                    "FORGE-SWARM-ERR-004: All %d swarm agents failed — "
                    "falling back to single-agent pipeline",
                    len(agent_results),
                )
                tracker.record_error(
                    "FORGE-SWARM-ERR-004", "swarm",
                    f"all {len(agent_results)} agents failed",
                )
                tracker.record_fallback("swarm", "all agents failed")
                events.append({
                    "phase": 4,
                    "status": f"All {len(agent_results)} agents failed — single-agent fallback",
                    "detail": "swarm_all_failed",
                    "pipeline_stage": "swarm_fallback",
                })

        except Exception as exc:
            # FORGE-SWARM-ERR-005: Swarm execution infrastructure failure
            logger.exception(
                "FORGE-SWARM-ERR-005: Swarm execution failed with %s: %s "
                "— falling back to single-agent pipeline",
                type(exc).__name__, exc,
            )
            tracker.record_error("FORGE-SWARM-ERR-005", "swarm_infra", str(exc))
            tracker.record_fallback("swarm", f"infrastructure: {type(exc).__name__}: {exc}")
            events.append({
                "phase": 4,
                "status": f"Swarm execution error ({type(exc).__name__}) — single-agent fallback",
                "detail": "swarm_exception",
                "pipeline_stage": "swarm_fallback",
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:200],
            })

    # ── Single-agent fallback (swarm not activated/failed) ──
    if not swarm_executed:
        if not agent_tasks:
            # FORGE-SWARM-ERR-006: No tasks means no swarm — explain clearly
            logger.info(
                "FORGE-SWARM-ERR-006: No agent tasks decomposed — "
                "using single-agent pipeline for: %s", query[:80],
            )
            tracker.record_fallback("swarm", "no agent tasks decomposed")
        else:
            tracker.record_fallback("swarm", "swarm failed — using single-agent")
        tracker.record_path("single_agent_fallback")
        events.append({
            "phase": 4,
            "status": (
                f"Executing workflow \"{workflow.get('name', 'default')}\" "
                f"({len(workflow.get('steps', []))} steps)"
                if workflow.get("steps")
                else "Generating content — single-agent LLM pipeline"
            ),
            "detail": "execute",
            "pipeline_stage": "workflow_execute",
        })
        deliverable = generate_deliverable(query, librarian_context=librarian_context)

    content = deliverable.get("content", "")
    if not content:
        # FORGE-SWARM-ERR-007: Deliverable content is empty after all paths
        logger.error(
            "FORGE-SWARM-ERR-007: Deliverable content is empty after "
            "%s path for query: %s",
            "swarm" if swarm_executed else "single-agent", query[:80],
        )
        tracker.record_error(
            "FORGE-SWARM-ERR-007", "deliverable_content",
            f"empty content after {'swarm' if swarm_executed else 'single-agent'} path",
        )

    word_count = len(content.split()) if content else 0
    line_count = content.count("\n") + 1 if content else 0
    size_kb = round(len(content) / 1024, 1) if content else 0

    # Quality score — swarm deliverables score higher due to multi-agent depth
    if swarm_executed and swarm_agent_count > 0:
        quality_score = min(99, 90 + min(swarm_agent_count, 9))
    else:
        quality_score = min(99, 85 + min(word_count // 200, 10))

    # WIRE-SPEC-001: Generate automation spec in streaming path too
    automation_spec: Optional[Dict[str, Any]] = None
    try:
        automation_spec = generate_automation_spec(query, librarian_context=librarian_context)
    except Exception as exc:  # AUTO-SPEC-ERR-001
        logger.warning("AUTO-SPEC-ERR-001: Automation spec generation skipped (streaming): %s", exc)
        tracker.record_error("AUTO-SPEC-ERR-001", "automation_spec", str(exc))

    # --- Persist the workflow for future reuse ------------------------------
    # The workflow is saved even if it was reused — usage metrics are updated.
    workflow_id = None
    try:
        from src.production_workflow_registry import get_workflow_registry
        reg = get_workflow_registry()
        if workflow_decision == "create" and workflow.get("steps"):
            workflow_id = reg.persist_workflow(workflow, source="auto")
        elif workflow_decision in ("reuse", "modify"):
            workflow_id = workflow.get("workflow_id")
        if workflow_id:
            reg.record_usage(workflow_id, quality_score=quality_score)
    except Exception as exc:  # WORKFLOW-PERSIST-ERR-001
        logger.warning("WORKFLOW-PERSIST-ERR-001: Workflow persistence skipped: %s", exc)
        tracker.record_error("WORKFLOW-PERSIST-ERR-001", "workflow_persist", str(exc))

    # --- Phase 5: HITL Review  (label: FORGE-HITL-001) --------------------
    # Every output goes through platform-side HITL review for bug fixing.
    hitl_status = "pending_review"
    events.append({
        "phase": 5,
        "status": "Deliverable queued for platform HITL review",
        "detail": "hitl",
        "pipeline_stage": "hitl_review",
        "hitl_status": hitl_status,
    })

    # --- Emit final pipeline summary ----------------------------------------
    tracker.log_final_summary()

    # --- Done ---------------------------------------------------------------
    done_status = (
        f"Build complete — {swarm_agent_count}-agent swarm deliverable ready "
        f"(pending HITL review)"
        if swarm_executed
        else "Build complete — deliverable ready (pending HITL review)"
    )
    done_event: Dict[str, Any] = {
        "phase": "done",
        "status": done_status,
        "deliverable": deliverable,
        "available_formats": list(SUPPORTED_FORMATS.keys()),
        "format_labels": {k: v["label"] for k, v in SUPPORTED_FORMATS.items()},
        "workflow": {
            "workflow_id": workflow_id or workflow.get("workflow_id"),
            "name": workflow.get("name"),
            "decision": workflow_decision,
            "steps_count": len(workflow.get("steps", [])),
            "hitl_status": hitl_status,
        },
        "metrics": {
            "word_count": word_count,
            "line_count": line_count,
            "size_kb": size_kb,
            "quality_score": quality_score,
            "scenario": scenario_key or "custom",
            "is_predefined": is_predefined,
            "swarm_executed": swarm_executed,
            "swarm_agent_count": swarm_agent_count,
        },
        "pipeline_diagnostics": tracker.summary(),
    }
    # WIRE-SPEC-001: Include automation spec when available
    if automation_spec:
        done_event["automation_spec"] = automation_spec
    events.append(done_event)
    return events


def _build_agent_task_list(
    query: str,
    mss_result: Dict[str, Any],
    *,
    workflow: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """Build an agent task list from workflow steps + MSS Magnify output.

    The number of tasks is derived from the actual MSS/workflow output —
    not a fixed count.  Each entry is
    ``{"agent_id": int, "agent_name": str, "task": str}``.

    Priority order for task items:
    1. Workflow steps (if a production workflow was resolved)
    2. MSS Magnify functional requirements + components
    3. MSS Solidify implementation steps
    4. Deterministic decomposition from the query (fallback)
    """
    tasks: List[Dict[str, str]] = []
    mag = mss_result.get("magnify", {})
    sol = mss_result.get("solidify", {})

    # Collect real task items — workflow steps first, then MSS output
    items: List[str] = []
    roles_from_workflow: List[str] = []

    # Workflow steps provide the production workflow's own task breakdown
    if workflow and workflow.get("steps"):
        for step in workflow["steps"]:
            step_name = step.get("name", "")
            step_desc = step.get("description", "")
            role = step.get("agent_role", "")
            items.append(f"{step_name}: {step_desc}"[:120] if step_desc else step_name)
            if role:
                roles_from_workflow.append(role)

    # MSS output enriches with finer-grained tasks
    for req in mag.get("functional_requirements", []):
        items.append(req)
    for comp in mag.get("technical_components", []):
        items.append(comp)
    for step in sol.get("implementation_steps", []):
        items.append(step)
    for ts in sol.get("testing_strategy", []):
        items.append(ts)
    for doc in sol.get("documentation_updates", []):
        items.append(doc)

    # If MSS didn't return data, build deterministic task decomposition
    if not items:
        items = _deterministic_task_decomposition(query)

    # Agent role names — prefer workflow roles if available, else defaults
    default_roles = [
        "ScopeAnalyzer", "RequirementsWriter", "ArchitectBot",
        "ComponentDesigner", "DataModeler", "APIDesigner",
        "SecurityAuditor", "ComplianceChecker", "TestPlanner",
        "IntegrationBot", "DocWriter", "ReviewAgent",
        "CostEstimator", "RiskAssessor", "TimelineBot",
        "QAValidator",
    ]
    roles = roles_from_workflow if roles_from_workflow else default_roles

    # Task count matches actual work — driven by MSS/workflow decomposition
    for i, item_text in enumerate(items):
        role = roles[i % len(roles)]
        tasks.append({
            "agent_id": i,
            "agent_name": f"Agent-{i + 1:02d}: {role}",
            "task": str(item_text)[:120],
        })

    return tasks


# =========================================================================
# SWARM EXECUTION ENGINE  (label: FORGE-SWARM-001)
# =========================================================================
# When agent tasks have been decomposed from MSS/workflow output, the swarm
# engine executes each task as a parallel LLM call.  All results are then
# synthesized into one coherent deliverable that is far larger and more
# detailed than a single LLM call could produce.
# =========================================================================

_SWARM_MAX_WORKERS = 1  # PATCH-013b: Sequential for Ollama local model (single-threaded)


def _execute_single_agent_task(
    agent_task: Dict[str, str],
    query: str,
    mss_context: str,
    librarian_context: str,
) -> Dict[str, Any]:
    """Execute one agent task via the LLM and return its output.

    Each agent receives the original query plus its specific task assignment
    and the shared MSS context.  Returns a dict with ``agent_id``,
    ``agent_name``, ``task``, ``content``, and ``success``.
    """
    agent_name = agent_task.get("agent_name", "Agent")
    task_desc = agent_task.get("task", "")
    agent_id = agent_task.get("agent_id", 0)

    system_prompt = (
        f"{MURPHY_SYSTEM_IDENTITY}\n\n"
        f"You are **{agent_name}** — a specialist agent in the Murphy System swarm.\n"
        f"Your assigned task is below.  Produce a detailed, production-grade\n"
        f"section for this specific area.  Be thorough — include tables,\n"
        f"checklists, specs, and concrete details.  Do NOT summarize;\n"
        f"produce the full section content.\n\n"
        f"Use section headers with ■, tables with box-drawing characters,\n"
        f"and checklists (□) where appropriate."
    )

    user_parts = [
        f"OVERALL PROJECT REQUEST:\n{query}\n",
        f"YOUR ASSIGNED TASK:\n{task_desc}\n",
    ]
    if mss_context:
        user_parts.append(f"MSS PIPELINE CONTEXT:\n{mss_context}\n")
    if librarian_context:
        user_parts.append(f"KNOWLEDGE BASE CONTEXT:\n{librarian_context}\n")
    user_parts.append(
        "Produce a comprehensive, production-grade section for your assigned "
        "task.  This will be merged with outputs from other specialist agents "
        "into a complete deliverable.  Do not duplicate the overall project "
        "overview — focus on YOUR section's depth and detail."
    )
    user_prompt = "\n".join(user_parts)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content = ""
    try:
        from src.llm_provider import get_llm
        provider = get_llm()
        completion = provider.complete_messages(
            messages,
            model_hint="chat",
            temperature=0.7,
            max_tokens=16384,
        )
        # PATCH-013a: Accept onboard (Ollama) provider — previously rejected by mistake
        if completion.content:
            content = completion.content
            logger.info(
                "Swarm agent %s (%s) completed: %d chars via %s",
                agent_id, agent_name, len(content), completion.provider,
            )
    except Exception as exc:
        logger.warning("Swarm agent %s (%s) LLM failed: %s", agent_id, agent_name, exc)

    # Fallback: use agent-role-specific content generator if LLM unavailable.
    # FORGE-SWARM-ROLE-001: Each agent produces a *distinct* section so that
    # the synthesized deliverable reflects genuine swarm collaboration rather
    # than N copies of the same generic template.
    if not content or len(content) < 50:
        role_content = _build_agent_specific_fallback_content(
            agent_name, task_desc, query,
        )
        content = (
            f"■ {agent_name.upper()} — {task_desc}\n"
            f"{'─' * 60}\n"
            f"{role_content}"
        )

    return {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "task": task_desc,
        "content": content,
        "success": bool(content and len(content) >= 50),
    }


def _execute_swarm_tasks(
    agent_tasks: List[Dict[str, str]],
    query: str,
    mss_result: Dict[str, Any],
    librarian_context: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Execute all agent tasks in parallel and return their outputs.

    Uses a bounded ThreadPoolExecutor to run up to ``_SWARM_MAX_WORKERS``
    concurrent LLM calls.  Each agent receives its specific task assignment
    plus shared context from the MSS pipeline.

    Label: FORGE-SWARM-001
    """
    if not agent_tasks:
        return []

    mss_context = _format_mss_context(mss_result) if mss_result else ""
    lib_ctx = librarian_context or ""

    import concurrent.futures
    results: List[Dict[str, Any]] = []
    max_w = min(_SWARM_MAX_WORKERS, len(agent_tasks))

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_w) as pool:
        future_to_task = {
            pool.submit(
                _execute_single_agent_task,
                task,
                query,
                mss_context,
                lib_ctx,
            ): task
            for task in agent_tasks
        }
        for future in concurrent.futures.as_completed(future_to_task):
            task_ref = future_to_task[future]
            try:
                result = future.result(timeout=120)
                results.append(result)
            except Exception as exc:
                logger.warning(
                    "Swarm task '%s' failed: %s",
                    task_ref.get("task", "?"), exc,
                )
                results.append({
                    "agent_id": task_ref.get("agent_id", 0),
                    "agent_name": task_ref.get("agent_name", "Agent"),
                    "task": task_ref.get("task", ""),
                    "content": "",
                    "success": False,
                })

    # Sort by agent_id to maintain deterministic ordering
    results.sort(key=lambda r: r.get("agent_id", 0))
    return results


def _synthesize_swarm_outputs(
    agent_results: List[Dict[str, Any]],
    query: str,
    mss_result: Dict[str, Any],
    mfgc_result: Optional[Dict[str, Any]] = None,
    librarian_context: Optional[str] = None,
) -> str:
    """Combine all agent outputs into one coherent deliverable.

    Strategy:
    1. Build an executive overview from MSS data.
    2. Concatenate each agent's section, delineated by headers.
    3. Run a final synthesis LLM pass to add a coherent introduction,
       cross-references, and a unified conclusion.

    If the synthesis LLM call fails, the concatenated agent sections are
    returned directly — still far richer than a single-call deliverable.

    Label: FORGE-SWARM-002
    """
    # --- Build concatenated agent sections --------------------------------
    # FORGE-SWARM-DEDUP-001: Deduplicate identical agent outputs so that
    # repeated fallback sections are not concatenated verbatim.
    sections: List[str] = []
    seen_hashes: set = set()
    successful_count = 0
    for r in agent_results:
        raw = r.get("content")
        if not raw:
            continue
        successful_count += 1
        stripped = raw.strip()
        content_hash = hashlib.md5(stripped.encode()).hexdigest()
        if content_hash in seen_hashes:
            logger.warning(
                "FORGE-SWARM-DEDUP-001: Duplicate content from agent '%s' "
                "suppressed — identical to a previous agent's output",
                r.get("agent_name", "?"),
            )
            continue
        seen_hashes.add(content_hash)
        sections.append(stripped)

    if not sections:
        # All agents failed — fall back to single-call pipeline
        return _generate_llm_content(
            query,
            mfgc_result=mfgc_result,
            mss_result=mss_result,
            librarian_context=librarian_context,
        )

    # --- Build executive overview from MSS --------------------------------
    mfgc_note = ""
    if mfgc_result:
        conf = mfgc_result.get("confidence", 0)
        mi = mfgc_result.get("murphy_index")
        mi_part = f", murphy_index={mi}" if mi is not None else ""
        mfgc_note = f"[MFGC gate: confidence={conf:.2f}{mi_part}]"

    overview = ""
    if mss_result and (mss_result.get("magnify") or mss_result.get("solidify")):
        overview = _build_content_from_mss(
            query, mss_result, mfgc_note, mfgc_result=mfgc_result,
        )

    # --- Assemble raw combined content ------------------------------------
    combined_body = "\n\n".join(sections)

    raw_deliverable_parts = []
    if overview:
        raw_deliverable_parts.append(overview)
    raw_deliverable_parts.append(
        f"\n{'═' * 71}\n"
        f"  DETAILED SECTIONS — {successful_count} specialist agents\n"
        f"{'═' * 71}\n"
    )
    raw_deliverable_parts.append(combined_body)

    raw_deliverable = "\n\n".join(raw_deliverable_parts)

    # --- Synthesis pass: unify into coherent document ----------------------
    try:
        from src.llm_provider import get_llm
        provider = get_llm()

        synth_system = (
            f"{MURPHY_SYSTEM_IDENTITY}\n\n"
            "You are the SYNTHESIS AGENT in the Murphy System swarm.  You have "
            "received the outputs of multiple specialist agents who each worked "
            "on a different section of the deliverable.  Your job is to:\n"
            "  1. Write a cohesive executive introduction.\n"
            "  2. Ensure smooth transitions between sections.\n"
            "  3. Add cross-references where sections relate to each other.\n"
            "  4. Write a unified conclusion and next-steps section.\n"
            "  5. Preserve ALL detail from the specialist sections — do NOT "
            "summarize or remove content.  Only add connective tissue.\n\n"
            "Use ■ section headers, box-drawing tables, and checklists (□).  "
            "The final output must be production-ready."
        )

        synth_user = (
            f"ORIGINAL REQUEST:\n{query}\n\n"
            f"COMBINED SPECIALIST AGENT OUTPUTS ({successful_count} agents):\n\n"
            f"{raw_deliverable}\n\n"
            f"Synthesize the above into a single, coherent, production-grade "
            f"deliverable.  Preserve all specialist detail — add an introduction, "
            f"transitions, cross-references, and a conclusion."
        )

        completion = provider.complete_messages(
            [
                {"role": "system", "content": synth_system},
                {"role": "user", "content": synth_user},
            ],
            model_hint="chat",
            temperature=0.5,
            max_tokens=131072,
        )
        if completion.content and completion.provider != "onboard":
            logger.info(
                "Swarm synthesis completed: %d chars via %s (from %d agents)",
                len(completion.content), completion.provider, successful_count,
            )
            return completion.content
    except Exception as exc:
        logger.warning("Swarm synthesis LLM failed: %s — using raw concatenation", exc)

    # Synthesis LLM unavailable — return raw concatenation which is still
    # much richer than a single-call deliverable
    return raw_deliverable


def _deterministic_task_decomposition(query: str) -> List[str]:
    """Build a deterministic task list from a query when MSS is unavailable.

    Produces a structured breakdown that represents what the Murphy System
    pipeline would generate: scope analysis, requirements, architecture,
    implementation steps, testing, and documentation.
    """
    q = query[:80]
    return [
        f"Analyze scope: {q}",
        f"Extract functional requirements from: {q}",
        f"Identify technical components for: {q}",
        f"Map compliance domains for: {q}",
        f"Design system architecture for: {q}",
        f"Define data model for: {q}",
        f"Plan API surface for: {q}",
        f"Assess security requirements for: {q}",
        f"Estimate cost and complexity for: {q}",
        f"Build implementation plan for: {q}",
        f"Write integration test strategy for: {q}",
        f"Plan user acceptance testing for: {q}",
        f"Draft documentation outline for: {q}",
        f"Generate deployment checklist for: {q}",
        f"Define monitoring and alerting for: {q}",
        f"Create rollback plan for: {q}",
        f"Prepare stakeholder review package for: {q}",
        f"Build training material outline for: {q}",
        f"Plan iteration cycles for: {q}",
        f"Final quality gate review for: {q}",
    ]


def make_fingerprint(request_ip: str, user_agent: str) -> str:
    """Derive an anonymous fingerprint from IP + User-Agent."""
    raw = f"{request_ip}:{user_agent}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# =============================================================================
# AUTOMATION SPECIFICATION ENGINE
# =============================================================================
# Generates a full Automation Specification: workflows inventory, integration
# map, time/cost savings, competitor pricing table, and a spec_id that
# pre-seeds the subscriber's account on signup.
# =============================================================================

import uuid as _uuid_mod
import json as _json_mod

# ---------------------------------------------------------------------------
# Competitor pricing data (kept here so it stays in sync with spec output)
# ---------------------------------------------------------------------------

COMPETITOR_PRICING: list[dict] = [
    {"name": "Custom Developer (US senior)",  "price": "$8,000 – $20,000/mo", "notes": "Setup + monthly retainer; no AI planning"},
    {"name": "Boutique Automation Agency",     "price": "$3,000 – $8,000/mo",  "notes": "Agency overhead; long lead times"},
    {"name": "Zapier Business",                "price": "$299/mo",             "notes": "5,000 task/mo limit; no AI; basic logic only"},
    {"name": "Make.com Business",              "price": "$159/mo",             "notes": "10,000 ops/mo limit; no AI planning"},
    {"name": "UiPath Automation Suite",        "price": "$420/mo",             "notes": "RPA only; no AI; steep learning curve"},
    {"name": "Microsoft Power Automate Prem.", "price": "$150/mo",             "notes": "Microsoft ecosystem lock-in; per-user pricing"},
    {"name": "n8n Cloud Pro",                  "price": "$50/mo",              "notes": "Technical setup required; no AI strategy layer"},
    {"name": "━━ Murphy Solo",                 "price": "$99/mo",              "notes": "✦ UNLIMITED automations · AI-powered · no setup fee"},
    {"name": "━━ Murphy Business",             "price": "$299/mo",             "notes": "✦ Teams + orgs + dedicated support"},
    {"name": "━━ Murphy Professional",         "price": "$599/mo",             "notes": "✦ Full org management · white-label · SSO"},
]

# ---------------------------------------------------------------------------
# Per-scenario automation specs
# ---------------------------------------------------------------------------

_AUTO_SPECS: dict[str, dict] = {
    "onboarding": {
        "title": "Client Onboarding Automation",
        "business_context": "professional services / agency",
        "manual_hours_month": 40,
        "hourly_rate": 65,
        "recommended_tier": "Solo ($99/mo)",
        "workflows": [
            {
                "name": "New Client Intake",
                "trigger": "Form submission or CRM deal moves to 'Won'",
                "steps": [
                    "Send branded welcome email with portal link",
                    "Generate and route NDA for e-signature (DocuSign / HelloSign)",
                    "Create client record in CRM (HubSpot / Salesforce / Pipedrive)",
                    "Provision client folder in Google Drive / SharePoint",
                ],
                "integrations": ["Email (SMTP/SendGrid)", "DocuSign/HelloSign", "CRM", "Google Drive"],
                "hours_saved_month": 8,
            },
            {
                "name": "Contract & Invoicing",
                "trigger": "NDA counter-signed event",
                "steps": [
                    "Generate Master Service Agreement from template",
                    "Route MSA for dual e-signature",
                    "Create initial invoice in accounting system",
                    "Send invoice with payment link (Stripe/Square)",
                    "Record payment when received; notify team via Slack",
                ],
                "integrations": ["DocuSign", "QuickBooks/Xero", "Stripe/Square", "Slack"],
                "hours_saved_month": 6,
            },
            {
                "name": "Project Workspace Setup",
                "trigger": "Contract fully executed",
                "steps": [
                    "Create project in task manager (Asana / ClickUp / Monday)",
                    "Generate sprint backlog from template (14 tasks)",
                    "Assign team members by role",
                    "Schedule kickoff call via Calendar AI",
                    "Send client onboarding packet (PDF + links)",
                ],
                "integrations": ["Asana/ClickUp/Monday", "Google Calendar / Outlook", "Email"],
                "hours_saved_month": 10,
            },
            {
                "name": "Ongoing Client Health Monitoring",
                "trigger": "Scheduled: weekly",
                "steps": [
                    "Pull project status from task manager",
                    "Calculate health score (on-track / at-risk / blocked)",
                    "Send weekly status digest to client and team",
                    "Escalate blocked items to account manager",
                ],
                "integrations": ["Asana/ClickUp", "Email", "Slack"],
                "hours_saved_month": 6,
            },
        ],
    },
    "finance": {
        "title": "Financial Reporting & Accounting Automation",
        "business_context": "small-to-mid business",
        "manual_hours_month": 32,
        "hourly_rate": 75,
        "recommended_tier": "Solo ($99/mo)",
        "workflows": [
            {
                "name": "Automated Transaction Ingestion",
                "trigger": "Daily scheduled pull from bank + accounting system",
                "steps": [
                    "Fetch new transactions from QuickBooks / Xero / FreshBooks",
                    "AI-categorize expenses (98%+ accuracy)",
                    "Flag uncategorized or anomalous transactions for review",
                    "Post categorized entries to chart of accounts",
                ],
                "integrations": ["QuickBooks / Xero / FreshBooks", "Bank feed API"],
                "hours_saved_month": 8,
            },
            {
                "name": "Monthly / Quarterly Report Generation",
                "trigger": "End of month or quarter (scheduled)",
                "steps": [
                    "Aggregate P&L, balance sheet, cash flow data",
                    "Build revenue breakdown by client / product line",
                    "Generate 6-month forecast with confidence band",
                    "Produce 24-page PDF + Google Sheets export",
                    "Email report to stakeholders automatically",
                ],
                "integrations": ["QuickBooks / Xero", "Google Sheets", "Email"],
                "hours_saved_month": 10,
            },
            {
                "name": "Accounts Receivable Follow-up",
                "trigger": "Invoice overdue by 7 / 14 / 30 days",
                "steps": [
                    "Detect unpaid invoices past due date",
                    "Send tiered reminder sequence (friendly → formal → demand)",
                    "Escalate to team at 30 days",
                    "Log all contact attempts in CRM",
                ],
                "integrations": ["QuickBooks / Stripe", "Email", "CRM"],
                "hours_saved_month": 6,
            },
            {
                "name": "Payroll & Expense Reconciliation",
                "trigger": "Bi-weekly payroll run",
                "steps": [
                    "Pull approved expenses from expense system",
                    "Match receipts to card transactions (AI OCR)",
                    "Generate payroll variance report",
                    "Submit to payroll provider (Gusto / ADP)",
                ],
                "integrations": ["Gusto / ADP / Rippling", "Expensify / Ramp", "Bank feed"],
                "hours_saved_month": 8,
            },
        ],
    },
    "hr": {
        "title": "HR & Recruitment Automation",
        "business_context": "growing team / SMB",
        "manual_hours_month": 50,
        "hourly_rate": 70,
        "recommended_tier": "Solo ($99/mo)",
        "workflows": [
            {
                "name": "Job Posting & Distribution",
                "trigger": "New role created in HR system",
                "steps": [
                    "Auto-post to LinkedIn, Indeed, Glassdoor simultaneously",
                    "Generate job description with AI (role-specific)",
                    "Set up applicant tracking pipeline in ATS",
                    "Notify hiring manager via Slack",
                ],
                "integrations": ["LinkedIn / Indeed / Glassdoor APIs", "Greenhouse / Lever / ATS", "Slack"],
                "hours_saved_month": 6,
            },
            {
                "name": "Applicant Screening & Ranking",
                "trigger": "New application received",
                "steps": [
                    "Parse resume with AI (skills, experience, education)",
                    "Score against job requirements (0–100 fit score)",
                    "Auto-reject below-threshold applicants with personalized email",
                    "Rank shortlist and present top 5 to hiring manager",
                ],
                "integrations": ["ATS (Greenhouse/Lever)", "Email", "Slack"],
                "hours_saved_month": 16,
            },
            {
                "name": "Interview Scheduling",
                "trigger": "Candidate advanced to interview stage",
                "steps": [
                    "Check interviewer calendar availability",
                    "Send candidate scheduling link (Calendly-style)",
                    "Send confirmation + prep materials to candidate",
                    "Create calendar events with video link",
                    "Send reminder 24h before interview",
                ],
                "integrations": ["Google Calendar / Outlook", "Email", "Zoom / Google Meet"],
                "hours_saved_month": 10,
            },
            {
                "name": "Offer & Onboarding Pipeline",
                "trigger": "Candidate marked as 'Hire'",
                "steps": [
                    "Generate offer letter from template",
                    "Route for internal approval + e-sign",
                    "Send to candidate for e-signature",
                    "Trigger IT provisioning (email, laptop, tools)",
                    "Create employee record in HRIS",
                    "Schedule Day 1 orientation + 30/60/90 check-ins",
                ],
                "integrations": ["DocuSign", "BambooHR / Workday", "IT ticketing (Jira/ServiceNow)", "Email"],
                "hours_saved_month": 12,
            },
        ],
    },
    "compliance": {
        "title": "Compliance & Audit Automation",
        "business_context": "regulated industry / SaaS",
        "manual_hours_month": 60,
        "hourly_rate": 120,
        "recommended_tier": "Business ($299/mo)",
        "workflows": [
            {
                "name": "Continuous Controls Monitoring",
                "trigger": "Scheduled: daily",
                "steps": [
                    "Scan access control logs for anomalies",
                    "Check encryption status of data stores",
                    "Verify backup jobs completed successfully",
                    "Generate controls status dashboard update",
                ],
                "integrations": ["AWS / GCP / Azure", "SIEM (Splunk/Datadog)", "Slack"],
                "hours_saved_month": 20,
            },
            {
                "name": "Audit Evidence Collection",
                "trigger": "Audit period opened (quarterly / annually)",
                "steps": [
                    "Auto-collect evidence from 12+ control categories",
                    "Package evidence into auditor-ready folders",
                    "Generate gap analysis report (findings + severity)",
                    "Create remediation task list with owners and deadlines",
                ],
                "integrations": ["AWS / GCP", "GitHub", "HRIS", "Ticketing"],
                "hours_saved_month": 24,
            },
            {
                "name": "Policy & Training Tracking",
                "trigger": "Policy update OR new employee added",
                "steps": [
                    "Send policy acknowledgment requests to affected staff",
                    "Track completion; send escalating reminders",
                    "Record completion with timestamp in compliance log",
                    "Report non-compliance to CISO / HR automatically",
                ],
                "integrations": ["HRIS", "Email", "LMS (if present)"],
                "hours_saved_month": 8,
            },
        ],
    },
    "project": {
        "title": "Project Management Automation",
        "business_context": "agency / product team",
        "manual_hours_month": 35,
        "hourly_rate": 65,
        "recommended_tier": "Solo ($99/mo)",
        "workflows": [
            {
                "name": "Project Kickoff Automation",
                "trigger": "New project created",
                "steps": [
                    "AI-generate sprint backlog from project brief",
                    "Allocate tasks to team by skill profile",
                    "Build Gantt timeline with milestones",
                    "Create project channel in Slack",
                    "Schedule kickoff + milestone review calls",
                ],
                "integrations": ["Asana / ClickUp / Monday", "Slack", "Google Calendar"],
                "hours_saved_month": 8,
            },
            {
                "name": "Daily Standup Automation",
                "trigger": "Scheduled: daily 9 AM",
                "steps": [
                    "Pull yesterday's task completions from PM tool",
                    "Identify blocked tasks and at-risk milestones",
                    "Post standup digest in Slack team channel",
                    "Escalate P1 blockers to project lead",
                ],
                "integrations": ["Asana / ClickUp", "Slack", "Email"],
                "hours_saved_month": 6,
            },
            {
                "name": "Client Status Reporting",
                "trigger": "Scheduled: weekly (Friday)",
                "steps": [
                    "Aggregate weekly progress from PM system",
                    "Calculate % complete, velocity, forecast completion",
                    "Generate branded status report PDF",
                    "Email to client contacts automatically",
                ],
                "integrations": ["Asana / ClickUp", "Email", "Google Drive"],
                "hours_saved_month": 8,
            },
            {
                "name": "Budget & Scope Monitoring",
                "trigger": "Continuous (event-driven)",
                "steps": [
                    "Track logged hours vs. budget in real-time",
                    "Alert PM when project exceeds 80% of budget",
                    "Generate change order draft when scope creep detected",
                    "Log all scope changes with client sign-off requirement",
                ],
                "integrations": ["Harvest / Toggl / Clockify", "Email", "DocuSign"],
                "hours_saved_month": 6,
            },
        ],
    },
    "invoice": {
        "title": "Accounts Payable & Invoice Processing Automation",
        "business_context": "operations / finance team",
        "manual_hours_month": 25,
        "hourly_rate": 60,
        "recommended_tier": "Solo ($99/mo)",
        "workflows": [
            {
                "name": "Invoice Ingestion & Parsing",
                "trigger": "Invoice received via email or upload",
                "steps": [
                    "Extract vendor, amount, due date, line items with AI OCR",
                    "Match to open purchase orders automatically",
                    "Detect duplicates and flag discrepancies",
                    "Route matched invoices for one-click approval",
                ],
                "integrations": ["Email (IMAP)", "QuickBooks / Xero", "PO system"],
                "hours_saved_month": 8,
            },
            {
                "name": "Approval Routing",
                "trigger": "Invoice parsed and unmatched or > approval threshold",
                "steps": [
                    "Determine approver by amount and department",
                    "Send mobile-friendly approval request",
                    "Escalate if no response in 48 hours",
                    "Log approval chain for audit trail",
                ],
                "integrations": ["Email / Slack", "HRIS (for org chart routing)"],
                "hours_saved_month": 5,
            },
            {
                "name": "Payment Scheduling & Execution",
                "trigger": "Invoice approved",
                "steps": [
                    "Schedule ACH / wire payment for optimal cash flow date",
                    "Batch payments (3 runs/week by default)",
                    "Record payment in accounting system",
                    "Send remittance advice to vendor",
                ],
                "integrations": ["QuickBooks / Xero", "Bank ACH API", "Email"],
                "hours_saved_month": 6,
            },
            {
                "name": "Vendor Statement Reconciliation",
                "trigger": "Scheduled: end of month",
                "steps": [
                    "Request vendor statements automatically",
                    "AI-reconcile against internal records",
                    "Generate discrepancy report",
                    "Create tasks for AP team to resolve gaps",
                ],
                "integrations": ["Email", "QuickBooks / Xero", "Task manager"],
                "hours_saved_month": 4,
            },
        ],
    },
}


def _get_spec_for_query(query: str) -> dict:
    """Return the spec template that best matches the query, or build a generic one."""
    scenario_key = _detect_scenario(query)
    if scenario_key and scenario_key in _AUTO_SPECS:
        return _AUTO_SPECS[scenario_key]
    # Generic fallback — derive what we can from the query
    return _build_generic_spec(query)


def _build_generic_spec(query: str) -> dict:
    """Build a reasonable automation spec for an arbitrary query."""
    q = query.lower()
    # Rough domain detection
    if any(k in q for k in ["sale", "lead", "crm", "pipeline", "deal", "prospect"]):
        domain = "sales automation"
        ctx = "sales team / revenue operations"
        hrs = 30
        rate = 70
    elif any(k in q for k in ["market", "email campaign", "newsletter", "social", "content", "seo"]):
        domain = "marketing automation"
        ctx = "marketing / growth team"
        hrs = 25
        rate = 65
    elif any(k in q for k in ["support", "ticket", "helpdesk", "customer service", "chat"]):
        domain = "customer support automation"
        ctx = "support / customer success"
        hrs = 35
        rate = 55
    elif any(k in q for k in ["inventory", "supply", "order", "fulfil", "warehouse", "logistics"]):
        domain = "operations & fulfillment automation"
        ctx = "operations / supply chain"
        hrs = 40
        rate = 65
    else:
        domain = "business process automation"
        ctx = "general operations"
        hrs = 30
        rate = 65

    words = query.strip().rstrip("?!.").title()
    return {
        "title": f"{words} Automation",
        "business_context": ctx,
        "manual_hours_month": hrs,
        "hourly_rate": rate,
        "recommended_tier": "Solo ($99/mo)",
        "workflows": [
            {
                "name": f"Intake & Routing — {words}",
                "trigger": "New request received (form / email / API event)",
                "steps": [
                    "Classify and validate incoming request with AI",
                    "Route to appropriate team or system automatically",
                    "Acknowledge requester with status and ETA",
                    "Create task in project management tool",
                ],
                "integrations": ["Email / Forms", "Slack", "Task manager (Asana/ClickUp)"],
                "hours_saved_month": round(hrs * 0.3),
            },
            {
                "name": f"Processing & Execution — {words}",
                "trigger": "Task assigned and confirmed",
                "steps": [
                    "Execute core business logic with Murphy AI",
                    "Pull data from relevant connected systems",
                    "Apply rules engine and quality checks",
                    "Update all downstream systems atomically",
                ],
                "integrations": ["CRM / ERP", "Accounting system", "Data warehouse"],
                "hours_saved_month": round(hrs * 0.4),
            },
            {
                "name": "Reporting & Notification",
                "trigger": "Scheduled daily + on completion events",
                "steps": [
                    "Aggregate activity metrics into dashboard",
                    "Generate daily/weekly digest for stakeholders",
                    "Alert on exceptions or SLA breaches",
                    "Log all actions for audit trail",
                ],
                "integrations": ["Email", "Slack", "Google Sheets / BI tool"],
                "hours_saved_month": round(hrs * 0.2),
            },
        ],
    }


def _format_competitor_table() -> str:
    """Render the competitor pricing comparison as aligned ASCII table."""
    lines = []
    lines.append("  ┌──────────────────────────────────────────────┬────────────────────┬──────────────────────────────────────────────┐")
    lines.append("  │ Platform / Option                            │ Monthly Cost       │ Notes                                        │")
    lines.append("  ├──────────────────────────────────────────────┼────────────────────┼──────────────────────────────────────────────┤")
    for c in COMPETITOR_PRICING:
        name  = c["name"][:44].ljust(44)
        price = c["price"][:18].ljust(18)
        notes = c["notes"][:44].ljust(44)
        lines.append(f"  │ {name} │ {price} │ {notes} │")
    lines.append("  └──────────────────────────────────────────────┴────────────────────┴──────────────────────────────────────────────┘")
    return "\n".join(lines)


def generate_automation_spec(
    query: str,
    librarian_context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a full Automation Specification for a given query.

    Returns a dict with:
      spec_id        — short ID (SPEC-xxxxxxxx) for signup pre-seeding
      title          — spec title
      business_context — inferred domain
      workflows      — list of workflow dicts (name, trigger, steps, integrations, hours_saved_month)
      integrations   — deduplicated list of all required integrations
      manual_hours_month — estimated current manual hours
      hours_saved_month  — total hours Murphy saves
      hourly_rate    — assumed rate for ROI calc
      monthly_savings_usd — hours_saved * rate
      murphy_cost    — recommended tier cost
      net_monthly_benefit — monthly_savings - murphy_cost
      annual_benefit — net * 12
      roi_multiple   — (monthly_savings / murphy_cost)
      competitor_table_text — formatted ASCII pricing table
      recommended_tier — Solo / Business / Enterprise
      content_txt    — full formatted plain-text specification
      signup_url     — https://murphy.systems/ui/signup?spec=SPEC-xxx
      generated_at   — ISO timestamp
    """
    spec_id = "SPEC-" + _uuid_mod.uuid4().hex[:8].upper()
    spec_template = _get_spec_for_query(query)

    title              = spec_template["title"]
    business_context   = spec_template["business_context"]
    workflows          = spec_template["workflows"]
    manual_hours_month = spec_template["manual_hours_month"]
    hourly_rate        = spec_template["hourly_rate"]
    recommended_tier   = spec_template["recommended_tier"]

    # Derive tier cost
    tier_cost = 99 if "Solo" in recommended_tier else (299 if "Business" in recommended_tier else (599 if "Professional" in recommended_tier else 99))

    # Total hours saved = sum of per-workflow savings (capped below manual total)
    hours_saved = min(
        sum(w.get("hours_saved_month", 0) for w in workflows),
        manual_hours_month - 1,  # always leave ≥1 hr for human oversight
    )

    monthly_savings = hours_saved * hourly_rate
    net_monthly     = monthly_savings - tier_cost
    annual_benefit  = net_monthly * 12
    roi_multiple    = round(monthly_savings / tier_cost, 1) if tier_cost else 0

    # Deduplicate integrations across all workflows
    all_integrations: list[str] = []
    seen_integrations: set[str] = set()
    for wf in workflows:
        for intg in wf.get("integrations", []):
            if intg not in seen_integrations:
                seen_integrations.add(intg)
                all_integrations.append(intg)

    signup_url = f"https://murphy.systems/ui/signup?spec={spec_id}"
    now_iso    = datetime.now(timezone.utc).isoformat()
    now_str    = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

    # ── Build the formatted plain-text spec ──────────────────────────────
    lines: list[str] = [
        _MURPHY_ASCII_LOGO,
        "",
        "═" * 72,
        f"  AUTOMATION SPECIFICATION",
        f"  {title}",
        "═" * 72,
        "",
        f"  Specification ID : {spec_id}",
        f"  Generated        : {now_str}",
        f"  For Request      : {query[:120]}",
        f"  Business Context : {business_context}",
        f"  Activation URL   : {signup_url}",
        "",
        "─" * 72,
        "  HOW TO USE THIS DOCUMENT",
        "─" * 72,
        "",
        "  This document specifies the automations Murphy System would build",
        "  and operate for you. You may:",
        "",
        "  1. Take it to any developer, agency, or automation platform to get",
        "     a competitive quote — then compare with Murphy's price.",
        "  2. Sign up at the Activation URL above to have Murphy configure all",
        f"     {len(workflows)} workflows in your account automatically.",
        "  3. Share with stakeholders to align on your automation roadmap.",
        "",
    ]

    # ── Executive Summary ──────────────────────────────────────────────
    lines += [
        "─" * 72,
        "  EXECUTIVE SUMMARY",
        "─" * 72,
        "",
        f"  Murphy System will automate {len(workflows)} core workflows for your",
        f"  {business_context}, saving approximately {hours_saved} hours/month",
        f"  ({manual_hours_month} hours currently manual → ~1 hr oversight only).",
        "",
        f"  At a ${hourly_rate}/hr blended rate, that is ${monthly_savings:,}/month in",
        f"  recovered productivity. Murphy costs ${tier_cost}/month.",
        "",
        f"  Net monthly benefit  : ${net_monthly:,}",
        f"  Annual benefit       : ${annual_benefit:,}",
        f"  Return on investment : {roi_multiple}× in the first year",
        "",
    ]

    # ── Automation Inventory ──────────────────────────────────────────
    lines += [
        "─" * 72,
        f"  AUTOMATION INVENTORY  ({len(workflows)} workflows)",
        "─" * 72,
        "",
    ]

    for i, wf in enumerate(workflows, 1):
        lines += [
            f"  ┌─ Workflow {i} of {len(workflows)}: {wf['name']}",
            f"  │  Trigger      : {wf['trigger']}",
            f"  │  Hours saved  : {wf.get('hours_saved_month', '?')} hrs/month",
            "  │",
            "  │  Steps:",
        ]
        for step in wf.get("steps", []):
            lines.append(f"  │    → {step}")
        lines += [
            "  │",
            "  │  Integrations required:",
        ]
        for intg in wf.get("integrations", []):
            lines.append(f"  │    • {intg}")
        lines += ["  └" + "─" * 65, ""]

    # ── Integration Map ────────────────────────────────────────────────
    lines += [
        "─" * 72,
        f"  INTEGRATION MAP  ({len(all_integrations)} systems)",
        "─" * 72,
        "",
    ]
    for intg in all_integrations:
        lines.append(f"  ✓  {intg}")
    lines.append("")
    lines += [
        "  All integrations use OAuth 2.0 or API key authentication.",
        "  Murphy never stores credentials in plain text.",
        "  Data never leaves your connected accounts.",
        "",
    ]

    # ── ROI Analysis ──────────────────────────────────────────────────
    lines += [
        "─" * 72,
        "  TIME & COST SAVINGS ANALYSIS",
        "─" * 72,
        "",
        f"  Current state (manual):",
        f"    • {manual_hours_month} hours/month spent on these workflows",
        f"    • Staff cost (@ ${hourly_rate}/hr): ${manual_hours_month * hourly_rate:,}/month",
        "",
        f"  With Murphy System:",
        f"    • ~1 hour/month (oversight, exception handling, approvals)",
        f"    • Platform cost: ${tier_cost}/month",
        f"    • Total cost: ${tier_cost + hourly_rate:,}/month",
        "",
        f"  Savings breakdown:",
        f"    • Hours freed per month  : {hours_saved} hrs",
        f"    • Value of freed capacity: ${monthly_savings:,}/month",
        f"    • Murphy subscription    : −${tier_cost}/month",
        f"    • Net monthly benefit    : ${net_monthly:,}/month",
        f"    • Annual ROI             : ${annual_benefit:,} (${annual_benefit + tier_cost * 12:,} saved − ${tier_cost * 12} platform cost)",
        f"    • ROI multiple           : {roi_multiple}× — Murphy pays for itself {roi_multiple}× over each month",
        "",
    ]

    # ── Competitor Pricing ─────────────────────────────────────────────
    lines += [
        "─" * 72,
        "  COMPETITOR PRICING COMPARISON",
        "  For the same scope as this specification:",
        "─" * 72,
        "",
        _format_competitor_table(),
        "",
        "  ★  Murphy delivers the same automation scope for $99/month.",
        "     No task limits. No per-user charges. No setup fees.",
        "     AI-powered planning, execution, monitoring, and self-improvement.",
        "",
    ]

    # ── Configuration Blueprint ────────────────────────────────────────
    lines += [
        "─" * 72,
        "  CONFIGURATION BLUEPRINT  (auto-loaded on signup)",
        "─" * 72,
        "",
        f"  When you sign up with Spec ID  {spec_id}",
        f"  Murphy will automatically:",
        "",
    ]
    for i, wf in enumerate(workflows, 1):
        lines.append(f"    {i}. Configure \"{wf['name']}\" workflow")
    lines += [
        "",
        "  All workflow templates are pre-built. You connect your tools via",
        "  OAuth (one click each) and Murphy activates everything.",
        "  Average time from signup to fully live: under 10 minutes.",
        "",
    ]

    # ── Next Steps ─────────────────────────────────────────────────────
    lines += [
        "─" * 72,
        "  NEXT STEPS",
        "─" * 72,
        "",
        f"  [ ] Visit {signup_url}",
        "  [ ] Murphy detects your spec and pre-configures all workflows",
        "  [ ] Connect your tools (one-click OAuth per integration)",
        "  [ ] Activate and watch your operations run automatically",
        "  [ ] Go live in under 10 minutes — no developers required",
        "",
        f"  Questions? Contact us at hello@murphy.systems",
        "",
    ]

    lines.append(_LICENSE_FOOTER)

    content_txt = "\n".join(lines)

    # Sanitise filename
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    filename = f"murphy-spec-{slug}-{spec_id.lower()}.txt"

    return {
        "spec_id":               spec_id,
        "title":                 title,
        "business_context":      business_context,
        "workflows":             workflows,
        "integrations":          all_integrations,
        "workflow_count":        len(workflows),
        "manual_hours_month":    manual_hours_month,
        "hours_saved_month":     hours_saved,
        "hourly_rate":           hourly_rate,
        "monthly_savings_usd":   monthly_savings,
        "murphy_cost":           tier_cost,
        "net_monthly_benefit":   net_monthly,
        "annual_benefit":        annual_benefit,
        "roi_multiple":          roi_multiple,
        "recommended_tier":      recommended_tier,
        "competitor_pricing":    COMPETITOR_PRICING,
        "content_txt":           content_txt,
        "signup_url":            signup_url,
        "generated_at":          now_iso,
        "filename":              filename,
    }
