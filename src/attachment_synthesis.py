"""
Ship 31i.A — Attachment Synthesis with Honest Limits + Resume

Wraps attachment_parser extraction with:
  1. Honest capability matrix — say what we CAN'T do
  2. Chunked synthesis for content >3K tokens
  3. SQLite checkpoint table for resume after interruption
  4. Per-chunk role-perspective synthesis
  5. Final merge pass

Schema (entity_graph.db.attachment_synthesis_jobs):
  job_id TEXT PK
  attachment_hash TEXT      — sha256 of content
  filename TEXT
  content_type TEXT
  total_chunks INTEGER
  completed_chunks INTEGER
  status TEXT               — pending | in_progress | done | failed | cannot_handle
  role_hint TEXT
  partial_synthesis TEXT    — JSON list of per-chunk syntheses
  final_synthesis TEXT      — merged output once done
  failure_reason TEXT
  created_ts TEXT
  updated_ts TEXT
"""

import hashlib, json, sqlite3, time, logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = "/var/lib/murphy-production/entity_graph.db"
CHUNK_CHAR_TARGET = 12000          # ~3K tokens, safe for Llama-70B
CHUNK_OVERLAP_CHARS = 500          # overlap to preserve context
STALE_HOURS = 24                   # reclaim stalled jobs after this


# ─── Capability matrix — HONEST about what we can/cannot handle ──────
CAN_HANDLE = {
    "application/pdf": "pdfplumber",
    "application/msword": "best-effort docx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "python-docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "openpyxl",
    "application/vnd.ms-excel": "openpyxl",
    "text/plain": "direct",
    "text/csv": "pandas",
    "text/markdown": "direct",
    "message/rfc822": "email parse",
}

CANNOT_HANDLE = {
    "image/": "no vision model wired (Ship 31i.A scope: text only)",
    "video/": "no video analysis available",
    "audio/": "no audio transcription wired",
    "application/octet-stream": "unknown binary — please rename with proper extension",
    "application/zip": "archive extraction not yet wired",
    "application/x-tar": "archive extraction not yet wired",
    "model/": "CAD/3D models require specialized tooling not yet wired",
    "application/dicom": "medical imaging requires specialized handler",
}


def capability_check(content_type: str, size_bytes: int):
    """Return (can_handle: bool, reason: str)."""
    ct = (content_type or "").lower()
    for prefix, reason in CANNOT_HANDLE.items():
        if ct.startswith(prefix.rstrip("/")):
            return False, f"I cannot analyze this file type ({ct}): {reason}"
    if ct in CAN_HANDLE:
        if size_bytes > 50 * 1024 * 1024:
            return False, f"File too large ({size_bytes/1e6:.1f} MB > 50 MB limit) — please send a smaller excerpt"
        return True, CAN_HANDLE[ct]
    return False, f"I cannot analyze this file type ({ct}): no extractor configured"


