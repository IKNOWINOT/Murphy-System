# Murphy System — DeepInfra → DeepInfra/Together Replacement

## Phase 1: Global sed replacements (env vars, URLs, strings) [DONE for llm_provider.py + llm_integration_layer.py]
- [x] src/llm_provider.py — NEW file (DeepInfra primary, Together fallback)
- [x] src/llm_integration_layer.py — REWRITTEN (uses MurphyLLMProvider)
- [ ] Global sed pass across ALL remaining files
  - [ ] DEEPINFRA_API_KEY → DEEPINFRA_API_KEY (env vars)
  - [ ] DEEPINFRA_API_KEYS → DEEPINFRA_API_KEYS (env vars)
  - [ ] api.deepinfra.com → api.deepinfra.com/v1/openai (base URLs)
  - [ ] deepinfra.com → deepinfra.com (misc URLs)
  - [ ] meta-llama/Meta-Llama-3.1-70B-Instruct → meta-llama/Meta-Llama-3.1-70B-Instruct (model names)
  - [ ] meta-llama/Meta-Llama-3.1-70B-Instruct → meta-llama/Meta-Llama-3.1-70B-Instruct
  - [ ] meta-llama/Meta-Llama-3.1-8B-Instruct → meta-llama/Meta-Llama-3.1-8B-Instruct
  - [ ] deepinfra → deepinfra (lowercase general references)
  - [ ] DeepInfra → DeepInfra (capitalized references)
  - [ ] DEEPINFRA → DEEPINFRA (uppercase references, except already-aliased)

## Phase 2: Targeted file rewrites (files with complex DeepInfra logic)
- [ ] src/openai_compatible_provider.py — ProviderType.DEEPINFRA → DEEPINFRA + Together
- [ ] src/groq_key_rotator.py → deepinfra_key_rotator.py (rename + rewrite)
- [ ] strategic/gap_closure/llm/multi_provider_router.py — replace DeepInfra Provider entries
- [ ] src/config.py — update provider config
- [ ] src/env_manager.py — update key names
- [ ] src/key_harvester.py — update key names
- [ ] src/secure_key_manager.py — update key names
- [ ] src/setup_wizard.py — update setup steps
- [ ] src/startup_validator.py — update validator
- [ ] src/readiness_scanner.py — update scanner
- [ ] k8s/secret.yaml — update secrets
- [ ] .env.example — update env vars
- [ ] config/murphy-production.environment.example — update env vars
- [ ] config/engines.yaml — update engine config
- [ ] tests/test_groq_integration.py → rename + rewrite
- [ ] All other test files — update assertions

## Phase 3: Wire /api/prompt endpoint to MurphyLLMProvider
- [ ] murphy_production_server.py — /api/prompt uses real LLM

## Phase 4: Commit & push
- [ ] git add all changes
- [ ] git commit
- [ ] git push feature/production-calendar-ui-wiring