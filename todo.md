# Murphy System — Demo Commissioning & Enhancement Plan (Wave 11)

## Phase 1: Audit Existing Demo Infrastructure
- [x] Read and audit `src/demo_runner.py` (520 lines — DemoRunner, 6 scenarios + custom, real pipeline with fallback)
- [x] Read and audit `src/demo_deliverable_generator.py` (4040 lines — predefined templates + custom LLM pipeline)
- [x] Read and audit `demo.html` (417 lines — standalone demo page with terminal animation)
- [x] Read and audit `murphy_landing_page.html` (1823 lines — landing page with Forge demo section)
- [x] Read and audit demo API endpoints in `src/runtime/app.py` (demo/run, demo/export, demo/generate-deliverable, demo/spec/{id}, demo/forge-stream)
- [x] Read and audit `src/subscription_manager.py` (rate limiting: 5/day anon, 10/day free, unlimited paid)
- [x] Read and audit `src/forge_rate_limiter.py` (192 lines — forge-specific rate limiter)
- [x] Read existing tests: `test_demo_commission.py`, `test_demo_deliverable.py`

## Phase 2: Identify Gaps vs User Requirements
- [x] Gap analysis completed — 6 deficiencies identified (D1-D6)

## Phase 3: Fix Identified Deficiencies (Backend)
- [x] Create `src/demo_bundle_generator.py` — ZIP bundle with professional file structure
- [x] Enhance `_build_minimal_custom_content` with domain-aware content (sales, marketing, support, operations, generic)
- [x] Make automation blueprint + quality plan always append in `generate_custom_deliverable`
- [x] Add rate limiting to `/api/demo/run` endpoint
- [x] Add `/api/demo/download-bundle` endpoint for ZIP download

## Phase 4: Frontend — demo.html
- [x] Add ZIP download button ("Download Full Package") to demo.html
- [x] Add `downloadBundle()` function calling `/api/demo/download-bundle`
- [x] Add `_showSpecSummary()` function for inline automation proposal display
- [x] Add `#demo-spec-summary` container div
- [x] Wire `_showSpecSummary` into `demoRun()` completion flow
- [x] Show bundle download + spec summary buttons only after demo completes

## Phase 5: Frontend — murphy_landing_page.html
- [x] Add bundle download button to forge result section
- [x] Add `_forgeDownloadBundle()` function for ZIP download from landing page
- [x] Add spec summary display in forge result section
- [x] Wire spec summary into `_showResult()` completion flow

## Phase 6: Commissioning Tests
- [x] Create `tests/commissioning/test_wave11_demo_system.py`
- [x] Test: custom queries across 14 domains produce valid deliverables (42 parametrized tests)
- [x] Test: rate limiting enforced correctly (5/anon, 10/free)
- [x] Test: deliverable contains actual content (not placeholder)
- [x] Test: automation spec has itemized workflows with cost breakdown
- [x] Test: bundle generator produces valid ZIP with professional structure
- [x] Test: all demo API endpoints return expected shapes
- [x] Run all tests — **114/114 PASS**

## Phase 7: Documentation & Deficiency Report
- [x] Create deficiency report (`docs/WAVE11_DEMO_DEFICIENCY_REPORT.md`)
- [x] Create API/SDK recommendations (`docs/WAVE11_API_SDK_RECOMMENDATIONS.md`)
- [x] Update `docs/AUDIT_AND_COMPLETION_REPORT.md` with Wave 11 summary
- [x] Commit and push all changes — commit `454266f9`

## Phase 8: Video Capability Note
- [x] Communicate to user about video recording limitation (see delivery message)