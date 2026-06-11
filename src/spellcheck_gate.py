"""
Ship 31ac — Spellcheck gate for outbound emails.

Runs aspell over body + subject before send. Auto-corrects obvious
typos via aspell's first suggestion when confidence is high.
Leaves jargon / proper nouns / technical terms alone via an allow-list.

Strategy:
  - Use aspell --list to get the bad words
  - Skip ALL-CAPS (acronyms), Mixed-Case proper nouns,
    numeric tokens, and anything in the allow-list
  - For each remaining suspect: take aspell's first suggestion
    IF the suspect and suggestion differ by 1-2 chars (Levenshtein
    distance) — very high-confidence corrections only
  - Never touch words >=14 chars (likely a deliberate compound)
"""
import subprocess, re, logging
log = logging.getLogger("spellcheck_gate")

# Domain-specific jargon, brand names, and technical terms we never flag
ALLOW = {
    # brand / product
    "murphy", "murphy.systems", "inoni", "nowpayments", "hitl",
    # legal codes
    "mrpc", "rpc", "icpc", "ada", "fmla", "fcra", "tcpa", "gdpr",
    "ccpa", "hipaa", "hitech", "sox", "ferpa", "coppa", "esi",
    # engineering / tech
    "mep", "ashrae", "ieee", "nec", "ibc", "iecc", "nfpa", "osha",
    "epa", "cfm", "btu", "kva", "kwh", "ipv4", "ipv6", "smtp", "imap",
    "dkim", "dmarc", "spf", "tls", "ssl", "saas", "paas", "iaas",
    "api", "cli", "ci", "cd", "ml", "ai", "llm", "nlp", "ux", "ui",
    "darcy", "weisbach", "reynolds", "stoke", "carnot", "ohm",
    # finance / business
    "gaap", "ifrs", "sec", "sox", "ebitda", "arr", "mrr", "cpm",
    "cac", "ltv", "kpi", "okr", "roi", "saas", "b2b", "b2c",
    # roles  
    "cto", "ceo", "cfo", "coo", "cio", "cmo", "vp", "svp", "evp",
    "fde", "pe", "ai", "ml", "ux", "ui", "qa", "qe", "ops",
    # codes / standards
    "iso", "ansi", "astm", "asme", "uns", "psi", "psig", "psia",
    # word forms aspell sometimes flags but are valid
    "automations", "automation's", "subreddit", "workflow",
    "workflows", "onboard", "onboarding", "offboarding",
    "stakeholders", "actionable", "leverage", "leveraging",
    # common AI / tech words
    "openai", "anthropic", "deepseek", "groq", "github",
    "gitlab", "stripe", "twilio", "sendgrid", "postmark",
    "cloudflare", "hetzner", "digitalocean", "aws", "gcp",
    "azure", "kubernetes", "docker", "nginx", "postfix",
    "postgres", "sqlite", "redis", "mongodb", "kafka",
    # email / web
    "url", "uri", "http", "https", "json", "csv", "xml",
    "html", "css", "js", "ts", "py", "yaml", "toml", "md",
    # Murphy ad / business
    "validators", "validator", "ad", "ads", "cta", "cpc",
    "ctr", "intent", "vertical", "verticals", "marketplace",
    "fireweed",
}

_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z']{2,}\b")

def _is_allowed(token: str) -> bool:
    t = token.lower().strip("'")
    if t in ALLOW:
        return True
    # ALL CAPS = acronym, skip
    if token.isupper() and len(token) <= 6:
        return True
    # contains digit = code/identifier
    if any(ch.isdigit() for ch in token):
        return True
    # Looks like a domain (has dot)
    if "." in token:
        return True
    # Mixed-case proper noun (e.g. "iPhone", "AcmeCorp")
    if token != token.lower() and token != token.upper():
        if not token[0].isupper():  # camelCase
            return True
        if token[0].isupper() and any(c.isupper() for c in token[1:]):
            return True
    # very long words = probably deliberate compound
    if len(token) >= 14:
        return True
    return False

def _levenshtein(a: str, b: str) -> int:
    """Tiny Levenshtein distance for confidence check."""
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(
                curr[j-1] + 1,
                prev[j] + 1,
                prev[j-1] + (0 if ca == cb else 1)
            ))
        prev = curr
    return prev[-1]

def _aspell_suggest(word: str) -> str | None:
    """Ask aspell for the top suggestion. Returns None if word is OK
    or if no high-confidence suggestion."""
    try:
        proc = subprocess.run(
            ["aspell", "-a", "--lang=en_US", "--sug-mode=fast"],
            input=word + "\n",
            capture_output=True, text=True, timeout=3,
        )
    except Exception as e:
        log.warning("aspell call failed: %s", e)
        return None
    # aspell -a output: first line is version banner, then per-word lines:
    #   "*" = correct
    #   "& word offset count: sug1, sug2, ..."
    for line in proc.stdout.splitlines():
        if line.startswith("&"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                sugs = [s.strip() for s in parts[1].split(",")]
                if sugs and sugs[0]:
                    return sugs[0]
        if line.startswith("*"):
            return None  # correct
    return None

def scan_and_fix(text: str, autocorrect: bool = True) -> tuple[str, list]:
    """Return (possibly-corrected text, list of corrections made)."""
    if not text:
        return text, []
    corrections = []
    tokens = list(_WORD_RE.finditer(text))
    if not tokens:
        return text, []
    
    # Run all suspects through aspell at once (faster than one-by-one)
    candidates = []
    for m in tokens:
        token = m.group(0)
        if _is_allowed(token):
            continue
        candidates.append((m.span(), token))
    
    if not candidates:
        return text, []
    
    # Build a word list aspell can chew on
    word_input = "\n".join(t for _, t in candidates) + "\n"
    try:
        proc = subprocess.run(
            ["aspell", "-a", "--lang=en_US", "--sug-mode=fast"],
            input=word_input,
            capture_output=True, text=True, timeout=10,
        )
    except Exception as e:
        log.warning("aspell batch call failed: %s", e)
        return text, []
    
    # Parse results, line-aligned with input
    lines = proc.stdout.splitlines()
    # Skip aspell banner (first line)
    result_lines = [l for l in lines if l.startswith(("*","&","#"))]
    
    # Build corrections map: original word -> first suggestion
    fixes = {}
    for (span, orig), result in zip(candidates, result_lines):
        if result.startswith("*"):
            continue  # already correct
        if result.startswith("&"):
            parts = result.split(":", 1)
            if len(parts) != 2:
                continue
            sugs = [s.strip() for s in parts[1].split(",")]
            if not sugs or not sugs[0]:
                continue
            top = sugs[0]
            # CONFIDENCE GATE — only auto-correct when distance is 1 or 2
            # AND the suggestion preserves first letter case
            d = _levenshtein(orig.lower(), top.lower())
            if d > 2:
                continue
            # case-preserve
            if orig[0].isupper() and top[0].islower():
                top = top[0].upper() + top[1:]
            fixes[orig] = top
            corrections.append({"from": orig, "to": top, "distance": d})
    
    if not fixes:
        return text, corrections
    
    if not autocorrect:
        return text, corrections
    
    # Apply replacements (whole-word, case-aware)
    out = text
    for orig, new in fixes.items():
        out = re.sub(r"\b" + re.escape(orig) + r"\b", new, out)
    return out, corrections
