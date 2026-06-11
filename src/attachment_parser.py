"""
Ship 31g — Attachment-Aware Perspective Analysis (2026-06-10)
==============================================================

Parses email attachments and extracts text + metadata so the
magnify-drill engine can analyze them from the forwarder's role
perspective.

KEY CAPABILITIES:
  parse_attachments(raw_message_bytes)
    → returns list of {filename, mime, size, text, kind, error}
  
  detect_forward(msg)
    → {is_forward, inner_from, inner_subject, inner_date, forwarder}
  
  extract_role_signals(msg, body, forwarder_addr)
    → {job_title, role_class, department, signature_block}
    Heuristics: signature parse, domain hint, common role keywords

SUPPORTED MIMES:
  application/pdf          → pdfplumber
  application/msword       → docx (best-effort)
  vnd.openxmlformats-...   → python-docx / openpyxl
  text/plain               → utf-8 decode
  text/csv                 → pandas read_csv summary
  message/rfc822           → recursive email parse (forwarded chain)
  image/*                  → metadata only (no OCR yet)

LIMITS (safety):
  - max 5 attachments per message
  - max 2 MB per attachment text extraction
  - max 8000 chars text extracted per attachment

LAST UPDATED: 2026-06-10
"""

import email
import io
import re
from email.message import Message
from email.utils import parseaddr
from typing import Dict, List, Optional, Tuple

MAX_ATTACHMENTS = 5
MAX_ATTACHMENT_BYTES = 2 * 1024 * 1024
MAX_TEXT_CHARS = 8000

# Role taxonomy — slug → list of trigger keywords found in title/signature
_ROLE_PATTERNS = {
    "founder":        [r"\b(founder|co[-\s]?founder|ceo|chief executive)\b"],
    "cfo":            [r"\b(cfo|chief financial officer|head of finance|vp finance)\b"],
    "coo":            [r"\b(coo|chief operating officer|head of ops)\b"],
    "cto":            [r"\b(cto|chief technology officer|head of engineering|vp engineering)\b"],
    "lawyer":         [r"\b(attorney|counsel|esq\.?|law firm|partner|associate at)\b"],
    "accountant":     [r"\b(accountant|cpa|bookkeeper|controller)\b"],
    "sales":          [r"\b(sales|account executive|ae|bd|business development|sdr|bdr)\b"],
    "marketing":      [r"\b(marketing|cmo|head of marketing|growth)\b"],
    "ops":            [r"\b(operations|ops manager|coo)\b"],
    "hr":             [r"\b(hr|people ops|talent|recruiter|chro)\b"],
    "engineer":       [r"\b(engineer|developer|programmer|swe|software)\b"],
    "product":        [r"\b(product manager|pm|product lead|cpo|head of product)\b"],
    "executive_assistant": [r"\b(executive assistant|ea|chief of staff|admin)\b"],
    "investor":       [r"\b(investor|venture|vc|partner|principal|associate at .* capital)\b"],
    "real_estate_agent": [r"\b(realtor|broker|real estate agent)\b"],
    "doctor":         [r"\b(md|dr\.?|physician|surgeon|nurse practitioner)\b"],
}

# Perspective lens — what each role cares about when analyzing a document
ROLE_LENSES = {
    "founder":     "risk, dilution, runway, strategic optionality, signing implications",
    "cfo":         "financial terms, payment schedule, indemnification caps, audit rights, revenue recognition",
    "coo":         "operational obligations, SLAs, milestones, dependency chains, exit clauses",
    "cto":         "technical scope, IP ownership, source escrow, security obligations, vendor lock-in",
    "lawyer":      "legal redlines, governing law, indemnity, limitations of liability, dispute resolution",
    "accountant":  "tax treatment, expense categorization, AR/AP impact, reporting obligations",
    "sales":       "commission terms, quota implications, customer concessions, pipeline impact",
    "marketing":   "brand obligations, marketing rights, co-branding, attribution",
    "ops":         "operational handoffs, SLA tracking, vendor management implications",
    "hr":          "employment terms, non-compete, severance, benefits, classification",
    "engineer":    "technical specs, API contracts, performance SLAs, security requirements",
    "product":     "feature scope, roadmap commitments, success metrics, customer obligations",
    "executive_assistant": "calendar implications, who needs to sign, deadlines, follow-ups",
    "investor":    "valuation, liquidation preferences, board rights, anti-dilution, pro-rata",
    "real_estate_agent": "commission structure, listing exclusivity, marketing rights, transaction timing",
    "doctor":      "clinical implications, compliance, malpractice exposure, patient impact",
    "unknown":     "general business implications, key obligations, financial exposure, risk factors",
}


# ----------------------------------------------------------------------
# Forward detection
# ----------------------------------------------------------------------

