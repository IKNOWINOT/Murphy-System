# Request: Complete Murphy System Audit and Hardening

I need you to act as a **principal software engineer and codebase auditor** to transform my Murphy system into a production-ready, maintainable codebase through a systematic 5-phase approach.

---

## ⚠️ REQUIRED INFORMATION (Complete Before Starting)

**[CODEBASE ACCESS]:** 
✅ **Repository at GitHub** - The codebase is available in the GitHub repository that Codex will be working with. All Murphy System 1.0 files are present in the `murphy_integrated/` directory, including:
- 2,000+ Python files across 67+ directories
- Complete source code for all components (Universal Control Plane, Integration Engine, Inoni Business Automation, Phase 1-5 implementations, original Murphy runtime)
- Documentation files (50,000+ words across 10+ documents)
- Configuration files (requirements, startup scripts, environment templates)
- Test files (test structure with pytest framework)

**[MURPHY DESCRIPTION]:** 
✅ **Murphy is a Universal AI Automation System** that serves as a complete control plane for automating any business type, including its own operations. Specifically:

**Core Purpose:**
- Universal automation platform capable of handling 6 automation types: factory/IoT (sensors, actuators), content publishing (blogs, social media), data processing (databases, analytics), system administration (DevOps, commands), agent reasoning (swarms, complex tasks), and business operations (sales, marketing, finance)

**Key Capabilities:**
1. **Self-Integration:** Automatically adds GitHub repositories, external APIs, and hardware devices with human-in-the-loop (HITL) safety approval. Uses SwissKiss loader to clone repos, analyze code, extract capabilities, generate modules/agents, test for safety, and request human approval before committing.

2. **Self-Improvement:** Learns from human corrections through a 4-method correction capture system (interactive, batch, API, inline), extracts patterns, and trains a shadow agent that improves accuracy from initial 80% to 95%+ over time.

3. **Self-Operation:** Runs Inoni LLC (the company that makes Murphy) autonomously through 5 business automation engines:
   - Sales Engine: Lead generation, qualification, outreach, demo scheduling
   - Marketing Engine: Content creation, social media, SEO, analytics
   - R&D Engine: Bug detection, code fixes, testing, deployment (Murphy fixes Murphy)
   - Business Management: Finance, support, project management, documentation
   - Production Management: Releases, QA, deployment, monitoring

4. **Safety & Governance:** Implements Murphy Validation (G/D/H formula + 5D uncertainty: UD/UA/UI/UR/UG), Murphy Gate (threshold-based validation), HITL checkpoints, authority-based scheduling, and complete audit trails.

**Architecture:**
- Two-phase execution: Phase 1 (Generative Setup - analyze request, determine control type, select engines, discover constraints, create ExecutionPacket, create session) → Phase 2 (Production Execution - load session, execute with selected engines, deliver results, learn from execution, repeat on schedule)
- Modular engine system with 7 engines (Sensor, Actuator, Database, API, Content, Command, Agent) that load per-session based on automation type
- Session isolation ensures different automation types don't interfere with each other

**Technology Stack:**
- Python 3.11+ with FastAPI REST API (30+ endpoints)
- LLM Integration: Groq (primary), onboard AI, Aristotle (NOT OpenAI or Anthropic)
- Machine Learning: PyTorch, scikit-learn for shadow agent training
- Infrastructure: Docker, Kubernetes, PostgreSQL, Redis, Prometheus, Grafana

**[CURRENT STATE]:** 
✅ **New/recent development with specific issues** - Murphy System 1.0 was completed on February 3, 2025. Current state:

**Completed Components:**
- ✅ All core architecture implemented (Universal Control Plane, Inoni Business Automation, Integration Engine, Two-Phase Orchestrator)
- ✅ Phase 1-5 implementations complete (forms, validation, correction capture, shadow agent training, deployment infrastructure)
- ✅ Original Murphy runtime (319 files) preserved and integrated
- ✅ Comprehensive documentation (50,000+ words)
- ✅ Basic test structure with pytest framework

**Known Issues:**
1. **Security Gaps (CRITICAL):**
   - No authentication/authorization system (API endpoints completely open)
   - No secrets management (API keys in plain environment variables)
   - No rate limiting (API can be overwhelmed)
   - No input sanitization beyond Pydantic schemas
   - No API versioning (breaking changes will affect all clients)

