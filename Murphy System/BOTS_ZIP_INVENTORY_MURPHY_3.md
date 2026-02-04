# bots.zip Inventory for Murphy 3.0

This inventory was built by directly enumerating the outer `bots.zip` at `Murphy System/bots.zip` and the nested `bots/bots.zip` contained within it. The nested archive is identical to the outer TypeScript bot package directories (same files and checksums).

## Summary

- Outer `bots.zip` contains 35 TypeScript bot packages (directories), 93 root-level Python files, plus `composite_registry.json` and a nested `bots.zip`.
- Nested `bots/bots.zip` contains the same 35 TypeScript bot packages; no additional or newer versions were detected.
- **Use for Murphy 3.0:** TypeScript bot packages + Python support utilities (non-`bot` names) are the most reusable building blocks.
- **Archive reference:** Nested `bots.zip` (duplicate) + legacy Python bot implementations (files with `bot` in the name).

## Outer bots.zip — TypeScript bot packages (recommended for Murphy 3.0)

| Bot package | Type | Murphy 3.0 usefulness |
| --- | --- | --- |
| `CRMLeadGenerator_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `analysisbot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `anomaly_watcher_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `bot_base/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `cad_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `clarifier_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `code_translator_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `commissioning_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `deduplication_refiner_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `engineering_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `feedback_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `ghost_controller_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `goldenpath_generator/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `json_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `kaia/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `key_manager_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `kiren/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `librarian_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `meeting_notes_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `memory_manager_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `multimodal_describer_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `optimization_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `optimizer_core_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `osmosis/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `plan_structurer_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `polyglot_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `research_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `rubixcube_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `scaling_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `swisskiss_loader/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `triage_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `utils/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `vallon/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `veritas/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |
| `visualization_bot/` | TypeScript bot package (schema/rollcall/tests) | **Use** (directly reusable) |

## Outer bots.zip — Python bot implementations (archive/reference)

| File | Type | Murphy 3.0 usefulness |
| --- | --- | --- |
| `Engineering_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `Ghost_Controller_Bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `analysisbot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `anomaly_watcher_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `bot_base.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `cad_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `clarifier_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `code_translator_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `coding_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `commissioning_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `comms_hub_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `deduplication_refiner_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `execution_planner_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `feedback_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `graph_architect_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `json_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `jsonbot_schema.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `key_manager_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `librarian_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `local_summarizer_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `matrix_chatbot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `memory_cortex_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `memory_manager_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `multimodal_describer_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `optimization_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `optimizer_core_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `plan_structurer_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `policy_trainer_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `polyglot_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `recursive_executor_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `rubixcube_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `scaling_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `scheduler_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `security_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `simulation_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `telemetry_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `triage_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `tuning_refiner_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `vallon_core_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `valon_prioritizer_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |
| `visualization_bot.py` | Legacy Python bot or bot runtime | **Archive** (reference for migration) |

## Outer bots.zip — Python support utilities (useful for Murphy 3.0)

