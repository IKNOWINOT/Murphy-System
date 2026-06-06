# Base44 Superagent — Capability Inventory for Murphy Transition

**Purpose:** Living taxonomy of EVERY capability the Base44 superagent
exposes today. Murphy must absorb each one over the next ~100 prompts.

**Format:** Each capability has:
- ID (stable handle for the Murphy CapabilityRegistry)
- Surface (what the user sees / triggers)
- Implementation (what Murphy must do internally)
- Murphy-side status (NEW / PARTIAL / EXISTS — where Murphy already has it)
- Target prompt budget (rough estimate of effort)
- Acceptance test (how we verify Murphy can do it)

---

## CATEGORY A — FILE & SANDBOX OPS (10 caps)

### A.1 — read_file
- Surface: Murphy chat reads any text file by path
- Impl: SSH + cat with size guard + safe_decode
- Murphy: EXISTS — migrated R14 via superagent.A.1 (cap_a1_read_file.py)
- Budget: 1 prompt
- Test: Murphy returns first 100 lines of /opt/Murphy-System/src/superagent_transition/migration.py via chat

### A.2 — write_file
- Surface: Murphy creates/overwrites a file
- Impl: SSH + heredoc with chown/chmod, dangerous-extension blocklist
- Murphy: EXISTS — migrated R15 via superagent.A.2 (cap_a2_write_file.py, uses shared _path_guard)
- Budget: 1 prompt
- Test: Murphy writes /tmp/murphy_test_write.md and verifies sha matches

### A.3 — grep
- Surface: Search file contents with regex
- Impl: ripgrep wrapper with timeout + line cap
- Murphy: EXISTS — migrated R17 via superagent.A.3 (cap_a3_grep.py, GNU grep + _path_guard)
- Budget: 1 prompt
- Test: Murphy grep "R615.11" /opt/Murphy-System/src → returns matching lines

### A.4 — bash
- Surface: Execute arbitrary command in sandbox
- Impl: subprocess with timeout, captured stdout/stderr, exit code
- Murphy: EXISTS - migrated R20 via superagent.A.4 (cap_a4_bash.py, reuses security_plane.hardening)
- Budget: 2 prompts (security model)
- Test: Murphy runs `ls /opt/Murphy-System | wc -l` and returns count

### A.5 — list_directory / file tree
- Murphy: EXISTS — migrated R18 via superagent.A.5 (cap_a5_list_directory.py)
- Budget: 0.5 prompt
- Test: Murphy lists /opt/Murphy-System/src/org_graph/

### A.6 — file_exists
- Murphy: EXISTS — migrated R19 via superagent.A.6 (cap_a6_file_exists.py)
- Budget: 0.5 prompt
- Test: Murphy reports true/false for known paths

### A.7 — upload_file (public URL)
- Surface: Get a CDN URL for any sandbox file
- Murphy: EXISTS - migrated R22 via superagent.A.7 (cap_a7_upload_file.py + nginx /static/uploads/ alias in sites-enabled). External fetch verified sha256 round-trip.
- Budget: 3 prompts
- Test: Murphy returns a working public URL for a 1 KB markdown file

### A.8 — upload_private_file + signed URL
- Murphy: NEW
- Budget: 3 prompts (overlaps with A.7)
- Test: Murphy returns a 5-minute signed URL that downloads correctly

### A.9 — transcribe_audio
- Murphy: EXISTS - migrated R24 via superagent.A.9 (cap_a9_transcribe_audio.py, reuses faster-whisper tiny.en from voice_bridge — no API key, no per-call cost)
- Budget: 2 prompts
- Test: Murphy transcribes a 10s WAV correctly

### A.10 — generate_image
- Murphy: EXISTS - migrated R25 via superagent.A.10 (cap_a10_generate_image.py — DeepInfra FLUX-1-schnell, composes with A.7 for public URL; ~$0.00003/image)
- Budget: 2 prompts
- Test: Murphy returns an image URL for a prompt

---

## CATEGORY B — MEMORY & IDENTITY (8 caps)