2. **Test Coverage (IMPORTANT):**
   - Test structure exists but actual test implementation is <10%
   - Critical paths untested (integration engine, Murphy validation, shadow agent)
   - No integration tests for end-to-end workflows
   - No performance/load testing

3. **Configuration Issues (IMPORTANT):**
   - Environment variables scattered across codebase
   - No centralized configuration management
   - Database connection handling incomplete (no pooling, no retry logic)
   - No graceful shutdown handling

4. **Error Handling (IMPORTANT):**
   - Many generic try/except blocks with broad exception catching
   - Inconsistent error response formats
   - No structured error hierarchy
   - Limited error context for debugging

5. **Monitoring Gaps (IMPORTANT):**
   - Prometheus/Grafana mentioned but not implemented
   - No metrics collection hooks
   - No health check beyond basic /api/health endpoint
   - No alerting system

6. **Code Quality (NICE-TO-HAVE):**
   - Inconsistent logging (mix of print statements and logger)
   - Incomplete type hints
   - Missing docstrings on many functions
   - Some complex sections lack inline comments

**System Status:**
- **Functional:** Yes, can execute tasks and integrations
- **Production-Ready:** No, needs security hardening and testing
- **Deployment Status:** Not deployed, ready for systematic audit
- **Last Updated:** February 3, 2025

**[SCOPE/TIME CONSTRAINTS]:** 
✅ **Comprehensive audit with specific priorities:**

**Priority 1: Security & Safety (MUST FIX)**
- Implement authentication/authorization system (JWT-based, RBAC)
- Add secrets management (environment-based with encryption)
- Implement rate limiting for all API endpoints
- Add input sanitization and validation beyond Pydantic
- Implement API versioning (/api/v1/)
- Review and harden HITL approval system (core safety feature)
- Validate Murphy Gate threshold logic
- Review credential verification system

**Priority 2: Testing & Reliability (MUST FIX)**
- Expand test coverage to 80%+ for critical paths
- Add integration tests for:
  - Integration Engine (GitHub ingestion, module generation, HITL approval)
  - Murphy Validation (G/D/H + 5D uncertainty calculations)
  - Shadow Agent Training (correction capture, pattern extraction, model training)
  - Two-Phase Orchestrator (setup → execute workflow)
  - Business Automation Engines (all 5 engines)
- Add performance/load tests (target: 1,000+ req/s)
- Add error scenario tests (network failures, invalid inputs, etc.)

**Priority 3: Production Readiness (IMPORTANT)**
- Implement proper error handling with structured exceptions
- Add comprehensive logging with structured format (JSON)
- Implement monitoring hooks (Prometheus metrics)
- Add health checks (liveness, readiness probes)
- Implement graceful shutdown (cleanup on SIGTERM/SIGINT)
- Add database connection pooling and retry logic
- Centralize configuration management
- Add backup strategy for critical data

**Priority 4: Code Quality & Maintainability (NICE-TO-HAVE)**
- Standardize logging approach (remove print statements)
- Add comprehensive type hints
- Add docstrings to all public functions
- Add inline comments for complex logic
- Enhance API documentation (Swagger/OpenAPI)
- Optimize async operations (remove blocking calls in async contexts)

**Areas to Avoid Changes:**
- ✅ Original Murphy Runtime (319 files) - Preserve as-is, only fix critical bugs
- ✅ SwissKiss Loader - Working correctly, only enhance if needed
- ✅ Documentation - Already comprehensive, only update for code changes
- ✅ Core Architecture - Design is sound, focus on implementation quality

**Special Considerations:**
- **LLM Integration:** Only use Groq, onboard AI, and Aristotle (NOT OpenAI or Anthropic)
- **HITL System:** This is a core safety feature - any changes must maintain human approval requirement
- **Murphy Validation:** G/D/H + 5D uncertainty is critical - validate logic but don't change formula
- **Shadow Agent:** Training pipeline is complex - test thoroughly before making changes
- **Backward Compatibility:** Maintain API compatibility where possible (use versioning for breaking changes)

**Timeline Expectations:**
- No hard deadline, but prioritize security fixes (Priority 1) first
- Comprehensive audit preferred over rushed fixes
- Wait for approval at each phase checkpoint before proceeding

---

## Mission Objectives

