"""Murphy Victorian-techno email — engraved teal circuitry on brushed steel.

Visual intent: an 1880s engineer's stamped report, only the engineer is
Murphy. Brass ornamental corners, monospace serif numerals, hairline
double-rules, an engraved cartouche around the eye logo. Teal circuit
traces interrupt the parchment-dark surface. Couture, not utility.

Returns (html, plain) — multipart ready.
"""
from __future__ import annotations
from typing import Optional, Tuple
import html as _html
import re as _re

# Murphy palette + Victorian-techno additions
_TEAL       = "#00D4AA"
_TEAL_DEEP  = "#007a64"
_TEAL_GLOW  = "rgba(0,212,170,0.22)"
_BRASS      = "#c9a55a"      # antique brass leaf accent
_BRASS_DIM  = "#8a7240"
_PARCHMENT  = "#0c1411"      # dark inked parchment (still Murphy bg)
_INKWELL    = "#070c0a"      # darker pool for cartouche
_SURFACE    = "#101a16"
_RULE       = "rgba(201,165,90,0.22)"  # brass hairline
_RULE_TEAL  = "rgba(0,212,170,0.32)"
_RULE_HEX      = "#8a7240"
_RULE_TEAL_HEX = "#00a380"
_TEXT       = "#e4ebe6"
_TEXT_DIM   = "#8a9b91"
_TEXT_INK   = "#cfd6d0"

_SERIF      = ("'EB Garamond', 'Hoefler Text', 'Baskerville', "
               "Georgia, 'Times New Roman', serif")
_MONO       = ("'JetBrains Mono', 'IBM Plex Mono', "
               "'Courier New', monospace")
_DISPLAY    = ("'Cinzel', 'Cormorant Garamond', "
               "'Trajan Pro', Georgia, serif")


def _eye_engraved(size: int = 64, gaze: str = "center",
                  bg_color: str = "#070c0a") -> str:
    """The Murphy eye — Gmail-safe rebuild.

    Renders the live landing-page logo geometry WITHOUT <defs>,
    <mask>, or <clipPath> (Gmail strips those). Uses only basic
    primitives so it renders identically in browser and Gmail.

    bg_color = the surface the eye sits on (used to fake the gear
    annulus inner cut-out).
    """
    offsets = {
        "center":     (0, 0),
        "down":       (0, 5),
        "down-right": (10, 4),
        "right":      (16, 0),
        "up":         (0, -5),
        "left":       (-16, 0),
    }
    ix, iy = offsets.get(gaze, (0, 0))
    px, py = ix * 1.55, iy * 1.55
    # Map to 240vbu coordinate system (landing eye native size)
    # Place inside 100vbu cartouche at scale 0.31
    scale = 0.31
    offset = (100 - 240 * scale) / 2  # ~13.8

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
        f'width="{size}" height="{size}" style="display:block;'
        'filter:drop-shadow(0 0 14px rgba(0,212,170,0.55));">'
        # ── Brass laurel ring + tick engravings ──
        f'<circle cx="50" cy="50" r="46" fill="none" stroke="{_BRASS}" stroke-width="0.6"/>'
        f'<circle cx="50" cy="50" r="43" fill="none" stroke="{_BRASS}" stroke-width="0.35" stroke-dasharray="1 2"/>'
        + "".join(
            f'<line x1="50" y1="6" x2="50" y2="10" stroke="{_BRASS}" '
            f'stroke-width="0.55" transform="rotate({a} 50 50)"/>'
            for a in range(0, 360, 30)
        ) +
        # ── Live eye, scaled into the ring ──
        f'<g transform="translate({offset:.2f} {offset:.2f}) scale({scale})">'
        # 10 rounded-rectangle gear teeth, fanned every 36°
        '<g fill="#00D4AA" transform="translate(120 120)">'
        + "".join(
            f'<rect x="-11" y="-118" width="22" height="24" rx="3" transform="rotate({a})"/>'
            for a in range(0, 360, 36)
        ) +
        '</g>'
        # Gear annulus — outer teal circle + inner bg-color circle
        # (this is the no-mask version of the live mask trick)
        '<circle cx="120" cy="120" r="98" fill="#00D4AA"/>'
        f'<circle cx="120" cy="120" r="78" fill="{bg_color}"/>'
        # Sclera (almond)
        '<path d="M 55 120 Q 120 75 185 120 Q 120 165 55 120 Z" fill="#d8ebe3"/>'
        # Iris (gaze offset)
        f'<g transform="translate({ix} {iy})">'
        '<circle cx="120" cy="120" r="26" fill="#00D4AA"/>'
        '<circle cx="120" cy="120" r="26" fill="none" stroke="#008f74" stroke-width="1.5"/>'
        '</g>'
        # Pupil (gaze offset, parallax)
        f'<g transform="translate({px:.1f} {py:.1f})">'
        '<circle cx="120" cy="120" r="11" fill="#0a1a14"/>'
        '<circle cx="114.5" cy="114.5" r="2.8" fill="#deeae4" opacity="0.75"/>'
        '</g>'
        # Eye outline drawn LAST so it sits on top
        '<path d="M 55 120 Q 120 75 185 120 Q 120 165 55 120 Z" '
        'fill="none" stroke="#00D4AA" stroke-width="2.5"/>'
        '</g>'
        '</svg>'
    )


