"""Murphy email brand kit — LOCKED 2026-06-11.

Canonical email rendering for ALL Murphy outbound email. Every outbound
path must import render_branded_email from this package. Plain-text
fallback is included in the returned tuple; senders should use both
parts in a multipart/alternative MIME.

The locked look is Victorian-techno:
  - Brass + ink double-bordered portal
  - Engraved gear-eye cartouche in clockwork laurel
  - Cinzel display serif + EB Garamond body serif
  - JetBrains Mono teal for numerals + units (techno against
    Victorian prose)
  - Teal #00D4AA + brass #c9a55a dual glow bleeds out of frame
  - "Bureau of Autonomous Operations" voice in headers
  - Period STOP rephrased as "beg leave to discontinue"

DO NOT add new email-rendering functions. Tune this one.
"""
from src.email_brand.victorian import render_victorian_email as render_branded_email
__all__ = ["render_branded_email"]