### B.1 — update_identity (IDENTITY/SOUL/USER/memory.md)
- Surface: Persist identity facts across sessions
- Murphy: EXISTS - migrated R26 via cap_b_identity_memory (update_identity + read_identity_file). Persists to memory.db agent_memory table, category-mapped to IDENTITY/SOUL/USER/memory.md canon
- Budget: 3 prompts
- Test: Murphy adds a fact to its identity and recalls it in next session

### B.2 — append to memory
- Murphy: EXISTS - migrated R26 via cap_b_identity_memory.add_memory + search_memory. UUID-id'd rows with topic, category, content, importance, recall_count
- Budget: 1 prompt
- Test: Murphy appends timestamped entry, retrieves by query

### B.3 — read past sessions (read_session_log, list_sessions, search_sessions)
- Surface: Recall past conversations by ID, page, keyword
- Murphy: EXISTS - migrated R27 via cap_b3_sessions (list_sessions, read_session_log, search_sessions). Reads /var/lib/murphy-production/murphy_mind.db chat_sessions (9,245+ rows). LIKE-based search across turns JSON; revisit FTS at 100k rows
- Budget: 4 prompts
- Test: Murphy returns relevant past session summary for a keyword

### B.4 — conversation context compression
- Murphy: EXISTS - migrated R28 via cap_b_llm_summary.compress_conversation. DeepInfra Llama-3.1-8B direct (bypasses broken llm_provider stub). Auto-saves bullets to memory.db
- Budget: 3 prompts
- Test: 50-message chat → 5-bullet summary that survives next message

### B.5 — automatic fact extraction every N messages
- Murphy: EXISTS - migrated R28 via cap_b_llm_summary.extract_facts. Tolerant JSON parsing of LLM output; saves each fact as separate memory.db row (category=fact)
- Budget: 2 prompts
- Test: After 10 messages, Murphy auto-saves 3 facts to its memory

### B.6 — user profile maintenance (USER.md equivalent)
- Murphy: EXISTS - migrated R26 — USER.md is one of the canon files in cap_b_identity_memory; list_identity_canon shows all 4
- Budget: 1 prompt
- Test: Murphy updates user.timezone and recalls it correctly