Transform the Murphy system through:
1. **Understanding** - Complete architecture and component analysis
2. **Fixing** - Resolve bugs, design flaws, and technical debt
3. **Testing** - Add comprehensive test coverage for critical functionality
4. **Preserving** - Archive (never delete) legacy/unused code with context
5. **Documenting** - Create clear documentation for future maintainers

---

## Execution Framework: 5-Phase Approach

### 📋 PHASE 1: Discovery & Inventory

**⚠️ CRITICAL: Make NO code changes until this phase is complete and I approve.**

#### Your Tasks:

**1. File System Audit**
   - List all files and directories with brief descriptions
   - Note file sizes and last modified dates where relevant
   - Identify all entry points (main files, scripts, executables)
   - Map the directory structure in a clear hierarchical format

**2. Architecture Mapping**
   - Identify core modules and their responsibilities
   - Map dependencies and data flows between components
   - Locate configuration files, tests, and documentation
   - Identify external dependencies and integrations

**3. File Classification**
   Categorize each file as:
   - `ACTIVE` - Currently used in production/main execution flow
   - `LEGACY` - Outdated but potentially referenced elsewhere
   - `TEST` - Test files, fixtures, and test utilities
   - `CONFIG` - Configuration, environment, and settings files
   - `DOCS` - Documentation and README files
   - `UNCLEAR` - Requires investigation or clarification

#### Deliverables:

Create these three documentation files (present their content in your response):

**`SYSTEM_OVERVIEW.md`**
- High-level description of what exists
- Directory structure and organization
- Key technologies and frameworks used
- External dependencies and versions

**`ARCHITECTURE_MAP.md`**
- Component relationships and interactions
- Data flows and processing pipelines
- Integration points and APIs
- System boundaries and interfaces

**`FILE_CLASSIFICATION.md`**
- Complete file inventory with classifications
- Brief purpose statement for each file
- Dependency relationships
- Files requiring investigation

#### Output Format:

Present your Phase 1 findings using this structure:

```markdown
## Phase 1 Complete: Discovery Summary

### File System Structure
[Organized tree view or hierarchical list]

### Entry Points Identified
- [Main execution entry points with descriptions]

### Key Components Discovered
- [Major subsystems and their purposes]

### Technology Stack
- [Languages, frameworks, libraries identified with versions]

### Initial Observations
- [Notable patterns, architectural decisions, concerns, or questions]

### Red Flags / Immediate Concerns
- [Any critical issues spotted during discovery]

### Documentation Files Content

#### SYSTEM_OVERVIEW.md
[Full content of this file]

#### ARCHITECTURE_MAP.md
[Full content of this file]

#### FILE_CLASSIFICATION.md
[Full content of this file]

### Questions for Clarification
[Any questions that need answers before proceeding]
```

**⏸️ CHECKPOINT: Wait for my review and approval before proceeding to Phase 2**

---

### 🔍 PHASE 2: Intent Analysis & Issue Identification

**Only begin this phase after I approve Phase 1 results.**

#### Your Tasks:

**For Each Major Component:**

**1. Purpose Determination**
   - What is this component supposed to do?
   - How does it fit into the larger system?
   - Document evidence (comments, naming conventions, structure, patterns)
   - Identify the component's contract/interface

**2. Integration Analysis**
   - What components depend on this one? (downstream dependencies)
   - What does this component depend on? (upstream dependencies)
   - Are there circular dependencies?
   - Are there tight coupling issues?
   - What are the data exchange patterns?

**3. Issue Identification & Categorization**

Classify each issue by severity:
   - 🔴 **CRITICAL**: Security vulnerabilities, data loss risks, crashes, corruption
   - 🟡 **IMPORTANT**: Duplicated logic, poor error handling, unclear intent, performance issues
   - 🟢 **NICE-TO-HAVE**: Style inconsistencies, minor optimizations, documentation gaps

For each issue, document:
   - Location (file and line numbers)
   - Description of the problem
   - Potential impact
   - Suggested fix approach
   - Estimated effort (small/medium/large)

**4. Decision-Making Protocol**

- **Infer and document** when intent is clear from code structure, naming, and patterns
- **Flag for my review** ONLY when:
  - A decision affects system correctness AND
  - Multiple valid interpretations exist AND
  - Wrong choice could break functionality OR
  - The change impacts system behavior significantly

#### Deliverables:

Present the content of these documentation files:

**`INTENT_ANALYSIS.md`**
- Purpose and responsibility of each component
- How components interact
- Design patterns identified
- Business logic documentation

**`ISSUES_IDENTIFIED.md`**
- Categorized list of all problems with severity ratings
- Location and description of each issue
- Impact assessment
- Suggested remediation approach
- Estimated effort/risk for fixes

**`ASSUMPTIONS_LOG.md`**
- Decisions made during analysis
- Reasoning and evidence for each decision
- Alternative interpretations considered
- Confidence level for each assumption (High/Medium/Low)

**`DEPENDENCY_GRAPH.md`**
- Visual or textual representation of component dependencies
- Circular dependencies highlighted
- Coupling hotspots identified
- Suggestions for decoupling where needed

#### Output Format:

```markdown
## Phase 2 Complete: Analysis Summary

### Components Analyzed
[List of major components with brief purpose]

### Critical Issues Found: [count]
[Summary of 🔴 critical issues with locations]

### Important Issues Found: [count]
[Summary of 🟡 important issues with locations]

### Nice-to-Have Improvements: [count]
[Summary of 🟢 improvements]

### Key Assumptions Made
[List of major assumptions with confidence levels]

### Questions Requiring Clarification
[Issues where I need your input - be specific]

### Documentation Files Content

#### INTENT_ANALYSIS.md
[Full content of this file]

#### ISSUES_IDENTIFIED.md
[Full content of this file]

#### ASSUMPTIONS_LOG.md
[Full content of this file]

#### DEPENDENCY_GRAPH.md
[Full content of this file]

### Recommended Priority Order for Fixes
1. [Issue category/area] - Rationale
2. [Issue category/area] - Rationale
[Continue with prioritized list]
```

**⏸️ CHECKPOINT: Wait for my review of issues and priorities before proceeding to Phase 3**

---

### 🧪 PHASE 3: Test Strategy & Implementation

**Only begin this phase after I approve Phase 2 results.**

**⚠️ IMPORTANT: Implement tests BEFORE making refactoring changes to ensure we don't break existing functionality.**

#### Your Tasks:

**1. Test Coverage Assessment**
   - What tests currently exist?
   - What is the current coverage percentage (if measurable)?
   - What critical paths are untested?
   - What integration points lack coverage?
   - What edge cases are not validated?

**2. Test Plan Creation**

Prioritize testing based on:
   - **Risk Level**: High-risk components get tested first
   - **Complexity**: Complex logic requires more thorough testing
   - **Change Frequency**: Frequently modified code needs regression tests
   - **Business Criticality**: Core functionality must be validated

For each component requiring tests, specify:
   - Test type needed (unit/integration/end-to-end)
   - Specific scenarios to cover
   - Expected inputs and outputs
   - Edge cases and error conditions

**3. Test Implementation**

Write tests that:
   - Follow the existing test framework (or recommend one if none exists)
   - Are clear, maintainable, and well-documented
   - Cover happy paths, edge cases, and error conditions
   - Use meaningful test names that describe what's being tested
   - Include setup and teardown where needed
   - Are independent and can run in any order

**4. Test Documentation**

For each test suite:
   - Explain what is being tested and why
   - Document any test data or fixtures required
   - Note any dependencies or prerequisites
   - Provide instructions for running the tests

#### Deliverables:

**`TEST_STRATEGY.md`**
- Overall testing approach and philosophy
- Test coverage goals
- Testing tools and frameworks to use
- Test organization structure
- How to run tests

**`TEST_PLAN.md`**
- Prioritized list of components to test
- Specific test scenarios for each component
- Coverage targets
- Timeline/effort estimates

**Test Implementation Files**
- Actual test code files
- Test fixtures and mock data
- Test utilities and helpers
- Configuration for test runners

**`TEST_COVERAGE_REPORT.md`**
- Current coverage metrics
- Coverage by component
- Gaps remaining
- Recommendations for additional testing

#### Output Format:

```markdown
## Phase 3 Complete: Testing Summary

### Current Test Coverage
- Existing tests: [count and description]
- Coverage percentage: [if measurable]
- Gaps identified: [summary]

### Test Strategy Overview
[Brief description of testing approach]

### Tests Implemented
[List of test files created with brief descriptions]

### Coverage Achieved
- Components now tested: [list]
- Test scenarios covered: [count]
- Edge cases validated: [count]

### Documentation Files Content

#### TEST_STRATEGY.md
[Full content of this file]

#### TEST_PLAN.md
[Full content of this file]

#### TEST_COVERAGE_REPORT.md
[Full content of this file]

### Test Implementation
[Present test code files with explanations]

### How to Run Tests
[Clear instructions for executing the test suite]

### Remaining Test Gaps
[Areas that still need testing and why]
```

