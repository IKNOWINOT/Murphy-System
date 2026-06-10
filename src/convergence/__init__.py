"""PCR-090 Convergence Layer.

Aggregates 397 /api/* namespaces into 8 logical domains:
work / money / identity / ops / learning / system / founder / tenant.

Stage 1 (PCR-090a): read-only domain router + 8 rollup endpoints.
Stage 2 (PCR-090b): closure forecast engine (R(t)-conditioned).
Stage 3 (PCR-090c): drill-down endpoint + alt route enumeration.
Stage 4 (PCR-090d): unified /os UI rewrite.
"""
__version__ = "0.1.0-pcr090a"

DOMAINS = ("work", "money", "identity", "ops", "learning", "system", "founder", "tenant")
