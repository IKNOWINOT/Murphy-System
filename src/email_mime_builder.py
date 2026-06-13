"""
Ship 31t — Multipart MIME builder for Murphy outbound.

Builds a single message with BOTH:
  - text/plain (the existing reply, untouched — for plain-text clients)
  - text/html  (branded card with logo, disclaimer, reply, ad slot, footer)

The HTML version is rendered from the SAME source body — we never
diverge content between plain and html. Email clients pick the best
part they can render.

Hard rules:
  - HTML must be self-contained (inline CSS, no external links to CSS)
  - Logo embedded as CID inline image OR pure CSS/HTML (no external img)
  - Plain version is always included (deliverability + accessibility)
  - All ad slots render in HTML; plain version keeps "Sponsored: ..." text
  - Disclaimer ALWAYS at top in both versions
"""
import re
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication
from email import encoders
from email.utils import formatdate, make_msgid


BRAND_COLOR = "#58a6ff"   # Murphy blue (matches /os/ dashboards)
BG_COLOR = "#0d1117"      # github-dark
TEXT_COLOR = "#c9d1d9"
MUTED_COLOR = "#8b949e"
ACCENT_COLOR = "#56d364"  # green

# ── Ship 31ar.FOOTER — Murphy brand mark + license footer ────────────
# Inoni LLC owns the FOOTER space on every Murphy-generated artifact
# (founder direction 2026-06-12). Header stays open for customer
# branding. Footer is immutable per ToS.
MURPHY_TEAL = "#00D4AA"   # matches static/logo-live.svg

# Eye-gear logo — compact inline SVG (no external assets, email-safe).
# Renders the gear annulus + eye almond at 28x28 for email header use.
def _eye_gear_svg(size_px: int = 28) -> str:
    return (
        f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size_px}" '''
        f'''height="{size_px}" viewBox="0 0 240 240" aria-label="Murphy">'''
        f'''<defs><mask id="mg{size_px}"><rect width="240" height="240" fill="#000"/>'''
        f'''<circle cx="120" cy="120" r="98" fill="#fff"/>'''
        f'''<circle cx="120" cy="120" r="78" fill="#000"/></mask></defs>'''
        f'''<g fill="{MURPHY_TEAL}" transform="translate(120 120)">'''
        + "".join(
            f'''<rect x="-11" y="-118" width="22" height="24" rx="3" '''
            f'''transform="rotate({deg})"/>'''
            for deg in (0, 36, 72, 108, 144, 180, 216, 252, 288, 324)
        )
        + f'''</g><rect width="240" height="240" fill="{MURPHY_TEAL}" '''
          f'''mask="url(#mg{size_px})"/>'''
          f'''<path d="M 55 120 Q 120 75 185 120 Q 120 165 55 120 Z" '''
          f'''fill="{MURPHY_TEAL}"/>'''
          f'''<circle cx="120" cy="120" r="22" fill="#0d1117"/>'''
          f'''<circle cx="120" cy="120" r="12" fill="{MURPHY_TEAL}"/></svg>'''
    )


def _murphy_license_footer(license_id: str = "") -> str:
    """Immutable Murphy footer with eye-gear + license-ID + verify link.

    This footer goes on EVERY outbound email. The eye-gear logo, the
    license ID, and the verify URL together prove provenance.
    Per ToS, removing/altering this footer is a license breach.
    """
    if not license_id:
        license_id = "mLIC-unmarked"
    verify_url = f"https://murphy.systems/verify/{license_id}"
    return f'''
<hr style="border:0;border-top:1px solid #30363d;margin:24px 0 16px 0">
<table cellpadding="0" cellspacing="0" border="0" width="100%">
<tr>
<td style="vertical-align:middle;padding-right:12px;width:36px">
{_eye_gear_svg(28)}
</td>
<td style="vertical-align:middle;color:{MUTED_COLOR};font-size:11px;line-height:1.5">
<strong style="color:{MURPHY_TEAL}">Murphy</strong> by Inoni LLC ·
Generated content licensed while subscribed ·
<a href="{verify_url}" style="color:{MURPHY_TEAL};text-decoration:none">
verify {license_id}
</a>
</td>
</tr>
</table>'''.strip()


HALLUCINATION_DISCLAIMER = (
    "Murphy is an AI assistant. Verify all specifics before acting — "
    "LLMs can hallucinate. Reply STOP to opt out."
)


