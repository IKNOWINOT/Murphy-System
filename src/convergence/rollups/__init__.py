"""Per-domain rollup implementations.

Each rollup_<domain>() returns:
  {"summary": {...counts...}, "items": [...up to 50...], "raw_endpoints": [...]}

Failures must be caught at the router level; rollups should raise on
real error so the router can include the error in the partial response.
"""
