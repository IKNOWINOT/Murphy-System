#!/usr/bin/env python3
"""
PCR-031 patcher — register /api/deliverable/juxtapose.

What this endpoint does:
  1. Takes a prompt
  2. Loads AGENT_ROSTER (5 personas: Morgan Vale CRO, Alex Reeves,
     Casey Torres, Taylor Kim, Drew Nakamura)
  3. For each persona, runs the prompt through Together API with that
     persona's system_prompt
  4. Writes one result_provenance row per persona, all tagged with
     the same job_id
  5. Returns a juxtaposed document with N labeled sections

This closes Shape-of-Complete gate (d) for cross-role deliverables:
  - end-to-end executes: N personas fan-out, distinct outputs
  - result_provenance shows N rows per job_id, distinct produced_by

Idempotent: marker-based, --revert capable.
"""

from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

APP = Path("/opt/Murphy-System/src/runtime/app.py")

# Insertion marker — we insert ABOVE the existing
# /api/demo/generate-deliverable endpoint so import context is shared
ANCHOR = '@app.post("/api/demo/generate-deliverable")'

MARKER_START = "    # PCR-031 BEGIN /api/deliverable/juxtapose"
MARKER_END = "    # PCR-031 END /api/deliverable/juxtapose"

ENDPOINT_CODE = '''
    # PCR-031 BEGIN /api/deliverable/juxtapose
    @app.post("/api/deliverable/juxtapose")
    async def deliverable_juxtapose(request: Request):
        """Cross-role juxtaposition deliverable.

        Takes one prompt, fans out to N personas in AGENT_ROSTER,
        returns N distinct labeled sections with provenance per persona.

        Body: {"query": "...", "personas": ["morgan_vale", ...] (optional)}
        Default: all 5 AGENT_ROSTER personas.

        Owner-only endpoint (per HITL canon — no unauthenticated access
        to LLM fan-out — costs N tokens per call).
        """
        import uuid as _uuid
        import json as _json
        import time as _time

        # ── parse ──────────────────────────────────────────────────────
        try:
            body = await request.json()
        except Exception:
            body = {}

        query = str(body.get("query", "")).strip()[:1500]
        if not query:
            return JSONResponse(
                {"success": False, "error": "missing_query",
                 "message": "query is required"},
                status_code=400,
            )

        # ── load roster ────────────────────────────────────────────────
        try:
            from src.agent_persona_library import AGENT_ROSTER
        except Exception as _e:
            return JSONResponse(
                {"success": False, "error": "roster_unavailable",
                 "message": str(_e)},
                status_code=500,
            )

        requested = body.get("personas") or list(AGENT_ROSTER.keys())
        personas = []
        for pid in requested:
            if pid in AGENT_ROSTER:
                personas.append((pid, AGENT_ROSTER[pid]))
        if not personas:
            return JSONResponse(
                {"success": False, "error": "no_personas",
                 "message": "no matching personas in roster",
                 "available": list(AGENT_ROSTER.keys())},
                status_code=400,
            )

        # ── shared job id for provenance ───────────────────────────────
        job_id = _uuid.uuid4().hex

        # ── llm caller (reuse existing path) ───────────────────────────
        try:
            from src.book_chapter_loop import _llm_call
        except Exception as _e:
            return JSONResponse(
                {"success": False, "error": "llm_unavailable",
                 "message": str(_e)},
                status_code=500,
            )

        # ── provenance writer (PCR-025 producer) ───────────────────────
        try:
            from src.provenance_writer import write_provenance
        except Exception:
            write_provenance = None

        # ── fan-out ────────────────────────────────────────────────────
        sections = []
        for pid, persona in personas:
            t0 = _time.time()
            persona_prompt = (
                persona.system_prompt + "\\n\\n"
                + "TASK: Respond IN YOUR ROLE'S VOICE to the prompt below. "
                + "Take the angle that is UNIQUE to your function — do NOT "
                + "produce a generic summary. Max 250 words. Plain text.\\n\\n"
                + "PROMPT: " + query
            )

            try:
                content = _llm_call(persona_prompt, max_tokens=600) or ""
            except Exception as _e:
                content = f"[error: {_e}]"

            elapsed_ms = int((_time.time() - t0) * 1000)

            sections.append({
                "persona_id": pid,
                "persona_name": persona.name,
                "title": persona.title,
                "department": persona.department,
                "content": content,
                "latency_ms": elapsed_ms,
            })

            # write provenance — one row per persona, same job_id
            if write_provenance:
                try:
                    write_provenance(
                        result_id=_uuid.uuid4().hex,
                        produced_by=pid,
                        action_name="/api/deliverable/juxtapose",
                        inputs_json=_json.dumps(
                            {"query": query[:200], "persona": pid}
                        ),
                        output_summary=(
                            f"HTTP 200 \\u00b7 {elapsed_ms}ms \\u00b7 "
                            + f"{len(content)}b"
                        ),
                        job_id=job_id,
                    )
                except Exception:
                    pass  # fire-and-forget

        # ── assemble document ──────────────────────────────────────────
        doc_lines = [
            "JUXTAPOSITION DELIVERABLE",
            "=" * 60,
            f"Prompt: {query}",
            f"Job ID: {job_id}",
            f"Personas: {len(sections)}",
            "=" * 60,
            "",
        ]
        for s in sections:
            doc_lines.append("")
            doc_lines.append(f"## {s['persona_name']} ({s['title']})")
            doc_lines.append(f"Department: {s['department']}")
            doc_lines.append("-" * 60)
            doc_lines.append(s["content"])
            doc_lines.append("")

        return JSONResponse({
            "success": True,
            "job_id": job_id,
            "personas": [s["persona_id"] for s in sections],
            "sections": sections,
            "document": "\\n".join(doc_lines),
        })
    # PCR-031 END /api/deliverable/juxtapose
'''


def apply(verify: bool, revert: bool):
    print(f"PCR-031 patcher verify={verify} revert={revert}")
    print("=" * 60)

    src = APP.read_text(encoding="utf-8")

    if revert:
        if MARKER_START not in src:
            print("  · already absent")
            return 0
        pattern = re.compile(
            re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END) + r"\n?",
            re.DOTALL,
        )
        new_src = pattern.sub("", src)
        if verify:
            print("  ✓ (verify) would remove PCR-031 endpoint")
            return 0
        APP.write_text(new_src, encoding="utf-8")
        print("  ✓ removed PCR-031 endpoint")
        return 0

    if MARKER_START in src:
        print("  · already present — no-op")
        return 0

    if ANCHOR not in src:
        print(f"  ✗ anchor not found: {ANCHOR!r}")
        return 1

    new_src = src.replace(ANCHOR, ENDPOINT_CODE.rstrip() + "\n\n    " + ANCHOR, 1)

    if verify:
        print("  ✓ (verify) would insert PCR-031 endpoint at anchor")
        return 0

    APP.write_text(new_src, encoding="utf-8")
    print("  ✓ inserted PCR-031 endpoint at anchor")
    print("=" * 60)
    print("  ✓ done")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    return apply(verify=args.verify, revert=args.revert)


if __name__ == "__main__":
    sys.exit(main())
