"""PCR-090f — Hallucination Antibody Loop.

5 stages:
  f.1 CAPTURE   — claim_extractor.py
  f.2 VERIFY    — verifiers/
  f.3 ANTIBODY  — immune_bridge.py
  f.4 SUNSET    — sunset_engine.py
  f.5 FACT ATLAS — fact_atlas.py

This stage 1 ships f.1 only: claim ledger schema + extractor scheduler.
"""
__version__ = "0.1.0-pcr090f.1"
