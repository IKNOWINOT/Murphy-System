"""DLF-Lite v2 — portable durable memory per Shogun white paper (2026-06-16).

Thin v2 layer on top of existing src.dlf_r (which gives us pack/unpack/store).
This package adds:
  audit    — 3-state provenance classification (AVAILABLE/SELECTED/CONFIRMED)
  hygiene  — REJECT_FUTURE_SELECTION enforcement
"""
from src.dlf_lite_v2.audit import classify, AUDIT_STATES
from src.dlf_lite_v2.hygiene import is_usable_substrate, mark_rejected
__all__ = ["classify", "AUDIT_STATES", "is_usable_substrate", "mark_rejected"]
