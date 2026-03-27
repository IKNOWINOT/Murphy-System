"""Modern Arcana package."""

from .config import validate_env
from .config_loader import load_config, AppConfig
from .task_record import TaskRecord
from .bot_base import AsyncBot, HiveBot, Message
from .json_bot import JSONBot
from .coding_bot import CodingBot
from .security_bot import (
    SecurityBot,
    Role,
    load_permissions,
    check_permission,
    log_activity,
    log_security_event,
    scan_for_anomalies,
    revoke_key,
)
from .triage_bot import TriageBot
from .commissioning_bot import CommissioningBot
from .task_lifecycle import TaskLifecycle
from .scheduler_bot import SchedulerBot, CircuitBreaker
from .fallback import with_fallback
from .progress import progress_bar
from .logging_utils import get_logger, LOG_LEVELS, QUIET_MODE
from .plugin_loader import load_plugin, load_plugins, reload_plugin
from .composite_registry import load_composite_bots
from .config_manager import ConfigManagerBot
from .scheduler_ui import run_scheduler_ui
try:
    from .simulation_bot import run_simulation
except Exception:  # pragma: no cover
    run_simulation = None
from .memory_manager_ttl import check_expired_stm, archive_to_ltm, deduplicate_ltm
from .rcm_stability_core import RecursiveStabilityEngine
from .metrics_exporter import start_metrics_server
from .analytics import enable as enable_analytics, track_event
from .energy_logger import log_energy, get_records
from .api_cache import cached_get
from .cache_manager import (
    get_cache,
    set_cache,
    delete_cache,
    cache_stats,
    cleanup_cache,
)
from .multimodal_describer_bot import (
    describe_input,
    describe_image_pixels,
    describe_audio_frames,
    describe_video_frames,
)
try:
    from .swisskiss_loader import SwissKissLoader
except Exception:  # pragma: no cover
    SwissKissLoader = None
try:
    from .rest_api import run_api
except Exception:  # pragma: no cover
    run_api = None

try:
    from .simulation_sandbox import simulate
except Exception:  # pragma: no cover - optional dependency
    simulate = None
try:  # optional heavy modules
    from .polyglot_bot import (
        translate,
        context_aware_translate,
        transpile_python_to_js,
        transpile_js_to_python,
    )
except Exception:  # pragma: no cover
    translate = context_aware_translate = transpile_python_to_js = transpile_js_to_python = None

try:
    from .hive_pipelines import predictive_scheduler, feedback_optimization_cycle
except Exception:  # pragma: no cover
    predictive_scheduler = feedback_optimization_cycle = None

from .container_runner import ContainerTask, run_container

try:
    from .memory_manager_bot import (
        MemoryManagerBot,
        MemoryEntry,
        adaptive_forgetting_curve,
        adaptive_decay,
    )
except Exception:  # pragma: no cover
    MemoryManagerBot = MemoryEntry = adaptive_forgetting_curve = adaptive_decay = None

try:
    from .optimization_bot import (
        reinforcement_learning_loop,
        run_optimization,
        close_feedback_issues,
    )
    from ..optimization_cycle import run_cycle as run_optimization_cycle
except Exception:  # pragma: no cover
    reinforcement_learning_loop = run_optimization = close_feedback_issues = None
    run_optimization_cycle = None


try:
    from .feedback_bot import FeedbackBot
except Exception:  # pragma: no cover
    FeedbackBot = None

try:
    from .valon import Plan, prioritize, Prioritizer, ml_prioritize
except Exception:  # pragma: no cover
    Plan = prioritize = Prioritizer = ml_prioritize = None

try:
    from .efficiency_optimizer import generate_subtasks, optimize_per_bot_type
except Exception:  # pragma: no cover
    generate_subtasks = optimize_per_bot_type = None

try:
    from .dependency_graph import DependencyGraph
except Exception:  # pragma: no cover
    DependencyGraph = None

try:
    from .anomaly_detection import detect_anomalies, ewma_control
except Exception:  # pragma: no cover
    detect_anomalies = ewma_control = None

try:
    from .vanta_metrics import compute_roc, adjust_vanta_params
except Exception:  # pragma: no cover
    compute_roc = adjust_vanta_params = None

try:
    from .llm_backend import LLMBackend, generate_text
except Exception:  # pragma: no cover
    LLMBackend = generate_text = None

try:
    from .kiren_speak import KirenSpeak, generate_response
except Exception:  # pragma: no cover
    KirenSpeak = generate_response = None

try:
    from .librarian_bot import LibrarianBot, Document
except Exception:  # pragma: no cover
    LibrarianBot = Document = None

try:
    from .crosslinked_knowledge_index import CrosslinkedKnowledgeIndex, KnowledgeNode
except Exception:  # pragma: no cover
    CrosslinkedKnowledgeIndex = KnowledgeNode = None

try:
    from .visualization_bot import VisualizationBot
    from .telemetry_bot import TelemetryBot
    from .recursion_stability import StabilityMetrics
except Exception:  # pragma: no cover
    VisualizationBot = TelemetryBot = None

