#!/usr/bin/env python3
"""
PCR-040b hotfix — LLMRequest takes `prompt=`, not `query=`.

I guessed the field name in PCR-040b. Live test caught it instantly:
  LLMRequest.__init__() got an unexpected keyword argument 'query'

The real signature is:
  LLMRequest(prompt: str, context: Optional[str] = None,
             temperature: float = 0.7, max_tokens: int = ...)

Other code in the codebase calls it as `LLMRequest(prompt=..., context=..., max_tokens=...)`
— that's the pattern I should have matched.

Marker-based fix, surgical, revertable.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

APP = Path("/opt/Murphy-System/src/runtime/app.py")

OLD = '''                                    _req_040b = _LLMReq_040b(
                                        query=_brief_040b,
                                        context="",
                                        max_tokens=2000,
                                    ) if hasattr(_LLMReq_040b, "__init__") else _LLMReq_040b(query=_brief_040b)'''

NEW = '''                                    # PCR-040b hotfix: field is `prompt`, not `query`
                                    _req_040b = _LLMReq_040b(
                                        prompt=_brief_040b,
                                        context="",
                                        max_tokens=2000,
                                    )'''


def apply(verify: bool, revert: bool) -> int:
    print(f"PCR-040b LLMRequest hotfix  verify={verify}  revert={revert}")
    src = APP.read_text(encoding="utf-8")

    if revert:
        if "# PCR-040b hotfix" not in src:
            print("  · already absent"); return 0
        src = src.replace(NEW, OLD, 1)
        if verify: print("  ✓ would revert"); return 0
        APP.write_text(src, encoding="utf-8"); print("  ✓ reverted"); return 0

    if "# PCR-040b hotfix" in src:
        print("  · already present"); return 0
    if OLD not in src:
        print("  ✗ anchor not found"); return 1

    src = src.replace(OLD, NEW, 1)
    if verify: print("  ✓ would apply"); return 0
    APP.write_text(src, encoding="utf-8")
    print("  ✓ applied — LLMRequest now uses prompt= instead of query=")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    return apply(verify=args.verify, revert=args.revert)


if __name__ == "__main__":
    sys.exit(main())