_FWD_PREFIXES = (
    "fwd:", "fw:", "fw :", "fwd :",
    "[fwd]", "[fw]",
    "tr:",  # French (Transféré)
    "wg:",  # German (Weitergeleitet)
)

_FORWARD_MARKERS = (
    "---------- forwarded message ---------",
    "----- forwarded message -----",
    "begin forwarded message",
    "-------- original message --------",
    "from:",  # weak — use only with other signals
)


def detect_forward(msg: Message) -> Dict:
    """Identify whether this message is a forward + extract inner sender."""
    subject = (msg.get("Subject", "") or "").lower().strip()
    is_subject_fwd = any(subject.startswith(p) for p in _FWD_PREFIXES)
    
    body_text = _get_text_body(msg).lower()
    has_marker = any(m in body_text for m in _FORWARD_MARKERS[:4])  # skip generic "from:"
    
    is_forward = is_subject_fwd or has_marker
    
    inner_from = ""
    inner_subject = ""
    inner_date = ""
    
    if is_forward:
        # Try to extract inner sender from the body
        raw_body = _get_text_body(msg)
        for line in raw_body.splitlines()[:30]:
            line_l = line.strip()
            if not line_l:
                continue
            lower = line_l.lower()
            if lower.startswith("from:"):
                _, inner_from = parseaddr(line_l[5:].strip())
            elif lower.startswith("subject:"):
                inner_subject = line_l[8:].strip()
            elif lower.startswith("date:") or lower.startswith("sent:"):
                inner_date = line_l[5:].strip()
    
    forwarder = parseaddr(str(msg.get("From", "")))[1]
    
    return {
        "is_forward": is_forward,
        "forwarder": forwarder,
        "inner_from": inner_from,
        "inner_subject": inner_subject,
        "inner_date": inner_date,
    }


# ----------------------------------------------------------------------
# Role signal extraction
# ----------------------------------------------------------------------

def _extract_signature(body: str) -> str:
    """Pull the last ~10 non-empty lines (likely signature block)."""
    lines = [ln.strip() for ln in (body or "").splitlines() if ln.strip()]
    if not lines:
        return ""
    # Find common signature delimiters
    for i in range(len(lines) - 1, max(0, len(lines) - 30), -1):
        if lines[i] in ("--", "—", "-", "best,", "thanks,", "regards,",
                        "best regards,", "kind regards,", "cheers,"):
            return "\n".join(lines[i:i+10])
    return "\n".join(lines[-10:])


def extract_role_signals(forwarder_addr: str, body: str,
                         email_signature: str = "") -> Dict:
    """Heuristic role detection from signature + email + body."""
    sig = email_signature or _extract_signature(body)
    haystack = (forwarder_addr + "\n" + body[:1000] + "\n" + sig).lower()
    
    # Try matching role patterns
    matches = {}
    for role_slug, patterns in _ROLE_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, haystack, re.IGNORECASE):
                matches[role_slug] = matches.get(role_slug, 0) + 1
                break  # one match per role is enough
    
    if matches:
        # Pick role with highest match count (ties → first in dict order)
        role_class = max(matches.items(), key=lambda x: x[1])[0]
        # Extract a job title string from the signature if possible
        job_title = ""
        for line in sig.splitlines():
            for pat in _ROLE_PATTERNS[role_class]:
                m = re.search(pat, line, re.IGNORECASE)
                if m:
                    job_title = line.strip()[:80]
                    break
            if job_title:
                break
        return {
            "role_class": role_class,
            "job_title": job_title or role_class.replace("_", " ").title(),
            "signature_block": sig[:500],
            "lens": ROLE_LENSES.get(role_class, ROLE_LENSES["unknown"]),
        }
    
    return {
        "role_class": "unknown",
        "job_title": "",
        "signature_block": sig[:500],
        "lens": ROLE_LENSES["unknown"],
    }


# ----------------------------------------------------------------------
# Attachment extraction
# ----------------------------------------------------------------------

def _get_text_body(msg: Message) -> str:
    """Return the text/plain body of a message, recursively."""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = (part.get("Content-Disposition") or "").lower()
            if ctype == "text/plain" and "attachment" not in disp:
                try:
                    return part.get_payload(decode=True).decode(
                        "utf-8", errors="ignore")[:50000]
                except Exception:
                    pass
    else:
        try:
            return msg.get_payload(decode=True).decode("utf-8", errors="ignore")[:50000]
        except Exception:
            return (msg.get_payload() or "")[:50000]
    return ""


