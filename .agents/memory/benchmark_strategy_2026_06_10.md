# Murphy Benchmark Strategy — locked 2026-06-10 (ship 28/29)

## Honest baseline (real numbers, real LLM, real tasks)

Model: Llama-3.3-70B-Instruct-Turbo (Together AI)
Date: 2026-06-10
Tasks: 10 hand-curated tau-bench-style multi-turn workflows (retail, airline, finance, it_support, hr)

| Run | Mean Score | Strict Pass | Latency/task |
|---|---|---|---|
| Baseline (single-shot) | 45.0% | 30.0% (3/10) | 2.4s |
| Murphy architecture (plan→verify→act) | **65.0%** | **40.0% (4/10)** | 7.7s |

Delta: **+20 mean score points** from architecture alone, same model.

Artifacts:
- `/documentation/testing/benchmark_real/murphy_tau_real_1781136047.json` (baseline)
- `/documentation/testing/benchmark_real/murphy_tau_architecture_1781136178.json` (Murphy)

## Truth hygiene action taken

Archived the 4 synthetic JSON files (tau, agent-bench, tool-bench, terminal-bench
from 2026-03-13) to `/documentation/testing/_synthetic_archive/` with a README
disclaiming them. They were harness-only runs without real LLM calls; the scores
(1.0, 0.5, 0.0) were placeholder defaults. Cannot be cited as evidence.

## Standardized rubrics to target (priority order)

1. **τ-bench (Princeton/Sierra)** — 375 tasks, public leaderboard
   Current SOTA pass^1: 74.5% (Automation Anywhere, May 2026 vs GPT-5.2, Claude Opus 4.5, Gemini 3 Pro, Qwen 3.5)
   Next: clone sierra-research/tau-bench, wire Murphy's executor, run pass^1-4
   
2. **GAIA (Hugging Face)** — general AI assistant, public leaderboard
   Adapter already drafted at `/src/benchmark_adapters/gaia_adapter.py`

3. **SWE-bench Verified (Princeton)** — real GitHub issue resolution
   Murphy's autonomous-PR loop is the natural fit

4. **AgentBench (Tsinghua)** — multi-environment

## Proprietary rubric (the wedge)

**Murphy-Bench v0.1** — defined this session:
- 5 domains: retail, airline, finance, it_support, hr
- Multi-turn HITL-aware tasks
- Trajectory-aware scoring (not just goal-completion)
- Two-stage plan→verify architecture as reference implementation

When we scale Murphy-Bench to 100+ tasks and open-source the scoring code,
we own a rubric the industry can measure against. Owning the rubric = owning
the surface space conversation.

## Five fronts (from the strategy doc)

1. Standardized rubrics — real τ-bench submission within 30 days
2. Proprietary rubric (Murphy-Bench) — open-source, public methodology
3. Pilot invitations — Palantir partner network, OpenAI FDE group, Anthropic SAs
4. Developer surface — SDK at /api/agents/spawn, marketplace at /agents
5. Public credibility — blog posts, LinkedIn responses, quarterly reports

## What's true I can defend right now

- "Architecture matters: +20 score points from same LLM, same tasks, just wrapping it"
- "Murphy ran a real benchmark on real LLM — we have JSON receipts"
- "30-day plan to be on the τ-bench leaderboard with a real submission"

## What I CANNOT claim yet

- "Murphy is SOTA on τ-bench" — we've run 10 tasks, not 375
- "Murphy beats GPT-5.2 / Claude Opus" — we don't know, haven't tested
- "Murphy is production-grade for enterprise" — we have one real customer test (zero paying)

## Next 30 days

Week 1 (now): real τ-bench full 375-task run with Llama-3.3-70B
Week 2: same with Claude Opus 4.5 via Anthropic API
Week 3: write up methodology + results, post to LinkedIn
Week 4: submit to leaderboard, draft Murphy-Bench v1.0 paper
