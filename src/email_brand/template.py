"""Murphy branded email — PORTAL edition.

Design intent: the email should NOT look like an email. It should look
like a portal opening into Murphy's operations room — dark, alive,
teal-glowing, with the eye watching. The reader's pale gray inbox
becomes the frame; Murphy is the bright, focused window inside it.

The "follow the finger mapping" is carried by:
  - A static eye in the header, iris+pupil pre-rendered looking DOWN
    at the answer block (gaze-direction pointer)
  - A small eye next to the follow-up question, looking RIGHT into it
  - Both eyes are the live gear-with-eye motif from the landing page,
    in dark surface with teal glow

Returns (html, plain) — multipart-ready.
"""
from __future__ import annotations
from typing import Optional, Tuple
import html as _html
import re as _re

# Locked palette — landing page values
_TEAL       = "#00D4AA"
_TEAL_GLOW  = "rgba(0,212,170,0.18)"
_GREEN      = "#00ff6a"
_BG         = "#080c0a"
_SURFACE    = "#111a15"
_ELEVATED   = "#162019"
_BORDER     = "rgba(0,212,170,0.13)"
_BORDER_HI  = "rgba(0,212,170,0.28)"
_TEXT       = "#deeae4"
_TEXT_DIM   = "#7a9a8a"

_FONT_STACK = ("Inter, -apple-system, BlinkMacSystemFont, "
               "'Segoe UI', Roboto, Helvetica, Arial, sans-serif")