# ─── Schema management ────────────────────────────────────────────────
def ensure_schema():
    c = sqlite3.connect(DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS attachment_synthesis_jobs (
        job_id TEXT PRIMARY KEY,
        attachment_hash TEXT NOT NULL,
        filename TEXT,
        content_type TEXT,
        size_bytes INTEGER,
        role_hint TEXT,
        vertical TEXT,
        total_chunks INTEGER DEFAULT 0,
        completed_chunks INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        partial_synthesis TEXT,
        final_synthesis TEXT,
        failure_reason TEXT,
        extracted_text_preview TEXT,
        created_ts TEXT,
        updated_ts TEXT
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_attach_hash ON attachment_synthesis_jobs(attachment_hash)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_attach_status ON attachment_synthesis_jobs(status)")
    c.commit()
    c.close()


# ─── Chunking ─────────────────────────────────────────────────────────
def chunk_text(text: str, target=CHUNK_CHAR_TARGET, overlap=CHUNK_OVERLAP_CHARS):
    """Split text into overlapping chunks. Prefers paragraph boundaries."""
    if len(text) <= target:
        return [text]
    chunks = []
    pos = 0
    while pos < len(text):
        end = min(pos + target, len(text))
        # Try to break at paragraph boundary
        if end < len(text):
            para_break = text.rfind("\n\n", pos + target // 2, end)
            if para_break > pos:
                end = para_break
            else:
                # Fall back to sentence
                sent_break = text.rfind(". ", pos + target // 2, end)
                if sent_break > pos:
                    end = sent_break + 1
        chunks.append(text[pos:end])
        if end >= len(text):
            break
        pos = max(end - overlap, pos + 1)
    return chunks


# ─── Per-chunk synthesis ──────────────────────────────────────────────
def synthesize_chunk(chunk_text_val: str, chunk_idx: int, total_chunks: int,
                     role_hint: str, vertical: str = "general"):
    """Call LLM with role-tailored prompt on a single chunk.

    Generative — NO templates, just the model with focused instructions.
    """
    try:
        from src.llm_provider import get_llm
        llm = get_llm()
    except Exception as exc:
        return {"error": f"llm_provider unreachable: {exc}", "synthesis": "", "cost_usd": 0.0}

    prompt = f"""You are reading chunk {chunk_idx+1} of {total_chunks} from an attached document.

Your role perspective: {role_hint or 'general analyst'}
Domain: {vertical}

Extract from THIS CHUNK ONLY:
1. KEY FACTS — the specific numbers, names, dates, claims
2. DECISIONS / ASKS — what needs to happen or be answered
3. RISKS / GAPS — what's missing, ambiguous, or concerning from a {role_hint} lens
4. CONNECTION POINTS — references to other sections, exhibits, or external info

If this chunk is mostly boilerplate or has nothing of value for a {role_hint}, say so honestly.

CHUNK TEXT:
{chunk_text_val[:CHUNK_CHAR_TARGET]}

Respond in plain prose, 4-6 sentences. No headers, no bullets, no fluff."""

    t0 = time.time()
    try:
        result = llm.complete(prompt, model_hint="chat", max_tokens=400)
        text = (getattr(result, "content", "") or "").strip()
        tok_in = int(getattr(result, "tokens_prompt", 0) or 0)
        tok_out = int(getattr(result, "tokens_completion", 0) or 0)
        cost = (tok_in + tok_out) * 0.88e-6
        return {"synthesis": text, "elapsed_s": time.time() - t0,
                "tok_in": tok_in, "tok_out": tok_out, "cost_usd": cost}
    except Exception as exc:
        return {"error": f"llm call failed: {exc}", "synthesis": "",
                "elapsed_s": time.time() - t0, "cost_usd": 0.0}


def merge_syntheses(partial_list, role_hint: str, vertical: str = "general"):
    """Final pass: combine per-chunk syntheses into one coherent analysis."""
    if not partial_list:
        return "(no content extracted)"
    if len(partial_list) == 1:
        return partial_list[0]
    try:
        from src.llm_provider import get_llm
        llm = get_llm()
    except Exception as exc:
        return "\n\n".join(f"[chunk {i+1}] {s}" for i, s in enumerate(partial_list))

    joined = "\n\n".join(f"CHUNK {i+1}: {s}" for i, s in enumerate(partial_list))
    prompt = f"""You are a {role_hint or 'general analyst'} in the {vertical} domain.

Below are per-chunk syntheses from a single document. Merge them into ONE coherent analysis answering:
1. What is this document?
2. What are the 3-5 most important facts/numbers/dates a {role_hint} needs?
3. What decisions or actions does it ask for?
4. What are the top 2-3 risks or gaps from a {role_hint} perspective?
5. What follow-up questions should be asked?

Be concrete. No generic AI fluff. If the chunks contradict each other, flag it.

PER-CHUNK SYNTHESES:
{joined[:15000]}

Respond in plain prose, 8-12 sentences. No markdown."""

    try:
        result = llm.complete(prompt, model_hint="chat", max_tokens=600)
        return (getattr(result, "content", "") or "").strip()
    except Exception as exc:
        return "\n\n".join(f"[chunk {i+1}] {s}" for i, s in enumerate(partial_list))


# ─── Job lifecycle ────────────────────────────────────────────────────
def start_or_resume_job(attachment_blob: bytes, filename: str,
                        content_type: str, role_hint: str = "",
                        vertical: str = "general"):
    """Begin synthesis or resume from checkpoint.

    Returns dict with: job_id, status, final_synthesis (if done),
    progress (if in-progress), failure_reason (if can't handle).
    """
    ensure_schema()
    size = len(attachment_blob)
    att_hash = hashlib.sha256(attachment_blob).hexdigest()
    job_id = f"as_{att_hash[:16]}_{role_hint or 'gen'}"

    # Capability check first
    can, reason = capability_check(content_type, size)
    if not can:
        c = sqlite3.connect(DB_PATH)
        c.execute("""INSERT OR REPLACE INTO attachment_synthesis_jobs
            (job_id, attachment_hash, filename, content_type, size_bytes,
             role_hint, vertical, status, failure_reason, created_ts, updated_ts)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (job_id, att_hash, filename, content_type, size, role_hint, vertical,
             "cannot_handle", reason,
             datetime.now(timezone.utc).isoformat(),
             datetime.now(timezone.utc).isoformat()))
        c.commit(); c.close()
        return {"job_id": job_id, "status": "cannot_handle",
                "failure_reason": reason, "honest_signal": True}

    # Check for resume
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    existing = c.execute("SELECT * FROM attachment_synthesis_jobs WHERE job_id=?",
                         (job_id,)).fetchone()
    if existing and existing["status"] == "done":
        c.close()
        return {"job_id": job_id, "status": "done",
                "final_synthesis": existing["final_synthesis"],
                "from_cache": True}
    c.close()

    # Extract
    try:
        from src.attachment_parser import (_extract_pdf, _extract_docx,
                                            _extract_xlsx, _extract_text_plain,
                                            _extract_eml)
        ct = content_type.lower()
        if ct == "application/pdf":
            text = _extract_pdf(attachment_blob)
        elif "wordprocessingml" in ct or ct == "application/msword":
            text = _extract_docx(attachment_blob)
        elif "spreadsheetml" in ct or ct == "application/vnd.ms-excel":
            text = _extract_xlsx(attachment_blob)
        elif ct.startswith("text/"):
            text = _extract_text_plain(attachment_blob)
        elif ct == "message/rfc822":
            text = _extract_eml(attachment_blob)
        else:
            text = attachment_blob.decode("utf-8", errors="ignore")
    except Exception as exc:
        c = sqlite3.connect(DB_PATH)
        c.execute("""INSERT OR REPLACE INTO attachment_synthesis_jobs
            (job_id, attachment_hash, filename, content_type, size_bytes,
             role_hint, vertical, status, failure_reason, created_ts, updated_ts)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (job_id, att_hash, filename, content_type, size, role_hint, vertical,
             "failed", f"extraction error: {exc}",
             datetime.now(timezone.utc).isoformat(),
             datetime.now(timezone.utc).isoformat()))
        c.commit(); c.close()
        return {"job_id": job_id, "status": "failed",
                "failure_reason": f"extraction error: {exc}"}

    if not text or len(text.strip()) < 20:
        return {"job_id": job_id, "status": "cannot_handle",
                "failure_reason": "Extracted file but no readable text content. Possibly scanned PDF (needs OCR), encrypted, or empty.",
                "honest_signal": True}

    chunks = chunk_text(text)
    total_cost = 0.0
    partials = []

    # Initialize job row
    c = sqlite3.connect(DB_PATH)
    c.execute("""INSERT OR REPLACE INTO attachment_synthesis_jobs
        (job_id, attachment_hash, filename, content_type, size_bytes,
         role_hint, vertical, total_chunks, completed_chunks,
         status, extracted_text_preview, created_ts, updated_ts)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (job_id, att_hash, filename, content_type, size, role_hint, vertical,
         len(chunks), 0, "in_progress", text[:800],
         datetime.now(timezone.utc).isoformat(),
         datetime.now(timezone.utc).isoformat()))
    c.commit(); c.close()

    # Process each chunk
    for idx, ck in enumerate(chunks):
        result = synthesize_chunk(ck, idx, len(chunks), role_hint, vertical)
        if "error" in result and not result.get("synthesis"):
            # Save checkpoint + bail
            c = sqlite3.connect(DB_PATH)
            c.execute("""UPDATE attachment_synthesis_jobs
                SET completed_chunks=?, partial_synthesis=?, status='in_progress',
                    failure_reason=?, updated_ts=?
                WHERE job_id=?""",
                (idx, json.dumps(partials), result.get("error"),
                 datetime.now(timezone.utc).isoformat(), job_id))
            c.commit(); c.close()
            return {"job_id": job_id, "status": "in_progress",
                    "completed_chunks": idx, "total_chunks": len(chunks),
                    "resume_token": job_id,
                    "failure_reason": result.get("error")}
        partials.append(result.get("synthesis", ""))
        total_cost += result.get("cost_usd", 0)
        # Checkpoint after each chunk
        c = sqlite3.connect(DB_PATH)
        c.execute("""UPDATE attachment_synthesis_jobs
            SET completed_chunks=?, partial_synthesis=?, updated_ts=?
            WHERE job_id=?""",
            (idx + 1, json.dumps(partials),
             datetime.now(timezone.utc).isoformat(), job_id))
        c.commit(); c.close()

    # Final merge
    final = merge_syntheses(partials, role_hint, vertical)
    c = sqlite3.connect(DB_PATH)
    c.execute("""UPDATE attachment_synthesis_jobs
        SET status='done', final_synthesis=?, updated_ts=?
        WHERE job_id=?""",
        (final, datetime.now(timezone.utc).isoformat(), job_id))
    c.commit(); c.close()
    return {"job_id": job_id, "status": "done",
            "final_synthesis": final,
            "chunks_processed": len(chunks),
            "total_cost_usd": round(total_cost, 5)}


def get_job(job_id: str):
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    row = c.execute("SELECT * FROM attachment_synthesis_jobs WHERE job_id=?",
                    (job_id,)).fetchone()
    c.close()
    return dict(row) if row else None