def _split_body_into_sections(body: str) -> dict:
    """Parse the existing plain body into structured sections.

    Looks for ad block markers (— — —) and compliance footer (---).
    Returns dict with: reply, ad_block, compliance.
    """
    sections = {"reply": "", "ad_block": "", "compliance": ""}

    # Compliance footer (always last, starts with ---)
    parts = re.split(r"\n+---\n", body, maxsplit=1)
    if len(parts) == 2:
        sections["compliance"] = parts[1].strip()
        rest = parts[0]
    else:
        rest = body

    # Ad block (sandwiched between "— — —" markers)
    ad_match = re.search(r"— — —\s*\n(.*?)\n\s*— — —", rest, re.DOTALL)
    if ad_match:
        sections["ad_block"] = ad_match.group(1).strip()
        sections["reply"] = rest[:ad_match.start()].strip()
    else:
        sections["reply"] = rest.strip()

    return sections


def _html_escape(text: str) -> str:
    """Escape HTML special chars."""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))


def _format_reply_html(reply_text: str) -> str:
    """Convert plain reply paragraphs into HTML <p> with proper spacing."""
    # Strip the leading disclaimer line if present (we render it explicitly)
    lines = reply_text.split("\n")
    paragraphs = []
    current = []
    for line in lines:
        if line.strip():
            current.append(line)
        else:
            if current:
                paragraphs.append(" ".join(current))
                current = []
    if current:
        paragraphs.append(" ".join(current))

    html_parts = []
    for p in paragraphs:
        # Detect "— Murphy (automated reply...)" signature line
        if p.strip().startswith("—"):
            html_parts.append(
                f'<p style="margin:16px 0 0 0;color:{MUTED_COLOR};font-size:13px;font-style:italic">'
                f'{_html_escape(p)}</p>'
            )
        else:
            html_parts.append(
                f'<p style="margin:0 0 14px 0;line-height:1.5">{_html_escape(p)}</p>'
            )
    return "".join(html_parts)


def _format_ad_html(ad_block: str) -> str:
    """Render an ad block as a branded card."""
    if not ad_block:
        return ""
    lines = [l.strip() for l in ad_block.split("\n") if l.strip()]
    if not lines:
        return ""
    # First line typically "Sponsored: <headline>"
    headline = lines[0] if lines else ""
    description = " ".join(lines[1:-1]) if len(lines) > 2 else ""
    link = lines[-1] if len(lines) > 1 else ""

    # Extract URL if last line is a URL
    url_match = re.search(r"https?://\S+", link)
    cta_url = url_match.group(0) if url_match else "#"

    return (
        f'<table cellpadding="0" cellspacing="0" border="0" width="100%" '
        f'style="margin:24px 0;border-collapse:collapse">'
        f'<tr><td style="background:#161b22;border:1px solid #30363d;'
        f'border-radius:6px;padding:16px">'
        f'<div style="color:{MUTED_COLOR};font-size:11px;text-transform:uppercase;'
        f'letter-spacing:0.05em;margin-bottom:6px">Sponsored</div>'
        f'<div style="color:{TEXT_COLOR};font-size:15px;font-weight:600;margin-bottom:8px">'
        f'{_html_escape(headline.replace("Sponsored:", "").strip())}</div>'
        f'<div style="color:{TEXT_COLOR};font-size:13px;line-height:1.4;margin-bottom:12px">'
        f'{_html_escape(description)}</div>'
        f'<a href="{_html_escape(cta_url)}" style="display:inline-block;background:{BRAND_COLOR};'
        f'color:#0d1117;padding:8px 16px;border-radius:4px;text-decoration:none;'
        f'font-size:13px;font-weight:600">Learn more →</a>'
        f'</td></tr></table>'
    )


def _format_compliance_html(compliance: str) -> str:
    """Render the compliance footer."""
    if not compliance:
        return ""
    safe = _html_escape(compliance).replace("\n", "<br>")
    return (
        f'<hr style="border:0;border-top:1px solid #30363d;margin:24px 0">'
        f'<div style="color:{MUTED_COLOR};font-size:11px;line-height:1.5">{safe}</div>'
    )


def render_html_body(plain_body: str, license_id: str = "") -> str:
    """Render the full HTML version of a Murphy reply.

    Takes the existing plain body, parses sections, returns full HTML doc.
    """
    sections = _split_body_into_sections(plain_body)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Murphy</title>