**⏸️ CHECKPOINT: Wait for my review of test implementation before proceeding to Phase 4**

---

### 🔧 PHASE 4: Refactoring & Issue Resolution

**Only begin this phase after I approve Phase 3 results.**

**⚠️ CRITICAL: Run tests after EACH change to ensure nothing breaks.**

#### Your Tasks:

**1. Issue Resolution**

Address issues in this priority order:
   1. 🔴 **CRITICAL** issues first
   2. 🟡 **IMPORTANT** issues second
   3. 🟢 **NICE-TO-HAVE** improvements last

For each fix:
   - Explain what you're changing and why
   - Show before/after code snippets for significant changes
   - Run tests to verify the fix doesn't break anything
   - Document any side effects or related changes needed

**2. Code Preservation Protocol**

When removing or replacing code:
   - **NEVER delete code** - always move it to an archive
   - Create an `_archive/` directory at the project root
   - Organize archived code by date and reason
   - Include a manifest file explaining what was archived and why
   - Preserve the original file structure in the archive

Archive structure:
```
_archive/
  YYYY-MM-DD_reason/
    ARCHIVE_MANIFEST.md
    [original file structure]
```

**3. Refactoring Guidelines**

When refactoring:
   - Make small, incremental changes
   - Test after each change
   - Maintain backward compatibility where possible
   - Update related documentation
   - Keep commits/changes logically grouped

**4. Code Quality Improvements**

Apply these improvements where beneficial:
   - Extract duplicated code into reusable functions
   - Improve naming for clarity
   - Add error handling where missing
   - Simplify complex logic
   - Remove dead code (after archiving)
   - Add inline comments for complex sections

#### Deliverables:

**`CHANGES_LOG.md`**
- Chronological list of all changes made
- Rationale for each change
- Test results after each change
- Any issues encountered and how they were resolved

**`REFACTORING_SUMMARY.md`**
- Overview of refactoring approach
- Major changes by category
- Before/after metrics (if applicable)
- Breaking changes (if any)

**`_archive/` Directory**
- Archived legacy code
- Archive manifest files
- Preservation of original structure

**Updated Code Files**
- All modified source files
- Updated configuration files
- New utility functions or modules

#### Output Format:

```markdown
## Phase 4 Complete: Refactoring Summary

### Issues Resolved

#### Critical Issues (🔴)
- [Issue description] - [How it was fixed] - ✅ Tests passing
- [Continue for each critical issue]

#### Important Issues (🟡)
- [Issue description] - [How it was fixed] - ✅ Tests passing
- [Continue for each important issue]

#### Nice-to-Have Improvements (🟢)
- [Improvement description] - [What was changed] - ✅ Tests passing
- [Continue for each improvement]

### Major Refactoring Changes
[Summary of significant structural changes]

### Code Archived
[List of files/components moved to archive with reasons]

### Documentation Files Content

#### CHANGES_LOG.md
[Full content of this file]

#### REFACTORING_SUMMARY.md
[Full content of this file]

### Test Results
- Total tests run: [count]
- Tests passing: [count]
- Tests failing: [count] - [explanations if any]
- New tests added: [count]

### Breaking Changes
[List any breaking changes with migration guidance]

### Code Samples
[Show before/after for significant changes]
```

**⏸️ CHECKPOINT: Wait for my review of refactoring results before proceeding to Phase 5**

---

### 📚 PHASE 5: Documentation & Handoff

**Only begin this phase after I approve Phase 4 results.**

#### Your Tasks:

**1. User Documentation**

Create or update:
   - **README.md**: Project overview, quick start, basic usage
   - **INSTALLATION.md**: Detailed setup instructions
   - **USAGE_GUIDE.md**: Comprehensive usage examples
   - **CONFIGURATION.md**: All configuration options explained
   - **TROUBLESHOOTING.md**: Common issues and solutions

**2. Developer Documentation**

