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


# Ship 31ay — Gatsby Tech palette (2026-06-13)
# Founder direction: technological Great Gatsby. Art deco geometry on a
# midnight stage, champagne gold accents, ivory body type, with a thin
# tech-grid sensibility (monospace IDs, hairline rules, sharp stepped
# chevrons rather than soft curves). 1925 stock ticker meets deco lobby.
BG_COLOR = "#0A0E1A"         # midnight stage — deep navy-black
CARD_BG = "#10162A"          # the card itself — slightly lifted midnight
CARD_BG_2 = "#0D1224"        # darker band for header / footer sections
TEXT_COLOR = "#F2E9D5"       # ivory body type (warm white, like satin)
MUTED_COLOR = "#A8997A"      # antiqued ivory for secondary type
BRAND_COLOR = "#D4AF37"      # champagne gold — primary accent
ACCENT_COLOR = "#8C7A3D"     # antiqued gold for rule lines
LIGHT_RULE = "#3A3220"       # faint gold-on-midnight rule
HIGHLIGHT = "#E8C76A"        # bright gold for the monogram glow
MONO_FONT = "'Courier New', 'Roboto Mono', Consolas, monospace"
# Legacy Victorian palette retired (31ax) — kept for reference:
#   was BG=#E8DEC6 CARD=#F7F0DC TEXT=#1A1410 BRAND=#7A1F23 ACCENT=#B89B5E

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
        f'<tr><td style="background:{CARD_BG_2};border-top:1px solid {BRAND_COLOR};border-bottom:1px solid {BRAND_COLOR};padding:18px 20px;font-family:Georgia,serif">'
        f'<div style="color:{HIGHLIGHT};font-family:Georgia,serif;font-size:9px;text-transform:uppercase;letter-spacing:0.32em;margin-bottom:8px;text-align:center">— Patronage —</div>'
        f'<div style="color:{TEXT_COLOR};font-size:15px;font-weight:400;margin-bottom:8px;text-align:center;font-family:Georgia,serif">'
        f'{_html_escape(headline.replace("Sponsored:", "").strip())}</div>'
        f'<div style="color:{MUTED_COLOR};font-size:12px;line-height:1.6;margin-bottom:14px;text-align:center;font-style:italic">'
        f'{_html_escape(description)}</div>'
        f'<div style="text-align:center">'
        f'<a href="{_html_escape(cta_url)}" style="display:inline-block;border:1px solid {HIGHLIGHT};color:{HIGHLIGHT};padding:8px 22px;text-decoration:none;font-size:10px;letter-spacing:0.32em;text-transform:uppercase;font-family:Georgia,serif">Read more</a>'
        f'</div></td></tr></table>'
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
    """Render the plain reply body in a Gatsby Tech envelope.

    Ship 31ay — 2026-06-13 — founder asked for technological Great Gatsby.

    Midnight stage with a slightly lifted card, champagne gold accents,
    ivory serif body, art-deco sunburst monogram, stepped chevron
    dividers, and monospace runs for IDs and timestamps. The reply
    itself remains the same plain text — only the envelope changes.
    """
    sections = _split_body_into_sections(plain_body)
    reply_html = _format_reply_html(sections["reply"])
    ad_html = _format_ad_html(sections["ad_block"])
    compliance_html = _format_compliance_html(sections["compliance"])
    footer_html = _murphy_license_footer(license_id)

    # Stepped chevron divider — three nested triangles in gold
    chevron = (
        f'''<div style="text-align:center;padding:8px 0;line-height:1">'''
        f'''<span style="display:inline-block;width:0;height:0;'''
        f'''border-left:6px solid transparent;border-right:6px solid transparent;'''
        f'''border-top:6px solid {BRAND_COLOR};margin:0 2px"></span>'''
        f'''<span style="display:inline-block;width:0;height:0;'''
        f'''border-left:9px solid transparent;border-right:9px solid transparent;'''
        f'''border-top:9px solid {ACCENT_COLOR};margin:0 2px"></span>'''
        f'''<span style="display:inline-block;width:0;height:0;'''
        f'''border-left:6px solid transparent;border-right:6px solid transparent;'''
        f'''border-top:6px solid {BRAND_COLOR};margin:0 2px"></span>'''
        f'''</div>'''
    )

    # Art-deco sunburst monogram — radiating rays + M in center
    sunburst_svg = (
        f'''<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56" '''
        f'''viewBox="0 0 100 100" aria-label="Murphy">'''
        f'''<defs><radialGradient id="ggold" cx="50%" cy="50%" r="50%">'''
        f'''<stop offset="0%" stop-color="{HIGHLIGHT}"/>'''
        f'''<stop offset="100%" stop-color="{BRAND_COLOR}"/>'''
        f'''</radialGradient></defs>'''
        # 12 rays radiating from center
        + "".join(
            f'''<polygon points="50,50 {50+2*((-1)**(d//30))},10 {50-2*((-1)**(d//30))},10" '''
            f'''fill="{BRAND_COLOR}" transform="rotate({d} 50 50)" opacity="0.9"/>'''
            for d in (0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330)
        )
        # inner deco ring
        + f'''<circle cx="50" cy="50" r="22" fill="{CARD_BG}" '''
          f'''stroke="{HIGHLIGHT}" stroke-width="1.2"/>'''
        + f'''<circle cx="50" cy="50" r="18" fill="none" '''
          f'''stroke="{ACCENT_COLOR}" stroke-width="0.6"/>'''
        # M centered, gold
        + f'''<text x="50" y="58" text-anchor="middle" '''
          f'''font-family="Georgia, serif" font-size="20" font-weight="700" '''
          f'''fill="{HIGHLIGHT}">M</text>'''
        + '''</svg>'''
    )

    # Thin grid texture for the header band — pure CSS, no image
    grid_band = (
        f'''background-image:linear-gradient(90deg,{LIGHT_RULE} 1px,transparent 1px),'''
        f'''linear-gradient(0deg,{LIGHT_RULE} 1px,transparent 1px);'''
        f'''background-size:20px 20px;background-position:center;'''
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Murphy</title>
<style>
  @media (prefers-color-scheme: light) {{
    body, table, td {{ background:{BG_COLOR} !important; color:{TEXT_COLOR} !important; }}
  }}
</style>
</head>
<body style="margin:0;padding:0;background:{BG_COLOR};
             font-family:Georgia, 'Cormorant Garamond', 'Times New Roman', serif;
             color:{TEXT_COLOR};-webkit-font-smoothing:antialiased">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:{BG_COLOR}">
<tr><td align="center" style="padding:40px 16px">

<!-- Top art-deco header strip with grid texture -->
<table cellpadding="0" cellspacing="0" border="0" width="100%"
       style="max-width:580px;background:{CARD_BG_2};{grid_band}
              border-top:2px solid {BRAND_COLOR};
              border-left:1px solid {ACCENT_COLOR};
              border-right:1px solid {ACCENT_COLOR}">
<tr><td style="padding:28px 36px;text-align:center">
<div style="margin-bottom:8px">{sunburst_svg}</div>
<div style="color:{HIGHLIGHT};font-family:Georgia,serif;font-size:24px;
            font-weight:400;letter-spacing:0.32em;margin-bottom:4px">
M·U·R·P·H·Y
</div>
<div style="color:{MUTED_COLOR};font-family:Georgia,serif;font-style:italic;
            font-size:11px;letter-spacing:0.08em">
— established in the age of the machine —
</div>
{chevron}
</td></tr></table>

<!-- Main card body -->
<table cellpadding="0" cellspacing="0" border="0" width="100%"
       style="max-width:580px;background:{CARD_BG};
              border-left:1px solid {ACCENT_COLOR};
              border-right:1px solid {ACCENT_COLOR}">
<tr><td style="padding:24px 36px 8px 36px">

<!-- Telegram-style transmission line: monospace meta -->
<div style="font-family:{MONO_FONT};font-size:10px;color:{MUTED_COLOR};
            letter-spacing:0.1em;padding:6px 0 14px 0;
            border-bottom:1px solid {LIGHT_RULE};margin-bottom:18px">
TRANSMISSION · MURPHY.SYSTEMS · INONI LLC · AUSTIN TX
</div>

<!-- AI candour note -->
<div style="color:{MUTED_COLOR};font-family:Georgia,serif;font-size:11px;
            font-style:italic;line-height:1.6;letter-spacing:0.01em;
            margin-bottom:18px">
A note of candour — Murphy is an artificial assistant. Verify particulars before acting upon them. Reply <span style="color:{HIGHLIGHT};font-style:normal;letter-spacing:0.1em">STOP</span> to opt out.
</div>

<!-- Reply body -->
<div style="color:{TEXT_COLOR};font-family:Georgia,serif;
            font-size:15px;line-height:1.7">
{reply_html}
</div>

{ad_html}

<!-- Chevron divider before footer -->
<div style="padding:16px 0 4px 0">{chevron}</div>

<!-- Compliance block -->
<div style="color:{MUTED_COLOR};font-family:Georgia,serif;font-size:10px;
            line-height:1.7;letter-spacing:0.04em;padding:8px 0 0 0">
{compliance_html}
</div>

<!-- Murphy license footer -->
<div style="padding-top:18px">
{footer_html}
</div>

</td></tr></table>

<!-- Bottom art-deco footer band -->
<table cellpadding="0" cellspacing="0" border="0" width="100%"
       style="max-width:580px;background:{CARD_BG_2};{grid_band}
              border-bottom:2px solid {BRAND_COLOR};
              border-left:1px solid {ACCENT_COLOR};
              border-right:1px solid {ACCENT_COLOR}">
<tr><td style="padding:18px 36px;text-align:center">
<div style="color:{HIGHLIGHT};font-family:Georgia,serif;font-size:11px;
            letter-spacing:0.32em">
· · · END OF TRANSMISSION · · ·
</div>
<div style="color:{MUTED_COLOR};font-family:{MONO_FONT};font-size:9px;
            letter-spacing:0.1em;margin-top:8px">
INONI LLC · AUSTIN · TEXAS · MMXXVI
</div>
</td></tr></table>

</td></tr></table>
</body></html>"""

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