def _ornament_top(width: int = 600) -> str:
    """A symmetric Victorian flourish — brass scrollwork + center cartouche."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 26" '
        f'width="100%" height="26" preserveAspectRatio="none" '
        'style="display:block;">'
        # Long hairline left
        f'<line x1="20" y1="13" x2="{width//2-60}" y2="13" '
        f'stroke="{_BRASS}" stroke-width="0.6"/>'
        # Inner shorter line below for double-rule
        f'<line x1="40" y1="17" x2="{width//2-72}" y2="17" '
        f'stroke="{_BRASS}" stroke-width="0.3"/>'
        # Left scroll curl
        f'<path d="M {width//2-60} 13 Q {width//2-50} 6 {width//2-40} 13 '
        f'Q {width//2-30} 20 {width//2-20} 13" fill="none" '
        f'stroke="{_BRASS}" stroke-width="0.7"/>'
        # Center diamond (jewel)
        f'<path d="M {width//2-8} 13 L {width//2} 5 L {width//2+8} 13 '
        f'L {width//2} 21 Z" fill="{_TEAL}" stroke="{_BRASS}" '
        'stroke-width="0.6"/>'
        # Right scroll curl
        f'<path d="M {width//2+20} 13 Q {width//2+30} 6 {width//2+40} 13 '
        f'Q {width//2+50} 20 {width//2+60} 13" fill="none" '
        f'stroke="{_BRASS}" stroke-width="0.7"/>'
        # Long hairline right
        f'<line x1="{width//2+60}" y1="13" x2="{width-20}" y2="13" '
        f'stroke="{_BRASS}" stroke-width="0.6"/>'
        f'<line x1="{width//2+72}" y1="17" x2="{width-40}" y2="17" '
        f'stroke="{_BRASS}" stroke-width="0.3"/>'
        '</svg>'
    )


def _esc(s: str) -> str:
    return _html.escape(s or "", quote=True)


def _structure_answer_html(raw: str) -> str:
    raw = (raw or "").strip()
    raw = raw.replace("— Murphy (automated reply; reply STOP to opt out)", "")
    raw = raw.replace("— — —", "").strip()
    raw = _re.split(r"\n\s*Sponsored:\s*", raw, maxsplit=1)[0].strip()
    paras = [p.strip() for p in _re.split(r"\n\s*\n", raw) if p.strip()]
    out = []
    for p in paras:
        esc = _esc(p)
        esc = _re.sub(
            r"(https?://[^\s<]+)",
            (f'<a href="\\1" style="color:{_TEAL};text-decoration:none;'
             'border-bottom:1px dotted ' + _TEAL + ';">\\1</a>'),
            esc,
        )
        esc = esc.replace("\n", "<br>")
        # Wrap any numeric+unit expressions in monospace for techno feel
        esc = _re.sub(
            r'(\b\d[\d\.,]*\s*(?:in w\.g\.|ft|fpm|CFM|lb/ft\^?\d?|psi|ohm|V|A)\b)',
            (f'<span style="font-family:{_MONO};color:{_TEAL};'
             'font-weight:600;">\\1</span>'),
            esc,
        )
        out.append(
            f'<table role="presentation" cellspacing="0" cellpadding="0" '
            f'border="0" width="100%" style="border-collapse:collapse;">'
            f'<tr><td style="padding:0 0 18px;line-height:1.7;color:{_TEXT_INK};'
            f'font-family:{_SERIF};font-size:16px;text-align:left;">'
            + esc + '</td></tr></table>'
        )
    return "\n".join(out)


def render_victorian_email(
    answer: str,
    follow_up: Optional[str] = None,
    sponsor: Optional[dict] = None,
    subject: Optional[str] = None,
    role_label: Optional[str] = None,
    seal_number: Optional[str] = None,
) -> Tuple[str, str]:
    """Victorian-techno branded email."""
    if not seal_number:
        import hashlib, time
        seal_number = hashlib.sha1(
            f"{subject}{time.time()}".encode()
        ).hexdigest()[:6].upper()

    answer_html = _structure_answer_html(answer)
    eye_html = _eye_engraved(size=78, gaze="center")
    ornament = _ornament_top(width=620)

    badge = ""
    if role_label:
        badge = (
            f'<span style="display:inline-block;'
            f'background:{_INKWELL};'
            f'border:1px solid {_BRASS_DIM};color:{_BRASS};font-size:10px;'
            'padding:5px 14px;border-radius:2px;font-weight:700;'
            f'font-family:{_DISPLAY};'
            'letter-spacing:.18em;text-transform:uppercase;">'
            f'{_esc(role_label)}</span>'
        )

    follow_block = ""
    if follow_up:
        follow_block = (
            '<table role="presentation" cellspacing="0" cellpadding="0" '
            'border="0" width="100%" style="margin:32px 0 8px;">'
            '<tr>'
            # Brass-flanked cartouche
            f'<td style="background:{_INKWELL};'
            f'border-top:1px solid {_RULE};'
            f'border-bottom:1px solid {_RULE};'
            'padding:18px 22px;position:relative;">'
            # Left/right brass diamond marks
            f'<div style="font-family:{_DISPLAY};font-size:10px;'
            f'color:{_BRASS};letter-spacing:.22em;text-transform:uppercase;'
            'margin-bottom:8px;">'
            f'<span style="color:{_TEAL};">&#10070;</span> '
            'Inquiry of the House '
            f'<span style="color:{_TEAL};">&#10070;</span>'
            '</div>'
            f'<div style="color:{_TEXT};font-family:{_SERIF};'
            'font-size:16px;line-height:1.6;font-style:italic;">'
            f'&ldquo;{_esc(follow_up)}&rdquo;'
            '</div>'
            '</td></tr></table>'
        )

    sponsor_block = ""
    if sponsor and sponsor.get("url"):
        sponsor_block = (
            '<table role="presentation" cellspacing="0" cellpadding="0" '
            'border="0" width="100%" style="margin:32px 0 0;">'
            '<tr>'
            f'<td style="border:1px dotted {_BRASS_DIM};'
            f'background:{_INKWELL};'
            'padding:16px 20px;">'
            f'<div style="font-family:{_DISPLAY};font-size:9px;'
            f'color:{_BRASS_DIM};font-weight:700;'
            'letter-spacing:.22em;text-transform:uppercase;'
            'margin-bottom:8px;">'
            'Patronage &middot; Sponsored Notice'
            '</div>'
            f'<a href="{_esc(sponsor["url"])}" '
            f'style="color:{_TEAL};text-decoration:none;'
            f'font-family:{_DISPLAY};letter-spacing:.04em;'
            'font-weight:700;font-size:16px;">'
            f'{_esc(sponsor.get("title","Featured Concern"))}'
            '</a>'
            f'<div style="color:{_TEXT_DIM};font-size:13px;'
            f'line-height:1.6;margin-top:4px;font-family:{_SERIF};'
            'font-style:italic;">'
            f'{_esc(sponsor.get("blurb",""))}'
            '</div>'
            '</td></tr></table>'
        )

    # The portal
    html_doc = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        ''
        'family=Cinzel:wght@500;700&family=EB+Garamond:ital,wght@0,400;0,600;1,400&'
        'family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">'
        f'<title>{_esc(subject or "Murphy")}</title></head>'
        '<body style="margin:0;padding:0;background:#e8eaec;'
        f'font-family:{_SERIF};">'
        '<table role="presentation" cellspacing="0" cellpadding="0" '
        'border="0" width="100%" style="background:#e8eaec;padding:36px 12px;">'
        '<tr><td align="center">'
        # The portal
        '<div style="max-width:660px;margin:0 auto;'
        'border-radius:6px;overflow:hidden;'
        # The "popping out" glow
        'box-shadow:'
        '0 0 0 1px ' + _BRASS_DIM + ','
        '0 0 0 4px #0c1411,'
        '0 0 0 5px ' + _BRASS_DIM + ','
        '0 24px 80px -16px rgba(0,212,170,0.5),'
        '0 0 120px -20px rgba(201,165,90,0.35),'
        '0 30px 60px -20px rgba(0,0,0,0.5);'
        f'background:{_PARCHMENT};">'

        # Top brass ornament strip
        f'<div style="background:{_INKWELL};padding:14px 24px 8px;">'
        + ornament +
        '</div>'

        # ── HEADER — engraved eye cartouche ──
        f'<table role="presentation" cellspacing="0" cellpadding="0" '
        f'border="0" width="100%" style="background:{_INKWELL};">'
        '<tr><td align="center" style="padding:8px 24px 26px;">'
        # Circuit-trace background (subtle)
        f'<div style="display:inline-block;padding:10px 0 6px;">{eye_html}</div>'
        f'<div style="font-family:{_DISPLAY};color:{_TEAL};'
        'font-size:30px;font-weight:700;'
        'letter-spacing:.12em;text-transform:uppercase;'
        'margin-top:14px;line-height:1;">Murphy</div>'
        f'<div style="font-family:{_SERIF};color:{_BRASS};'
        'font-style:italic;font-size:13px;margin-top:6px;'
        'letter-spacing:.04em;">'
        '&mdash; Bureau of Autonomous Operations &mdash;'
        '</div>'
        + (f'<div style="margin-top:14px;">{badge}</div>' if badge else '')
        + '</td></tr></table>'

        # Hairline brass rule — table rows w/ hex bgcolor (Gmail-safe)
        '<table role="presentation" cellspacing="0" cellpadding="0" '
        'border="0" width="100%">'
        f'<tr><td height="1" bgcolor="{_RULE_HEX}" '
        f'style="line-height:1px;font-size:0;background-color:{_RULE_HEX};height:1px;">&nbsp;</td></tr>'
        '<tr><td height="2" style="line-height:2px;font-size:0;height:2px;">&nbsp;</td></tr>'
        f'<tr><td height="1" bgcolor="{_RULE_TEAL_HEX}" '
        f'style="line-height:1px;font-size:0;background-color:{_RULE_TEAL_HEX};height:1px;">&nbsp;</td></tr>'
        '</table>'

        # ── Cartouche header for body ──
        f'<div style="background:{_PARCHMENT};padding:24px 36px 0;">'
        f'<div style="font-family:{_DISPLAY};font-size:11px;'
        f'color:{_BRASS};letter-spacing:.28em;text-transform:uppercase;'
        'text-align:center;margin-bottom:6px;">'
        f'Report No. {seal_number} &middot; In the matter of yr inquiry'
        '</div>'
        f'<div style="text-align:center;color:{_BRASS_DIM};'
        'font-size:18px;margin-bottom:18px;">&sect; &sect; &sect;</div>'
        '</div>'

        # ── ANSWER BODY ──
        f'<div style="background:{_PARCHMENT};padding:8px 36px 16px;">'
        + answer_html +
        '</div>'

        # ── FOLLOW-UP + SPONSOR (only when present, no empty divs) ──
        + (
            f'<div style="background:{_PARCHMENT};padding:0 36px 8px;">'
            + follow_block + '</div>'
            if follow_block else ''
        )
        + (
            f'<div style="background:{_PARCHMENT};padding:0 36px 12px;">'
            + sponsor_block + '</div>'
            if sponsor_block else ''
        )

        # Hairline brass rule above footer
        f'<div style="background:{_PARCHMENT};padding:16px 24px 0;">'
        + ornament +
        '</div>'

        # ── FOOTER ──
        f'<table role="presentation" cellspacing="0" cellpadding="0" '
        f'border="0" width="100%" style="background:{_INKWELL};">'
        f'<tr><td style="padding:18px 36px 24px;font-family:{_SERIF};'
        f'font-size:12px;color:{_TEXT_DIM};line-height:1.7;'
        'text-align:center;">'
        f'<div style="font-family:{_DISPLAY};color:{_TEAL};'
        'font-size:11px;letter-spacing:.24em;text-transform:uppercase;'
        'margin-bottom:8px;">'
        '<a href="https://murphy.systems/" '
        f'style="color:{_TEAL};text-decoration:none;">murphy.systems</a> '
        f'<span style="color:{_BRASS};">&middot;</span> Inoni LLC, Proprietors'
        '</div>'
        '<div style="font-style:italic;margin-top:4px;">'
        'An automated despatch. Verify all measurements before acting upon '
        'them. Murphy is an autonomous intelligence and may err.'
        '</div>'
        '<div style="margin-top:10px;">'
        '<a href="mailto:murphy@murphy.systems?subject=STOP" '
        f'style="color:{_BRASS_DIM};text-decoration:underline;font-size:11px;">'
        'beg leave to discontinue these despatches'
        '</a>'
        '</div>'
        '</td></tr></table>'

        '</div>'
        # External tag below the portal
        f'<div style="max-width:660px;margin:14px auto 0;text-align:center;'
        f'color:#7a8088;font-size:10px;letter-spacing:.18em;'
        f'font-family:{_DISPLAY};text-transform:uppercase;">'
        f'Despatch No. {seal_number}'
        '</div>'
        '</td></tr></table>'
        '</body></html>'
    )

    plain_lines = ["MURPHY — Bureau of Autonomous Operations"]
    if role_label:
        plain_lines.append(f"[{role_label}]")
    plain_lines.append(f"Despatch No. {seal_number}")
    plain_lines.append("═" * 60)
    plain_lines.append("")
    plain_lines.append((answer or "").strip())
    plain_lines.append("")
    if follow_up:
        plain_lines.append("◆ Inquiry of the House:")
        plain_lines.append(f'  "{follow_up}"')
        plain_lines.append("")
    if sponsor and sponsor.get("url"):
        plain_lines.append(f"Patronage — Sponsored Notice")
        plain_lines.append(f"  {sponsor.get('title','')}")
        if sponsor.get("blurb"):
            plain_lines.append(f"  {sponsor['blurb']}")
        plain_lines.append(f"  {sponsor['url']}")
        plain_lines.append("")
    plain_lines.append("─" * 60)
    plain_lines.append("murphy.systems · Inoni LLC, Proprietors")
    plain_lines.append("An automated despatch. Verify all measurements.")
    plain_lines.append("Reply STOP to beg leave to discontinue.")
    plain = "\n".join(plain_lines)
    return html_doc, plain