| File | Type | Murphy 3.0 usefulness |
| --- | --- | --- |
| `__init__.py` | Python support module | **Use** (support utilities) |
| `aionmind_core.py` | Python support module | **Use** (support utilities) |
| `analytics.py` | Python support module | **Use** (support utilities) |
| `anomaly_detection.py` | Python support module | **Use** (support utilities) |
| `api_cache.py` | Python support module | **Use** (support utilities) |
| `async_utils.py` | Python support module | **Use** (support utilities) |
| `cache_manager.py` | Python support module | **Use** (support utilities) |
| `comment_classifier.py` | Python support module | **Use** (support utilities) |
| `composite_registry.py` | Python support module | **Use** (support utilities) |
| `config.py` | Python support module | **Use** (support utilities) |
| `config_loader.py` | Python support module | **Use** (support utilities) |
| `config_manager.py` | Python support module | **Use** (support utilities) |
| `container_runner.py` | Python support module | **Use** (support utilities) |
| `crosslinked_knowledge_index.py` | Python support module | **Use** (support utilities) |
| `crypto_utils.py` | Python support module | **Use** (support utilities) |
| `dashboard.py` | Python support module | **Use** (support utilities) |
| `dependency_graph.py` | Python support module | **Use** (support utilities) |
| `efficiency_optimizer.py` | Python support module | **Use** (support utilities) |
| `energy_logger.py` | Python support module | **Use** (support utilities) |
| `fallback.py` | Python support module | **Use** (support utilities) |
| `gpt_oss_runner.py` | Python support module | **Use** (support utilities) |
| `health_check.py` | Python support module | **Use** (support utilities) |
| `history_diff.py` | Python support module | **Use** (support utilities) |
| `hive_pipelines.py` | Python support module | **Use** (support utilities) |
| `input_parser.py` | Python support module | **Use** (support utilities) |
| `json_converter.py` | Python support module | **Use** (support utilities) |
| `json_streamed_logic.py` | Python support module | **Use** (support utilities) |
| `kiren_speak.py` | Python support module | **Use** (support utilities) |
| `llm_backend.py` | Python support module | **Use** (support utilities) |
| `logging_utils.py` | Python support module | **Use** (support utilities) |
| `matrix_client.py` | Python support module | **Use** (support utilities) |
| `memory_manager_ttl.py` | Python support module | **Use** (support utilities) |
| `message_validator.py` | Python support module | **Use** (support utilities) |
| `metrics_exporter.py` | Python support module | **Use** (support utilities) |
| `plugin_loader.py` | Python support module | **Use** (support utilities) |
| `progress.py` | Python support module | **Use** (support utilities) |
| `rcm_stability_core.py` | Python support module | **Use** (support utilities) |
| `recursion_stability.py` | Python support module | **Use** (support utilities) |
| `recursive_oversight_layer.py` | Python support module | **Use** (support utilities) |
| `rest_api.py` | Python support module | **Use** (support utilities) |
| `rl_training.py` | Python support module | **Use** (support utilities) |
| `scheduler_ui.py` | Python support module | **Use** (support utilities) |
| `simulation_sandbox.py` | Python support module | **Use** (support utilities) |
| `streaming_handler.py` | Python support module | **Use** (support utilities) |
| `swisskiss_loader.py` | Python support module | **Use** (support utilities) |
| `task_graph_executor.py` | Python support module | **Use** (support utilities) |
| `task_lifecycle.py` | Python support module | **Use** (support utilities) |
| `task_record.py` | Python support module | **Use** (support utilities) |
| `tool_dispatcher.py` | Python support module | **Use** (support utilities) |
| `valon.py` | Python support module | **Use** (support utilities) |
| `valon_engine.py` | Python support module | **Use** (support utilities) |
| `vanta_metrics.py` | Python support module | **Use** (support utilities) |

## Outer bots.zip — Other root files

| File | Type | Murphy 3.0 usefulness |
| --- | --- | --- |
| `bots.zip` | Nested archive (duplicate of TypeScript bot packages) | **Archive** (duplicate reference) |
| `composite_registry.json` | Registry/config data | **Archive** (reference for legacy Python bots) |

## Nested bots.zip (`bots/bots.zip`) inventory

Nested archive contains the same TypeScript bot packages listed above. File list and checksums match the outer directories, so it is redundant. Keep as an archive reference only.

| Bot package | Match to outer bots.zip | Murphy 3.0 usefulness |
| --- | --- | --- |
| `CRMLeadGenerator_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `analysisbot/` | Identical to outer package | **Archive** (duplicate reference) |
| `anomaly_watcher_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `bot_base/` | Identical to outer package | **Archive** (duplicate reference) |
| `cad_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `clarifier_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `code_translator_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `commissioning_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `deduplication_refiner_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `engineering_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `feedback_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `ghost_controller_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `goldenpath_generator/` | Identical to outer package | **Archive** (duplicate reference) |
| `json_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `kaia/` | Identical to outer package | **Archive** (duplicate reference) |
| `key_manager_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `kiren/` | Identical to outer package | **Archive** (duplicate reference) |
| `librarian_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `meeting_notes_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `memory_manager_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `multimodal_describer_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `optimization_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `optimizer_core_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `osmosis/` | Identical to outer package | **Archive** (duplicate reference) |
| `plan_structurer_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `polyglot_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `research_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `rubixcube_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `scaling_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `swisskiss_loader/` | Identical to outer package | **Archive** (duplicate reference) |
| `triage_bot/` | Identical to outer package | **Archive** (duplicate reference) |
| `utils/` | Identical to outer package | **Archive** (duplicate reference) |
| `vallon/` | Identical to outer package | **Archive** (duplicate reference) |
| `veritas/` | Identical to outer package | **Archive** (duplicate reference) |
| `visualization_bot/` | Identical to outer package | **Archive** (duplicate reference) |

## Archive plan (reference retention)

- **Archive:** nested `bots/bots.zip` (duplicate), plus the legacy Python bot implementations listed above. These should be retained as historical reference during any Murphy 3.0 migration.
- **Keep active:** TypeScript bot packages and Python support utilities (non-`bot` names) are the most immediately reusable assets for Murphy 3.0.