try:
    from .utils.fuzzy_prompt import best_match, clarify_prompt
except Exception:  # pragma: no cover
    best_match = clarify_prompt = None

try:
    from .history_diff import get_diff, MemoryVersion
except Exception:  # pragma: no cover
    get_diff = MemoryVersion = None

try:
    from .health_check import HealthChecker
except Exception:  # pragma: no cover
    HealthChecker = None

try:
    from .clarifier_bot import ClarifierBot, PromptRefinerBot
except Exception:  # pragma: no cover
    ClarifierBot = PromptRefinerBot = None

try:
    from .valon_prioritizer_bot import ValonPrioritizerBot, PriorityTrainerBot
except Exception:  # pragma: no cover
    ValonPrioritizerBot = PriorityTrainerBot = None

try:
    from .anomaly_watcher_bot import AnomalyWatcherBot, ThresholdRefinerBot
except Exception:  # pragma: no cover
    AnomalyWatcherBot = ThresholdRefinerBot = None

try:
    from .code_translator_bot import CodeTranslatorBot
    from .comment_classifier import classify_line
except Exception:  # pragma: no cover
    CodeTranslatorBot = None
    classify_line = None

try:
    from .message_validator import MessageValidatorBot
except Exception:  # pragma: no cover
    MessageValidatorBot = None

try:
    from .rubixcube_bot import visualize_quantum, log_usage, forecast_scaling
except Exception:  # pragma: no cover
    visualize_quantum = log_usage = forecast_scaling = None

try:
    from .memory_cortex_bot import MemoryCortexBot
except Exception:  # pragma: no cover
    MemoryCortexBot = None

try:
    from .valon_engine import ValonEngine
except Exception:  # pragma: no cover
    ValonEngine = None

try:
    from .tool_dispatcher import dispatch
    from .json_converter import parse_user_input_to_json
    from .aionmind_core import handle_user_query
    from .json_bot import handle_validated_task
except Exception:  # pragma: no cover
    dispatch = parse_user_input_to_json = handle_user_query = handle_validated_task = None

try:
    from .streaming_handler import StreamingInputHandler, async_json_echo
except Exception:  # pragma: no cover
    StreamingInputHandler = async_json_echo = None

try:
    from .optimizer_core_bot import OptimizerCoreBot
except Exception:  # pragma: no cover
    OptimizerCoreBot = None

try:
    from .vallon_core_bot import VallonCoreBot
except Exception:  # pragma: no cover
    VallonCoreBot = None

try:
    from .recursive_oversight_layer import RecursiveOversightLayer
except Exception:  # pragma: no cover
    RecursiveOversightLayer = None

try:
    from .comms_hub_bot import CommsHubBot
except Exception:  # pragma: no cover
    CommsHubBot = None

try:
    from .dashboard import run_dashboard
except Exception:  # pragma: no cover
    run_dashboard = None

try:
    from .async_utils import fetch_with_timeout
except Exception:  # pragma: no cover
    fetch_with_timeout = None

try:
    from .scaling_bot import ScalingBot
except Exception:  # pragma: no cover
    ScalingBot = None

try:
    from .graph_architect_bot import GraphArchitectBot
    from .execution_planner_bot import ExecutionPlannerBot
except Exception:  # pragma: no cover
    GraphArchitectBot = ExecutionPlannerBot = None

try:
    from .plan_structurer_bot import PlanStructurerBot, SubPlan
    from .recursive_executor_bot import RecursiveExecutorBot
except Exception:  # pragma: no cover
    PlanStructurerBot = SubPlan = RecursiveExecutorBot = None

try:
    from .local_summarizer_bot import LocalSummarizerBot, SummaryEvaluatorBot
except Exception:  # pragma: no cover
    LocalSummarizerBot = SummaryEvaluatorBot = None

try:
    from .tuning_refiner_bot import TuningRefinerBot
    from .policy_trainer_bot import PolicyTrainerBot
except Exception:  # pragma: no cover
    TuningRefinerBot = PolicyTrainerBot = None

try:
    from .deduplication_refiner_bot import DeduplicationRefinerBot, EntryMergerBot
except Exception:  # pragma: no cover
    DeduplicationRefinerBot = EntryMergerBot = None

try:
    from .matrix_chatbot import MatrixChatBot
    from .matrix_client import MatrixClient
    from .key_manager_bot import KeyManagerBot
    from .crypto_utils import (
        sign_message,
        verify_signature,
        encrypt_payload,
        decrypt_payload,
    )
except Exception:  # pragma: no cover
    MatrixChatBot = MatrixClient = KeyManagerBot = None
    sign_message = verify_signature = encrypt_payload = decrypt_payload = None

try:
    from .matrix_config import MatrixConfig, load_config as load_matrix_config, MatrixBotConfig
    from .matrix_formatters import (
        format_status,
        format_overview,
        format_error,
        format_success,
        format_links,
        format_jargon,
        format_jargon_list,
        format_help,
        format_email_result,
        format_notification_result,
        format_webhook_delivery,
        format_connector_status,
        format_comms_activity_feed,
        format_integration_status,
        format_service_ticket,
        get_all_jargon,
    )
    from .matrix_bot import MurphyMatrixBot, MurphyAPIBridge, MurphyAPIClient
    from .matrix_hitl import HITLBridge
    from .matrix_notifications import HealthMonitor
