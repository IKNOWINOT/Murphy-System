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

### Deficiency Summary:
1. **D1-BUNDLE**: No ZIP download — only .txt file. FIXED: Created `src/demo_bundle_generator.py` + `/api/demo/download-bundle` endpoint.
2. **D2-CUSTOM**: Custom query fallback too thin. FIXED: Enhanced `_build_minimal_custom_content` with domain-aware rich templates.
3. **D3-PROPOSAL**: Automation proposal fragmented. FIXED: Created `_build_automation_proposal()` in bundle generator.
4. **D4-QUOTE**: No explicit 100% itemized quote. FIXED: Created `_build_itemized_quote()` in bundle generator.
5. **D5-DEMO-RUN**: `/api/demo/run` had no rate limiting. FIXED: Added rate limiting with same pattern as generate-deliverable.
6. **D6-SPEC-CUSTOM**: `generate_custom_deliverable` only conditionally appended blueprint/quality plan. FIXED: Now always appends both.

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
- [ ] Wire `_showSpecSummary` into `demoRun()` completion flow — call it after API response with spec data
- [ ] Show bundle download + spec summary buttons only after demo completes (hide initially)

## Phase 5: Frontend — murphy_landing_page.html
- [ ] Add bundle download button to forge result section
- [ ] Add `_forgeDownloadBundle()` function for ZIP download from landing page
- [ ] Add spec summary display in forge result section
- [ ] Wire spec summary into `_showResult()` completion flow

## Phase 6: Commissioning Tests
- [ ] Create `tests/commissioning/test_wave11_demo_system.py`
- [ ] Test: custom queries across 10+ domains produce valid deliverables
- [ ] Test: rate limiting enforced correctly (5/anon, 10/free)
- [ ] Test: deliverable contains actual content (not placeholder)
- [ ] Test: automation spec has itemized workflows with cost breakdown
- [ ] Test: bundle generator produces valid ZIP with professional structure
- [ ] Test: all demo API endpoints return expected shapes
- [ ] Run all tests and verify pass

## Phase 7: Documentation & Deficiency Report
- [ ] Create deficiency report with all findings
- [ ] Create API/SDK recommendations list
- [ ] Update `docs/AUDIT_AND_COMPLETION_REPORT.md` with Wave 11 summary
- [ ] Commit and push all changes

## Phase 8: Video Capability Note
- [ ] Communicate to user about video recording limitation