def _eye_svg(gaze: str = "center", size: int = 44) -> str:
    """Render the gear-with-eye logo with the iris+pupil pre-offset.

    gaze ∈ {"center", "down", "right", "down-right", "up"}
    Pre-renders the saccade offset that the JS version computes live.
    """
    # Match murphy-gaze.js: iris max +/- 22 vbu x, +/- 12 vbu y
    # pupil moves 1.55x more
    offsets = {
        "center":     (0, 0),
        "down":       (0, 9),
        "down-right": (10, 7),
        "right":      (16, 0),
        "up":         (0, -7),
        "sleep":      (0, 0),  # eyelids drawn closed
    }
    ix, iy = offsets.get(gaze, (0, 0))
    px, py = ix * 1.55, iy * 1.55
    sleep = (gaze == "sleep")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
        f'width="{size}" height="{size}" '
        f'style="display:block;filter:drop-shadow(0 0 12px rgba(0,212,170,0.45));">'
        '<defs>'
        f'<clipPath id="ec_{gaze}"><ellipse cx="32" cy="32" rx="9" ry="5.5"/></clipPath>'
        '</defs>'
        # Gear body
        '<path d="M32,3 L38.8,11.08 L49.05,8.54 L49.8,19.07 L59.58,23.04 '
        'L54,32 L59.58,40.96 L49.8,44.93 L49.05,55.46 L38.8,52.92 L32,61 '
        'L25.2,52.92 L14.95,55.46 L14.2,44.93 L4.42,40.96 L10,32 '
        'L4.42,23.04 L14.2,19.07 L14.95,8.54 L25.2,11.08 Z '
        'M32,47 A15,15 0 1,1 32,17 A15,15 0 1,1 32,47 Z" '
        f'fill="{_TEAL}" fill-rule="evenodd"/>'
        f'<circle cx="32" cy="32" r="15" fill="none" stroke="{_TEAL}" stroke-width="1"/>'
        # Sclera (white of eye)
        '<ellipse cx="32" cy="32" rx="9" ry="5.5" fill="#E6ECF2"/>'
        # Upper lid shadow inside the eye
        f'<path d="M23,32 Q32,23.5 41,32" fill="#C8D0DC" clip-path="url(#ec_{gaze})"/>'
    ) + (
        # Iris + pupil offset to indicate gaze direction
        f'<g transform="translate({ix},{iy})">'
        f'<circle cx="32" cy="32" r="4" fill="{_TEAL}"/>'
        '</g>'
        f'<g transform="translate({px:.1f},{py:.1f})">'
        '<circle cx="32" cy="32" r="1.9" fill="#080E14"/>'
        f'<circle cx="{33.2+px:.1f}" cy="{30.8+py:.1f}" r="0.9" '
        'fill="rgba(255,255,255,0.55)"/>'
        '</g>'
    ) + (
        # Eye outline
        f'<ellipse cx="32" cy="32" rx="9" ry="5.5" fill="none" '
        f'stroke="{_TEAL}" stroke-width="0.9"/>'
        # Eyelids (closed if sleeping)
        + (f'<path d="M23,32 Q32,38 41,32 L41,28 Q32,32 23,28 Z" '
           f'fill="{_BG}" stroke="{_TEAL}" stroke-width="0.9"/>'
           if sleep else "")
        + '</svg>'
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
        out.append(
            f'<p style="margin:0 0 18px;line-height:1.7;color:{_TEXT};'
            'font-size:15px;">' + esc + '</p>'
        )
    return "\n".join(out)


def render_branded_email(
    answer: str,
    follow_up: Optional[str] = None,
    sponsor: Optional[dict] = None,
    subject: Optional[str] = None,
    role_label: Optional[str] = None,
) -> Tuple[str, str]:
    """Render answer as a portal-style branded email."""
    answer_html = _structure_answer_html(answer)
    eye_header = _eye_svg("down", size=52)         # looks DOWN at answer
    eye_follow = _eye_svg("right", size=24)        # looks RIGHT into question

    badge = ""
    if role_label:
        badge = (
            f'<span style="display:inline-block;background:{_TEAL_GLOW};'
            f'border:1px solid {_BORDER_HI};color:{_TEAL};font-size:10px;'
            'padding:4px 11px;border-radius:20px;font-weight:700;'
            'letter-spacing:.1em;text-transform:uppercase;">'
            f'{_esc(role_label)}</span>'
        )

    follow_block = ""
    if follow_up:
        follow_block = (
            '<table role="presentation" cellspacing="0" cellpadding="0" '
            'border="0" width="100%" style="margin:28px 0 8px;">'
            '<tr>'
            f'<td valign="top" style="width:42px;padding-top:4px;">'
            f'{eye_follow}</td>'
            f'<td style="background:{_ELEVATED};'
            f'border:1px solid {_BORDER};border-left:3px solid {_TEAL};'
            'border-radius:8px;padding:14px 18px;">'
            f'<div style="font-size:10px;color:{_TEAL};font-weight:700;'
            'letter-spacing:.12em;text-transform:uppercase;'
            'margin-bottom:6px;">One question</div>'
            f'<div style="color:{_TEXT};font-size:15px;line-height:1.55;">'
            f'{_esc(follow_up)}</div>'
            '</td></tr></table>'
        )

    sponsor_block = ""
    if sponsor and sponsor.get("url"):
        sponsor_block = (
            '<table role="presentation" cellspacing="0" cellpadding="0" '
            'border="0" width="100%" style="margin:28px 0 0;">'
            '<tr>'
            f'<td style="border:1px dashed {_BORDER};border-radius:8px;'
            'padding:14px 18px;">'
            f'<div style="font-size:9px;color:{_TEXT_DIM};font-weight:700;'
            'letter-spacing:.12em;text-transform:uppercase;'
            'margin-bottom:6px;">Sponsored</div>'
            f'<a href="{_esc(sponsor["url"])}" '
            f'style="color:{_TEAL};text-decoration:none;'
            'font-weight:700;font-size:15px;">'
            f'{_esc(sponsor.get("title","Featured tool"))}</a>'
            f'<div style="color:{_TEXT_DIM};font-size:12px;'
            f'line-height:1.5;margin-top:4px;">'
            f'{_esc(sponsor.get("blurb",""))}</div>'
            '</td></tr></table>'
        )

    # ─── THE PORTAL ─────────────────────────────────────────────────
    # Outer wrapper renders the GLOW that bleeds past the inner frame —
    # gives the "popping out of the inbox" feel. Inner table is the
    # dark Murphy world. The eye sits at the top, looking down INTO it.
    html_doc = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{_esc(subject or "Murphy")}</title></head>'
        '<body style="margin:0;padding:0;background:#f4f6f8;'
        f'font-family:{_FONT_STACK};">'
        # Outer wrapper — pale gray like Gmail itself, so the dark portal
        # frame pops as a discontinuity
        '<table role="presentation" cellspacing="0" cellpadding="0" '
        'border="0" width="100%" style="background:#f4f6f8;padding:32px 12px;">'
        '<tr><td align="center">'
        # The portal itself — radial teal glow bleeding out of its edges
        '<div style="max-width:660px;margin:0 auto;'
        # Pseudo-glow via box-shadow on the dark frame
        'border-radius:18px;'
        'box-shadow:0 0 0 1px rgba(0,212,170,0.35),'
        '0 20px 80px -10px rgba(0,212,170,0.45),'
        '0 0 120px -20px rgba(0,212,170,0.35),'
        '0 30px 60px -20px rgba(0,0,0,0.25);'
        f'background:{_BG};overflow:hidden;">'
        # Top edge — green pulse stripe like the live-dot pill
        f'<div style="height:3px;background:linear-gradient(90deg,'
        f'transparent 0%,{_TEAL} 50%,transparent 100%);"></div>'
        # ── HEADER with the eye looking down ──
        '<table role="presentation" cellspacing="0" cellpadding="0" '
        'border="0" width="100%">'
        '<tr><td align="center" style="padding:28px 24px 8px;'
        # Faint teal grid background to echo landing-page hero
        f'background:{_BG};'
        f'background-image:'
        f'linear-gradient(rgba(0,212,170,0.04) 1px,transparent 1px),'
        f'linear-gradient(90deg,rgba(0,212,170,0.04) 1px,transparent 1px);'
        'background-size:32px 32px;">'
        '<table role="presentation" cellspacing="0" cellpadding="0" '
        'border="0"><tr>'
        f'<td valign="middle" style="padding-right:14px;">{eye_header}</td>'
        '<td valign="middle">'
        f'<div style="color:{_TEAL};font-weight:800;font-size:22px;'
        'letter-spacing:-.02em;line-height:1;">Murphy</div>'
        f'<div style="color:{_TEXT_DIM};font-size:11px;'
        'margin-top:4px;letter-spacing:.06em;">'
        '<span style="display:inline-block;width:6px;height:6px;'
        f'background:{_GREEN};border-radius:50%;margin-right:5px;'
        'vertical-align:middle;"></span>AUTONOMOUS OPS &middot; LIVE'
        '</div>'
        '</td></tr></table>'
        + (f'<div style="margin-top:14px;">{badge}</div>' if badge else '')
        + '</td></tr>'
        # Separator
        f'<tr><td style="height:1px;background:{_BORDER};'
        'line-height:1px;font-size:0;">&nbsp;</td></tr>'
        # ── ANSWER BODY ──
        f'<tr><td style="padding:28px 32px 4px;background:{_SURFACE};">'
        + answer_html +
        '</td></tr>'
        # ── FOLLOW-UP ──
        f'<tr><td style="padding:0 32px;background:{_SURFACE};">'
        + follow_block +
        '</td></tr>'
        # ── SPONSOR ──
        f'<tr><td style="padding:0 32px 8px;background:{_SURFACE};">'
        + sponsor_block +
        '</td></tr>'
        # ── FOOTER ──
        f'<tr><td style="padding:18px 32px 22px;background:{_BG};'
        f'border-top:1px solid {_BORDER};font-size:11px;color:{_TEXT_DIM};'
        'line-height:1.6;">'
        '<table role="presentation" cellspacing="0" cellpadding="0" '
        'border="0" width="100%"><tr>'
        '<td style="vertical-align:middle;">'
        f'<a href="https://murphy.systems/" style="color:{_TEAL};'
        'text-decoration:none;font-weight:700;">murphy.systems</a>'
        f'<span style="color:{_TEXT_DIM};"> &middot; Inoni LLC</span>'
        '</td>'
        f'<td align="right" style="vertical-align:middle;color:{_TEXT_DIM};">'
        '<a href="mailto:murphy@murphy.systems?subject=STOP" '
        f'style="color:{_TEXT_DIM};text-decoration:underline;">'
        'reply STOP to opt out</a>'
        '</td></tr></table>'
        f'<div style="margin-top:10px;color:{_TEXT_DIM};font-size:10px;'
        'line-height:1.5;">'
        'Verify all data. Murphy is an autonomous AI system; '
        'replies may contain errors. Powered by independent agents '
        'running on dedicated infrastructure.'
        '</div>'
        '</td></tr></table>'
        # Bottom edge pulse
        f'<div style="height:3px;background:linear-gradient(90deg,'
        f'transparent 0%,{_TEAL} 50%,transparent 100%);"></div>'
        '</div>'
        # Outside-portal small line under the frame
        f'<div style="max-width:660px;margin:14px auto 0;text-align:center;'
        f'color:#9aa3ad;font-size:10px;letter-spacing:.08em;">'
        'A SIGNAL FROM MURPHY &middot; murphy.systems'
        '</div>'
        '</td></tr></table>'
        '</body></html>'
    )

    # Plain text fallback (unchanged from 31aa.6)
    plain_lines = ["MURPHY / autonomous ops"]
    if role_label:
        plain_lines.append(f"[{role_label}]")
    plain_lines.append("─" * 60)
    plain_lines.append("")
    plain_lines.append((answer or "").strip())
    plain_lines.append("")
    if follow_up:
        plain_lines.append("→ One question:")
        plain_lines.append(f"  {follow_up}")
        plain_lines.append("")
    if sponsor and sponsor.get("url"):
        plain_lines.append(f"Sponsored: {sponsor.get('title','')}")
        if sponsor.get("blurb"):
            plain_lines.append(f"  {sponsor['blurb']}")
        plain_lines.append(f"  {sponsor['url']}")
        plain_lines.append("")
    plain_lines.append("─" * 60)
    plain_lines.append("murphy.systems · Inoni LLC")
    plain_lines.append("automated reply · reply STOP to opt out")
    plain_lines.append(
        "Verify all data. Murphy is autonomous AI; replies may contain errors."
    )
    plain = "\n".join(plain_lines)
    return html_doc, plain