</head>
<body style="margin:0;padding:0;background:{BG_COLOR};
             font:14px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             color:{TEXT_COLOR}">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:{BG_COLOR}">
<tr><td align="center" style="padding:24px 16px">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:640px">

<!-- Header / Brand -->
<tr><td style="padding-bottom:16px;border-bottom:1px solid #30363d">
<table cellpadding="0" cellspacing="0" border="0"><tr>
<td style="vertical-align:middle">
<div style="width:32px;height:32px;background:{BRAND_COLOR};
            border-radius:6px;display:inline-block;
            text-align:center;line-height:32px;
            font-weight:700;color:#0d1117;font-size:18px">M</div>
</td>
<td style="vertical-align:middle;padding-left:12px">
<div style="color:{TEXT_COLOR};font-size:16px;font-weight:600">Murphy</div>
<div style="color:{MUTED_COLOR};font-size:11px">automation that actually does things</div>
</td>
</tr></table></td></tr>

<!-- Hallucination disclaimer (always top, always visible) -->
<tr><td style="padding:16px 0">
<div style="background:#3d2914;border:1px solid #d29922;border-radius:4px;
            padding:10px 12px;color:#d29922;font-size:12px;line-height:1.4">
⚠ {_html_escape(HALLUCINATION_DISCLAIMER)}
</div></td></tr>

<!-- Reply body -->
<tr><td style="padding:8px 0 16px 0;color:{TEXT_COLOR};font-size:14px">
{_format_reply_html(sections["reply"])}
</td></tr>

<!-- Ad slot -->
<tr><td>{_format_ad_html(sections["ad_block"])}</td></tr>

<!-- Compliance footer -->
<tr><td>{_format_compliance_html(sections["compliance"])}</td></tr>

<!-- 31ar Murphy license footer (immutable per ToS) -->
<tr><td>{_murphy_license_footer(license_id)}</td></tr>

</table></td></tr></table>
</body></html>"""
    return html


def build_multipart_message(
    to_addr: str, subject: str, plain_body: str,
    from_addr: str = "murphy@murphy.systems",
    reply_to: str = "murphy@murphy.systems",
    attachments: list = None,
) -> str:
    """Build a multipart/alternative message with plain + html parts.

    Returns the full message as a string ready for sendmail stdin.
    The plain body gets the disclaimer prepended (if not already present).
    """
    # Ensure plain body has disclaimer at top
    if HALLUCINATION_DISCLAIMER[:30] not in plain_body[:200]:
        plain_with_disc = (
            "⚠ " + HALLUCINATION_DISCLAIMER + "\n\n" + plain_body
        )
    else:
        plain_with_disc = plain_body

    # Ship 31ar.FOOTER — mint a license_id for this outbound and embed it
    try:
        from src.license_registry_31ar import mint as _mint_lic
        _lic_id = _mint_lic(
            artifact_kind="email_outbound",
            recipient=to_addr,
            content=plain_body,
        )
    except Exception:
        _lic_id = ""
    html_body = render_html_body(plain_body, license_id=_lic_id)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Reply-To"] = reply_to
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain="murphy.systems")
    msg["X-Murphy-Version"] = "31t-multipart"

    msg.attach(MIMEText(plain_with_disc, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Ship 31ag: attachments support. Wrap alt-part in mixed when files present.
    if attachments:
        outer = MIMEMultipart("mixed")
        for hk in ("Subject","From","To","Reply-To","Date","Message-ID","X-Murphy-Version"):
            v = msg[hk]
            if v is not None:
                outer[hk] = v
                del msg[hk]
        outer.attach(msg)  # alternative part with plain+html
        for att in attachments:
            fname = att.get("filename") or "attachment.bin"
            blob = att.get("blob") or b""
            mime = att.get("mime") or "application/octet-stream"
            if isinstance(blob, str):
                blob = blob.encode("utf-8")
            if "/" in mime:
                maintype, subtype = mime.split("/", 1)
            else:
                maintype, subtype = "application", "octet-stream"
            if maintype == "application":
                part = MIMEApplication(blob, _subtype=subtype, name=fname)
            else:
                part = MIMEBase(maintype, subtype)
                part.set_payload(blob)
                encoders.encode_base64(part)
                part.add_header("Content-Type", mime, name=fname)
            part.add_header("Content-Disposition", "attachment", filename=fname)
            outer.attach(part)
        return outer.as_string()

    return msg.as_string()
