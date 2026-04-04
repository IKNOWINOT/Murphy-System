"""
Gap-closure tests — Round 26.

Categories addressed:
56. BROKEN_DOC_LINKS — 30 broken internal markdown links across 14 files
    - Created SECURITY_IMPLEMENTATION_PLAN.md (referenced 5× in README, 1× in SECURITY.md)
    - Created 19 documentation stubs for missing referenced pages
    - Fixed screenshots README link to point to GETTING_STARTED.md

Quality gate:
- Every ``[text](relative/path)`` link in every ``.md`` file must resolve to an
  existing file on disk (after URL-decoding and stripping anchors/angle brackets).
"""

import os
import re
import urllib.parse

import pytest

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
MURPHY_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def _collect_broken_links():
    """Walk all .md files and return broken internal links."""
    broken = []
    for dirpath, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', 'archive', 'node_modules')]
        for f in files:
            if not f.endswith('.md'):
                continue
            fpath = os.path.join(dirpath, f)
            with open(fpath, encoding='utf-8') as fh:
                content = fh.read()
            for m in re.finditer(r'\[([^\]]*)\]\(([^)]+)\)', content):
                text, target = m.group(1), m.group(2)
                if target.startswith(('http://', 'https://', '#', 'mailto:')):
                    continue
                clean = target.strip('<>').split('#')[0]
                if not clean:
                    continue
                decoded = urllib.parse.unquote(clean)
                resolved = os.path.normpath(os.path.join(dirpath, decoded))
                if not os.path.exists(resolved):
                    src_rel = os.path.relpath(fpath, REPO_ROOT)
                    broken.append(f"{src_rel}: [{text}]({target})")
    return broken


class TestBrokenDocLinks:
    """Every internal markdown link must resolve to an existing file."""

    def test_zero_broken_internal_links(self):
        broken = _collect_broken_links()
        assert broken == [], (
            f"Found {len(broken)} broken internal doc link(s):\n"
            + "\n".join(f"  {b}" for b in broken)
        )

    def test_key_docs_exist(self):
        """Core professional-repo documents must be present."""
        required = [
            "README.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
            "CODE_OF_CONDUCT.md",
            "CHANGELOG.md",
            "LICENSE",
            "GETTING_STARTED.md",
        ]
        missing = [f for f in required if not os.path.isfile(os.path.join(REPO_ROOT, f))]
        assert missing == [], f"Missing required repo files: {missing}"