except Exception:  # pragma: no cover
    MatrixConfig = load_matrix_config = MatrixBotConfig = None
    MurphyMatrixBot = MurphyAPIBridge = MurphyAPIClient = HITLBridge = HealthMonitor = None
    format_status = format_overview = format_error = format_success = None
    format_links = format_jargon = format_jargon_list = format_help = None
    format_email_result = format_notification_result = format_webhook_delivery = None
    format_connector_status = format_comms_activity_feed = None
    format_integration_status = format_service_ticket = get_all_jargon = None

try:
    from .utils.typed_event import HiveEvent
except Exception:  # pragma: no cover
    HiveEvent = None

__all__ = [
    'translate',
    'context_aware_translate',
    'transpile_python_to_js',
    'transpile_js_to_python',
    'MemoryManagerBot',
    'MemoryEntry',
    'adaptive_forgetting_curve',
    'adaptive_decay',
    'reinforcement_learning_loop',
    'FeedbackBot',
    'LLMBackend',
    'generate_text',
    'best_match',
    'clarify_prompt',
    'Plan',
    'prioritize',
    'Prioritizer',
    'ml_prioritize',
    'generate_subtasks',
    'optimize_per_bot_type',
    'DependencyGraph',
    'detect_anomalies',
    'ewma_control',
    'HealthChecker',
    'ClarifierBot',
    'PromptRefinerBot',
    'ValonPrioritizerBot',
    'PriorityTrainerBot',
    'AnomalyWatcherBot',
    'ThresholdRefinerBot',
    'CodeTranslatorBot',
    'classify_line',
    'validate_env',
    'JSONBot',
    'CodingBot',
    'TriageBot',
    'SchedulerBot',
    'CircuitBreaker',
    'with_fallback',
    'SecurityBot',
    'Role',
    'LibrarianBot',
    'Document',
    'CrosslinkedKnowledgeIndex',
    'KnowledgeNode',
    'visualize_quantum',
    'log_usage',
    'forecast_scaling',
    'run_dashboard',
    'ScalingBot',
    'fetch_with_timeout',
    'MatrixChatBot',
    'MatrixClient',
    'KeyManagerBot',
    'sign_message',
    'verify_signature',
    'encrypt_payload',
    'decrypt_payload',
    'progress_bar',
    'get_logger',
    'LOG_LEVELS',
    'QUIET_MODE',
    'load_plugin',
    'load_plugins',
    'reload_plugin',
    'load_composite_bots',
    'ConfigManagerBot',
    'run_scheduler_ui',
    'simulate',
    'ContainerTask',
    'run_container',
    'load_config',
    'AppConfig',
    'TaskRecord',
    'SwissKissLoader',
    'AsyncBot',
    'HiveBot',
    'Message',
    'HiveEvent',
    'compute_roc',
    'adjust_vanta_params',
    'get_diff',
    'MemoryVersion',
    'GraphArchitectBot',
    'ExecutionPlannerBot',
    'SubPlan',
    'PlanStructurerBot',
    'RecursiveExecutorBot',
    'LocalSummarizerBot',
    'SummaryEvaluatorBot',
    'TuningRefinerBot',
    'PolicyTrainerBot',
    'DeduplicationRefinerBot',
    'EntryMergerBot',
    'run_api',
    'start_metrics_server',
    'enable_analytics',
    'track_event',
    'log_energy',
    'get_records',
    'VisualizationBot',
    'TelemetryBot',
    'cached_get',
    'MemoryCortexBot',
    'ValonEngine',
    'OptimizerCoreBot',
    'VallonCoreBot',
    'CommsHubBot',
    'TaskGraphExecutor',
    'StreamingInputHandler',
    'async_json_echo',
    'JSONStreamedLogicIngestor',
    'RecursiveOversightLayer',
    'predictive_scheduler',
    'feedback_optimization_cycle',
    'run_optimization_cycle',
    "StabilityMetrics",
    'load_permissions',
    'check_permission',
    'log_activity',
    'log_security_event',
    'scan_for_anomalies',
    'revoke_key',
    'dispatch',
    'handle_validated_task',
    'parse_user_input_to_json',
    'handle_user_query',
    # Matrix bot integration
    'MatrixConfig',
    'load_matrix_config',
    'MatrixBot',
    'MurphyAPIClient',
    'HITLBridge',
    'NotificationRelay',
    'format_status',
    'format_overview',
    'format_error',
    'format_success',
    'format_links',
    'format_jargon',
    'format_jargon_list',
    'format_help',
    'format_email_result',
    'format_notification_result',
    'format_webhook_delivery',
    'format_connector_status',
    'format_comms_activity_feed',
    'format_integration_status',
    'format_service_ticket',
    'get_all_jargon',
]