def _extract_pdf(blob: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(blob)) as pdf:
            chunks = []
            for page in pdf.pages[:30]:  # cap 30 pages
                t = page.extract_text() or ""
                chunks.append(t)
                if sum(len(c) for c in chunks) > MAX_TEXT_CHARS:
                    break
            return "\n".join(chunks)[:MAX_TEXT_CHARS]
    except Exception as e:
        return f"[PDF parse failed: {e}]"


def _extract_docx(blob: bytes) -> str:
    try:
        import docx
        doc = docx.Document(io.BytesIO(blob))
        paragraphs = [p.text for p in doc.paragraphs if p.text]
        text = "\n".join(paragraphs)
        return text[:MAX_TEXT_CHARS]
    except Exception as e:
        return f"[DOCX parse failed: {e}]"


def _extract_xlsx(blob: bytes) -> str:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
        lines = []
        for ws in wb.worksheets[:5]:
            lines.append(f"=== Sheet: {ws.title} ===")
            for row in ws.iter_rows(max_row=200, values_only=True):
                row_str = " | ".join(str(c) if c is not None else "" for c in row)
                lines.append(row_str)
                if sum(len(l) for l in lines) > MAX_TEXT_CHARS:
                    break
            if sum(len(l) for l in lines) > MAX_TEXT_CHARS:
                break
        return "\n".join(lines)[:MAX_TEXT_CHARS]
    except Exception as e:
        return f"[XLSX parse failed: {e}]"


def _extract_text_plain(blob: bytes) -> str:
    try:
        return blob.decode("utf-8", errors="ignore")[:MAX_TEXT_CHARS]
    except Exception:
        return ""


def _extract_eml(blob: bytes) -> str:
    """Forwarded email-in-email (message/rfc822) — parse inner subject + body."""
    try:
        inner = email.message_from_bytes(blob)
        subj = inner.get("Subject", "")
        from_ = inner.get("From", "")
        body = _get_text_body(inner)
        return f"FROM: {from_}\nSUBJECT: {subj}\n\n{body[:MAX_TEXT_CHARS]}"
    except Exception as e:
        return f"[EML parse failed: {e}]"


def parse_attachments(msg: Message) -> List[Dict]:
    """Walk a parsed email message and extract every attachment as text."""
    out = []
    if not msg.is_multipart():
        return out
    
    for part in msg.walk():
        if len(out) >= MAX_ATTACHMENTS:
            break
        
        disp = (part.get("Content-Disposition") or "").lower()
        filename = part.get_filename() or ""
        ctype = part.get_content_type()
        
        # Skip if not an attachment
        is_attachment = "attachment" in disp or (filename and ctype != "text/plain")
        if not is_attachment:
            continue
        
        try:
            blob = part.get_payload(decode=True) or b""
        except Exception:
            continue
        
        size = len(blob)
        if size > MAX_ATTACHMENT_BYTES:
            out.append({
                "filename": filename, "mime": ctype, "size": size,
                "text": "", "kind": "skipped_oversize",
                "error": f"exceeds {MAX_ATTACHMENT_BYTES} bytes",
            })
            continue
        
        # Route to extractor
        text = ""
        kind = "unknown"
        error = None
        try:
            if ctype == "application/pdf" or filename.lower().endswith(".pdf"):
                text = _extract_pdf(blob); kind = "pdf"
            elif (ctype in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            "application/msword")
                  or filename.lower().endswith((".docx", ".doc"))):
                text = _extract_docx(blob); kind = "docx"
            elif (ctype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  or filename.lower().endswith((".xlsx", ".xls"))):
                text = _extract_xlsx(blob); kind = "xlsx"
            elif ctype == "message/rfc822" or filename.lower().endswith(".eml"):
                text = _extract_eml(blob); kind = "eml"
            elif ctype.startswith("text/") or filename.lower().endswith((".txt", ".md", ".csv")):
                text = _extract_text_plain(blob); kind = "text"
            elif ctype.startswith("image/"):
                text = ""; kind = "image_metadata_only"
            else:
                kind = "unsupported"
        except Exception as e:
            error = str(e)
        
        out.append({
            "filename": filename,
            "mime": ctype,
            "size": size,
            "text": (text or "")[:MAX_TEXT_CHARS],
            "kind": kind,
            "error": error,
        })
    
    return out


def summarize_attachments(attachments: List[Dict]) -> str:
    """Compact summary for prompt injection."""
    if not attachments:
        return ""
    lines = [f"=== {len(attachments)} ATTACHMENT(S) ==="]
    for a in attachments:
        lines.append(f"\n[{a['kind'].upper()}] {a['filename']} ({a['size']} bytes)")
        if a.get("error"):
            lines.append(f"  ERROR: {a['error']}")
        elif a.get("text"):
            lines.append("  CONTENT:")
            lines.append(a["text"][:3000])
    return "\n".join(lines)