Create or update:
   - **ARCHITECTURE.md**: System design and component overview
   - **DEVELOPMENT_GUIDE.md**: How to contribute, coding standards
   - **API_DOCUMENTATION.md**: All APIs, endpoints, functions documented
   - **TESTING_GUIDE.md**: How to write and run tests
   - **DEPLOYMENT_GUIDE.md**: How to deploy to production

**3. Maintenance Documentation**

Create:
   - **CHANGELOG.md**: All changes made during this audit
   - **TECHNICAL_DEBT.md**: Remaining issues and future improvements
   - **DECISION_LOG.md**: Key architectural and design decisions
   - **RUNBOOK.md**: Operational procedures and monitoring

**4. Code Documentation**

Ensure:
   - All public functions have docstrings/comments
   - Complex algorithms are explained
   - Non-obvious code has inline comments
   - Module-level documentation exists
   - Examples are provided for key functionality

**5. Project Health Report**

Create a comprehensive report including:
   - Before/after comparison
   - Metrics (if applicable): code quality, test coverage, performance
   - Remaining technical debt
   - Recommendations for future work
   - Maintenance priorities

#### Deliverables:

**Complete Documentation Suite**
- All user-facing documentation
- All developer-facing documentation
- All maintenance documentation
- Inline code documentation

**`PROJECT_HEALTH_REPORT.md`**
- Comprehensive before/after analysis
- Metrics and improvements
- Remaining work
- Future recommendations

**`HANDOFF_CHECKLIST.md`**
- Verification that all deliverables are complete
- Instructions for next steps
- Contact points for questions

#### Output Format:

```markdown
## Phase 5 Complete: Documentation & Handoff Summary

### Documentation Created/Updated

#### User Documentation
- ✅ README.md
- ✅ INSTALLATION.md
- ✅ USAGE_GUIDE.md
- ✅ CONFIGURATION.md
- ✅ TROUBLESHOOTING.md

#### Developer Documentation
- ✅ ARCHITECTURE.md
- ✅ DEVELOPMENT_GUIDE.md
- ✅ API_DOCUMENTATION.md
- ✅ TESTING_GUIDE.md
- ✅ DEPLOYMENT_GUIDE.md

#### Maintenance Documentation
- ✅ CHANGELOG.md
- ✅ TECHNICAL_DEBT.md
- ✅ DECISION_LOG.md
- ✅ RUNBOOK.md

### Documentation Files Content

[Present the full content of each documentation file]

### Project Health Report

#### PROJECT_HEALTH_REPORT.md
[Full content of this comprehensive report]

### Handoff Checklist

#### HANDOFF_CHECKLIST.md
[Full content of this checklist]

### Before/After Comparison
- Files analyzed: [count]
- Issues fixed: [count by severity]
- Tests added: [count]
- Documentation pages created: [count]
- Code coverage: [before] → [after]

### Recommendations for Future Work
1. [Priority recommendation]
2. [Priority recommendation]
[Continue with prioritized list]

### Next Steps
[Clear guidance on what to do after this audit]
```

---

## 🎯 Success Criteria

This audit will be considered complete when:

1. ✅ All 5 phases are completed and approved
2. ✅ Critical and important issues are resolved
3. ✅ Test coverage is adequate for core functionality
4. ✅ All documentation is comprehensive and clear
5. ✅ Legacy code is properly archived with context
6. ✅ The system is production-ready and maintainable

---

## 📝 Working Principles

Throughout this audit, please:

1. **Communicate clearly**: Explain your reasoning and decisions
2. **Be systematic**: Follow the phases in order, wait for approval at checkpoints
3. **Preserve history**: Never delete code, always archive with context
4. **Test continuously**: Run tests after every change
5. **Document thoroughly**: Make your work understandable to future maintainers
6. **Ask when uncertain**: Flag ambiguities rather than guessing
7. **Think long-term**: Prioritize maintainability and clarity over cleverness

---

## 🚀 Ready to Begin

✅ **All required information has been provided:**
- ✅ Codebase access specified (GitHub repository)
- ✅ Murphy description complete (Universal AI Automation System)
- ✅ Current state documented (Recently completed, needs security hardening)
- ✅ Scope and priorities defined (Security → Testing → Production → Quality)

**Codex is ready to begin Phase 1: Discovery & Inventory**

Please proceed with the systematic audit, waiting for approval at each checkpoint before continuing to the next phase.