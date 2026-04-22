"""Forge regression suite — locks in the FORGE-DETECT-002 + FORGE-PREDEF-002 fixes.

This test is the executable form of the in-session black-box evaluation
that documented the demo-forge regressions:

* **FORGE-DETECT-001 baseline** — first-match dict iteration in
  ``_detect_scenario`` mis-routed three of six landing-page chips:
  the "automation" chip → ``onboarding``, the "course" chip →
  ``automation``, the "biz_auto" chip → ``onboarding``.
* **FORGE-PREDEF-001 baseline** — three distinct game prompts produced
  96.8 - 97.5 % byte-identical bodies because the matched-scenario path
  returned ``_SCENARIO_TEMPLATES[k]`` verbatim, never invoking the LLM
  or any per-prompt composition.

The replacement implementations are documented in
``demo_deliverable_generator._detect_scenario`` (FORGE-DETECT-002) and
``demo_deliverable_generator.generate_predefined_deliverable``
(FORGE-PREDEF-002).  This test enforces both the routing and the
no-template-pumping invariants so the regressions cannot silently come
back.

Per-prompt eval data lives at the top of this file as ``CHIP_PROMPTS``
to mirror the chip set on ``index.html`` exactly — keep them in sync
when the landing page changes.
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

import pytest

# The Forge module lives under "Murphy System/src" but is imported as a
# top-level module by the production server (which adds both
# "Murphy System" and "Murphy System/src" to ``sys.path``).  The test
# replicates that path setup so the imports resolve identically.
_REPO = Path(__file__).resolve().parents[2]
for p in (_REPO / "Murphy System", _REPO / "Murphy System" / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:  # pragma: no cover - skip cleanly if heavy deps missing
    from demo_deliverable_generator import (  # type: ignore
        _detect_scenario,
        generate_deliverable,
    )
except Exception as exc:  # pragma: no cover
    pytest.skip(f"demo_deliverable_generator unavailable: {exc}", allow_module_level=True)


# ---------------------------------------------------------------------------
# Landing-page chip prompts.  Keep in sync with index.html.
# Each entry: chip-id → (prompt, expected scenario key or None for "custom").
# ---------------------------------------------------------------------------
CHIP_PROMPTS: dict = {
    "mmorpg": (
        "build me a playable single-level html5 mmorpg game with original story, "
        "canvas sprites, touch controls, and mobile publishing guide",
        "game",
    ),
    "webapp": (
        "build me a complete web app mvp with dashboard, task management, "
        "fastapi backend, and deployment guide",
        "app",
    ),
    "automation": (
        "build me a complete vertical automation suite with stripe payment "
        "processing, agentic workflows, onboarding, and webhook handling",
        "automation",
    ),
    "course": (
        "build me a complete course on applied python for business automation "
        "with lessons, exercises, answer keys, and grading rubrics",
        "course",
    ),
    "biz_auto": (
        "automate my entire business operations including invoicing accounts "
        "payable hr onboarding compliance and reporting",
        "automation",
    ),
    "bizplan": (
        "generate a complete business plan with executive summary market analysis "
        "financial projections marketing strategy and funding requirements",
        None,  # legitimately "custom" — bizplan has no dedicated template
    ),
}


class TestChipRoutingMatrix:
    """FORGE-DETECT-002 — every landing-page chip routes to the correct scenario."""

    @pytest.mark.parametrize("chip_id,prompt,expected", [
        (cid, p, exp) for cid, (p, exp) in CHIP_PROMPTS.items()
    ])
    def test_chip_routes_to_expected_scenario(self, chip_id, prompt, expected):
        got = _detect_scenario(prompt)
        assert got == expected, (
            f"Chip '{chip_id}' should route to {expected!r} but got {got!r}.\n"
            f"  Prompt: {prompt!r}\n"
            f"  Regression to FORGE-DETECT-001 first-match heuristic?"
        )

    def test_no_chip_routes_to_onboarding_unless_explicitly_about_onboarding(self):
        """Specific guard against the headline misrouting bug.

        Three chips contain the word "onboarding" as one feature among
        many.  None of them should route to the onboarding template;
        the onboarding chip is for prompts that are *primarily* about
        client onboarding.
        """
        for chip_id in ("automation", "biz_auto"):
            prompt, _expected = CHIP_PROMPTS[chip_id]
            got = _detect_scenario(prompt)
            assert got != "onboarding", (
                f"Chip '{chip_id}' mis-routed to 'onboarding' — this was the "
                f"FORGE-DETECT-001 regression."
            )


class TestNoTemplatePumping:
    """FORGE-PREDEF-002 - distinct prompts in the same scenario must
    produce distinct bodies (no verbatim template echo).
    """

    GAME_PROMPTS = [
        "build me a playable single-level html5 mmorpg game with original story, "
        "canvas sprites, touch controls, and mobile publishing guide",
        "create a phone game with multiplayer dungeons, leaderboards, and in-app purchases",
        "make a browser game shooter with pixel art and 8-bit chiptune music",
    ]

    APP_PROMPTS = [
        "build me a complete web app mvp with dashboard, task management, "
        "fastapi backend, and deployment guide",
        "create a real-time collaborative document editor with WebSockets and Postgres",
    ]

    def _generate_bodies(self, prompts):
        return [generate_deliverable(p)["content"] for p in prompts]

    def test_game_prompts_produce_distinct_byte_hashes(self):
        bodies = self._generate_bodies(self.GAME_PROMPTS)
        hashes = {hash(b) for b in bodies}
        assert len(hashes) == len(bodies), (
            "Two different game prompts produced byte-identical bodies — "
            "FORGE-PREDEF-001 template-pumping regression."
        )

    def test_game_prompts_produce_distinct_byte_lengths(self):
        bodies = self._generate_bodies(self.GAME_PROMPTS)
        lengths = [len(b) for b in bodies]
        # The FORGE-PREDEF-001 baseline produced 22744 / 22661 / 22748 — within
        # 1 % of each other.  Distinct prompts should diverge more than 2 %.
        spread = (max(lengths) - min(lengths)) / max(lengths)
        assert spread > 0.02, (
            f"Game prompts produced near-identical byte lengths {lengths!r} "
            f"(spread={spread:.3f}).  Indicates template-pumping has returned."
        )

    def test_app_prompts_produce_distinct_byte_hashes(self):
        bodies = self._generate_bodies(self.APP_PROMPTS)
        assert len({hash(b) for b in bodies}) == len(bodies)

    def test_each_body_contains_its_own_distinctive_words(self):
        """Each generated deliverable must mention at least one phrase
        from its own prompt that is *not* in any other prompt.  This
        catches the case where bodies happen to differ only in
        boilerplate timestamps but not in scope acknowledgement.
        """
        prompts = self.GAME_PROMPTS
        bodies = self._generate_bodies(prompts)
        # For each body, find a distinctive token from its prompt that
        # doesn't appear in the other prompts.
        per_prompt_unique = []
        for i, p in enumerate(prompts):
            others = " ".join(prompts[:i] + prompts[i + 1:]).lower()
            tokens = [t for t in p.lower().replace(",", " ").split() if len(t) > 4]
            unique = [t for t in tokens if t not in others]
            per_prompt_unique.append(unique)
        for i, body in enumerate(bodies):
            assert per_prompt_unique[i], (
                f"Test setup error: prompt {i} has no unique tokens vs the others"
            )
            body_low = body.lower()
            assert any(tok in body_low for tok in per_prompt_unique[i]), (
                f"Body for game prompt {i} does not mention any of its "
                f"distinctive tokens {per_prompt_unique[i]!r} — the deliverable "
                f"is not actually personalised to the prompt."
            )

    def test_line_overlap_below_template_pumping_baseline(self):
        """Soft regression check.

        The FORGE-PREDEF-001 baseline produced 96.8 - 97.5 % identical
        lines across distinct game prompts.  The replacement should
        leave headroom — we require < 90 % to allow for legitimately
        repeated structural lines (section headers, footers, branding)
        while catching any return to verbatim-template behaviour.
        """
        bodies = self._generate_bodies(self.GAME_PROMPTS)

        def overlap(a: str, b: str) -> float:
            sm = difflib.SequenceMatcher(a=a.splitlines(), b=b.splitlines())
            equal = sum(
                (i2 - i1)
                for op, i1, i2, j1, j2 in sm.get_opcodes()
                if op == "equal"
            )
            total = max(len(a.splitlines()), len(b.splitlines()))
            return equal / total if total else 0.0

        for i in range(len(bodies)):
            for j in range(i + 1, len(bodies)):
                ov = overlap(bodies[i], bodies[j])
                assert ov < 0.90, (
                    f"Line overlap {ov:.3f} between game prompts {i} and {j} "
                    f"exceeds 0.90 ceiling - regression to template pumping."
                )


class TestProviderAttribution:
    """FORGE-PROVIDER-001 (P2b) — every deliverable must carry an
    ``llm_provider`` field so the UI can distinguish real LLM output
    from composer-only fallback content.
    """

    def test_predefined_path_sets_llm_provider(self):
        prompt, expected_scenario = CHIP_PROMPTS["mmorpg"]
        assert expected_scenario == "game"  # sanity
        d = generate_deliverable(prompt)
        assert "llm_provider" in d, "predefined path must populate llm_provider"
        assert d["llm_provider"] in {"llm", "composer"}, (
            f"unexpected llm_provider value: {d['llm_provider']!r}"
        )

    def test_custom_path_sets_llm_provider(self):
        prompt, expected_scenario = CHIP_PROMPTS["bizplan"]
        assert expected_scenario is None  # sanity
        d = generate_deliverable(prompt)
        assert "llm_provider" in d
        assert d["llm_provider"] in {"llm", "composer"}