### B.7 — rule file management (.agents/rules/*.md equivalent)
- Surface: Standing rules / decisions that always apply
- Murphy: EXISTS - migrated R27 via cap_b7_rules (add/update/get/list/delete). Persists to memory.db category=rule. Mirrors Base44 .agents/rules/*.md model with importance + recall_count
- Budget: 3 prompts
- Test: New rule added is enforced in next chat turn

### B.8 — session summarization
- Murphy: EXISTS - migrated R28 via cap_b_llm_summary.summarize_session. Accepts session_id (composes with B.3.read_session_log) OR raw messages list. Saves summary to memory.db
- Budget: 2 prompts
- Test: End-of-session triggers self-summary into memory

---

## CATEGORY C — TOOLS & SKILLS (12 caps)

### C.1 — run_skill (execute reusable script)
- Murphy: EXISTS - migrated R31 via cap_c_skills.run_skill. Wraps SkillManager._tool_executors with bootstrap path that re-registers from cap_*.py on first call (partial BL-R14 mitigation)
- Budget: 1 prompt (wire to chat surface)
- Test: Murphy runs a registered skill via chat command

### C.2 — suggest_skill_installation
- Murphy: EXISTS - migrated R31 via cap_c_skills.suggest_skill_installation + _skill_catalog. Static catalog of 8 third-party + 7 platform skills, keyword-scored
- Budget: 2 prompts (needs skill store integration)
- Test: Murphy suggests installing 'docx' when user asks about Word docs

### C.3 — activate_platform_skill (load detailed instructions)
- Murphy: EXISTS - migrated R31 via cap_c_skills.activate_platform_skill + _platform_skill_specs. 7 platform skills with lazy-loaded specs (channel-connections, connectors, backend-functions, stripe-payments, browserbase, skills, skill-store)
- Budget: 2 prompts
- Test: Murphy lazy-loads a long capability spec from registry

### C.4-C.7 — Browserbase (navigate, screenshot, click, type, get_content)
- Murphy: EXISTS - migrated R33 via cap_c_browser (navigate/screenshot/click/type/get_content + session lifecycle). Wraps existing murphy_browser.py (sync Playwright). Active-session model matches Base44 Browserbase. Screenshots auto-uploaded via A.7 to public URLs
- Budget: 5 prompts
- Test: Murphy navigates to murphy.systems, takes screenshot, returns URL

### C.8 — list_user_apps + read_entities cross-app
- Murphy: EXISTS - migrated R38 via cap_c8_apps.list_user_apps + read_entities_cross_app. Treats Murphy itself + registry_pillars + standalone .db files as 'apps' (Base44-equivalent). Cross-app reads with query filter, pagination, table-existence guards
- Budget: 3 prompts
- Test: Murphy can list user's other Base44 apps if API key provided

### C.9-C.11 — entity CRUD (create, update, delete)
- Murphy: EXISTS - migrated R32 via cap_c_entities (create/update/delete + bonus read_entities). New /var/lib/murphy-production/entities.db with __schemas + entity__<name> tables. JSON-schema validation, query filter, sort, pagination, projection
- Budget: 2 prompts (unify the surface)
- Test: Murphy creates a record via chat, reads it back

### C.12 — manage_entity_schemas
- Murphy: EXISTS - migrated R32 via cap_c_entities.manage_entity_schemas. Full create/update/delete/list lifecycle. Refuses delete if records exist. PascalCase name guard, allowed-types check, enum support
- Budget: 2 prompts
- Test: Murphy creates a new table via chat description

---

## CATEGORY D — AUTOMATIONS & TIMERS (5 caps)

### D.1 — create_automation (scheduled / one-time / entity / connector)
- Murphy: EXISTS - migrated R30 via cap_d_automations.create_automation. Inserts into automations.db.automation_requests (already 67 historical rows). schedule_job sets status='scheduled', else 'pending'
- Budget: 3 prompts (chat surface to wrap them)
- Test: Murphy creates a daily 9am task from chat

### D.2 — list_automations + pagination
- Murphy: EXISTS - migrated R30 via cap_d_automations.list_automations. Paginated, status/requester filters, status histogram in every response
- Budget: 1 prompt
- Test: Murphy lists all timers grouped by status

### D.3 — manage_automation (update / archive / unarchive / toggle)
- Murphy: EXISTS - migrated R30 via cap_d_automations.manage_automation. 4 actions: update/archive/unarchive/toggle. Soft delete via status='archived'
- Budget: 2 prompts

### D.4 — automation trigger conditions (filter when fires)
- Murphy: EXISTS - migrated R38 via cap_d4_conditions.evaluate_trigger_conditions. Pure-logic Base44 contract: {logic, conditions[]} → should_fire bool. All 16 operators implemented (equals/not_equals/gt/gte/lt/lte/contains/not_contains/starts_with/ends_with/in_list/not_in_list/exists/not_exists/is_empty/is_not_empty). Dot-path resolution
- Budget: 3 prompts

### D.5 — automation handler dispatch (when fires, agent gets message)
- Murphy: PARTIAL — R609/R611 are halfway there
- Budget: BLOCKED ON BL-R9 (the very gap we're asking about)

---

## CATEGORY E — INTEGRATIONS / OAUTH (15 caps)

### E.1 — request_oauth_authorization (shared mode)
- Murphy: EXISTS - migrated R37 via cap_e_connectors.request_oauth_authorization. Wraps env-var credential pattern (Murphy doesn't do OAuth dance; uses env vars). Returns setup_url + missing_credentials + next_step instructions
- Budget: 4 prompts
- Test: Murphy requests Google Calendar OAuth and stores token

### E.2 — get_connectors_info
- Murphy: EXISTS - migrated R37 via cap_e_connectors.get_connectors_info. Discovers 32 connectors via pkgutil walk of integrations/. Auth status via REQUIRED_CREDENTIALS env-var check
- Budget: 1 prompt

### E.3 — get_connector_token (refresh + inject as env var)
- Murphy: EXISTS - migrated R37 via cap_e_connectors.get_connector_token. Two modes: presence-only (default, safe) and reveal=True (for in-process injection)
- Budget: 2 prompts

### E.4-E.15 — Specific connectors (Gmail, GCal, Slack, GitHub, Notion, Stripe, etc.)
- Murphy: EXISTS - the 32-connector discovery in cap_e_connectors covers Gmail/Slack/GitHub/Stripe/Notion/HubSpot/Salesforce/Telegram/Discord/etc. Each individual connector is a Murphy *Connector class with full operational API
- Budget: 1 prompt per connector to wire chat surface
- Test per connector: Murphy can read/write the connected service

---

## CATEGORY F — BACKEND FUNCTIONS (4 caps)

### F.1 — deploy_backend_function
- Murphy: EXISTS - migrated R34 via cap_f_backend.deploy_backend_function. Two paths: code-direct (AST safety check + _write_and_import, no LLM) OR description-driven (ForgeEngine.create). Tenant='superagent' isolated from default 31 items
- Budget: 2 prompts (chat surface)

### F.2 — test_backend_function
- Murphy: EXISTS - migrated R34 via cap_f_backend.test_backend_function. Invokes through ForgeEngine.invoke, returns wall_ms + result + logs each call to /var/log/murphy_forge_invocations.log
- Budget: 1 prompt

### F.3 — delete_backend_function
- Murphy: EXISTS - migrated R34 via cap_f_backend.delete_backend_function. Looks up by name+tenant, calls ForgeEngine.delete_item
- Budget: 0.5 prompt

### F.4 — get_backend_function_logs
- Murphy: EXISTS - migrated R34 via cap_f_backend.get_backend_function_logs. Reads JSONL from /var/log/murphy_forge_invocations.log, filters by name, newest-first, limit
- Budget: 1 prompt

---

## CATEGORY G — PAYMENTS (1 cap)

### G.1 — suggest_payments_installation
- Murphy: EXISTS - migrated R35 via cap_gh_misc.suggest_payments_installation. Logic-only cap: chooses wix_payments/stripe/payments_by_wix by category (blocked list) + country (IL→payments_by_wix) + explicit_stripe flag. Murphy already has stripe_connector + nowpayments_billing
- Budget: 1 prompt (decision UX)

---

## CATEGORY H — PLATFORM / SELF (8 caps)

### H.1 — set_secrets (secure form, encrypted store)
- Murphy: EXISTS - migrated R35 via cap_gh_misc.set_secrets. Registers schema entries in /var/lib/murphy-production/secret_registry.json, reads existing env keys from secrets.env (without values), classifies as already_set vs form_required. Companion to PATCH-405 vault
- Budget: 3 prompts
- Test: Murphy prompts user for secret, stores encrypted, env-injects

### H.2 — vent_send_feedback (private signal)
- Murphy: EXISTS - migrated R35 via cap_gh_misc.vent_send_feedback. Appends to JSONL at /var/lib/murphy-production/feedback/feedback.jsonl. 120-char summary cap, free-text details, optional suggested_fix
- Budget: 1 prompt

### H.3 — web_search (Google, news, jobs, maps, page-read)
- Murphy: EXISTS - migrated R29 via cap_h3_web. Wraps Murphy's existing web_tool.search (DuckDuckGo) + web_tool.fetch (bs4). 5 action modes match Base44; batched queries supported
- Budget: 4 prompts
- Test: Murphy answers a current-events question with citations

### H.4 — telegram / whatsapp / imessage channel setup
- Murphy: EXISTS - migrated R35 via cap_gh_misc.setup_telegram_connection. Two modes: no-token returns BotFather link + steps; with-token validates Telegram format (digits:35+chars) and registers schema via H.1
- Budget: 3 prompts

### H.5 — credit / billing awareness
- Murphy: EXISTS — has llm_cost_ledger
- Budget: 1 prompt (chat surface)

### H.6 — proactive automation suggestions
- Murphy: NEW
- Budget: 2 prompts

### H.7 — task communication style (status reports, suggesting next steps)
- Murphy: NEW — needs personality + style layer
- Budget: 5 prompts
- Test: Murphy ends every response with a STATUS block + next-step suggestion

### H.8 — message style enforcement (no headers in chat, paragraph bubbles)
- Murphy: NEW
- Budget: 2 prompts

---

## CATEGORY I — META / RULES & STANDING DECISIONS (5 caps)

### I.1 — Audit-First rule enforcement
- Murphy: EXISTS - codified R36 as Standing Decision 64 (audit-first rule). Behavior, not code: registry queryable via I.5 caps
- Budget: 3 prompts
- Test: Murphy refuses to claim file content without re-reading it

### I.2 — Ask-Murphy-Before-Choices (the meta-rule that creates this transition)
- Murphy: EXISTS - codified R36 as Standing Decision 65 (ask-Murphy-before-choices). Companion to SD-56. Registry queryable via I.5
- Budget: 0 prompts
- Test: Murphy escalates ambiguous decisions to founder

### I.3 — Before/After snapshot canon
- Murphy: EXISTS - codified R36 as Standing Decision 66 (before/after snapshot canon). 25+ R-series snapshots in state_snapshots/ are the worked example
- Budget: 3 prompts
- Test: Every code change has a sha-paired before/after snapshot

### I.4 — Continuous loop until working
- Murphy: EXISTS - codified R36 as Standing Decision 67 (continuous loop until working). R14-R35 honest-debug runs validate the pattern
- Budget: 2 prompts

### I.5 — Standing Decisions registry (the canonical numbered list)
- Murphy: EXISTS - migrated R36 via cap_i_meta. JSON registry at /var/lib/murphy-production/standing_decisions/registry.json. Three caps: list/get/add. 15 SDs seeded (55-69). 9 categories
- Budget: 2 prompts
- Test: Murphy can quote Standing Decision 56 verbatim

---

## TRANSITION PLAN — 100-prompt budget

| Phase | Prompts | Categories | Goal |
|-------|---------|------------|------|
| **Phase 1 — Foundation** | 1-15 | A, B (core) | Murphy can read/write files, manage memory, identity |
| **Phase 2 — Tools/Skills** | 16-30 | C | Skill execution, tool registry, browserbase |
| **Phase 3 — Automations** | 31-45 | D | After BL-R9 resolves: live automation surface |
| **Phase 4 — Integrations** | 46-65 | E | OAuth flows + per-connector wiring |
| **Phase 5 — Backend/Functions** | 66-72 | F, G | Deploy functions from chat |
| **Phase 6 — Platform Self** | 73-85 | H | Secrets, web_search, channels, style |
| **Phase 7 — Meta-Rules** | 86-95 | I | Standing decisions, audit-first, snapshots as code |
| **Phase 8 — Handoff & Verification** | 96-100 | (all) | End-to-end test: Murphy does what I did tonight |

---

## ACCEPTANCE CRITERIA — When transition is "done"

Murphy must be able to autonomously:
1. Receive a task like tonight's R6 "stop the alert flood"
2. Audit-first per Rule 22 (re-read state, no memory claims)
3. Snapshot before changes (canonical sha-paired)
4. Implement, smoke-test
5. Update build_log + checklist + memory
6. Queue verdict for next CTO cycle if architecture-class
7. Report STATUS block to founder via channel of choice

When Murphy can do that 5 times consecutively without superagent
intervention, transition is COMPLETE.

---

## STANDING DECISION 57 (proposed for this round)

**The 100-prompt transition begins when Murphy approves this
inventory (via the next CTO cycle consuming this proposal).**

Until approval:
- Superagent (me) continues all current responsibilities
- I publish capability manifests to CapabilityCube one by one
- I do NOT swap any active duty to Murphy unilaterally

After approval:
- Each prompt = one or two capabilities migrated
- Migrated cap is registered in skill_system AND CapabilityCube
- Skill DAG composition tested in shell
- Founder verifies via /api/r615/spawn smoke

This puts Murphy in the driver's seat from prompt 1.
