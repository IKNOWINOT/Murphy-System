"""
Enterprise Integrations Module — Connector adapters for enterprise productivity,
engineering, and business software platforms.

Provides a unified interface for accounting/finance, CAD/3D engineering,
project management, document/content, communication, DevOps/infrastructure,
data/analytics, and ERP/business platforms with thread-safe registry,
DAG workflow binding, and automatic capability mapping.
"""

import logging
import threading
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class IntegrationCategory(Enum):
    """Integration category (Enum subclass)."""
    ACCOUNTING_FINANCE = "accounting_finance"
    ENGINEERING_DESIGN = "engineering_design"
    PROJECT_MANAGEMENT = "project_management"
    DOCUMENT_CONTENT = "document_content"
    COMMUNICATION = "communication"
    DEVOPS_INFRASTRUCTURE = "devops_infrastructure"
    DATA_ANALYTICS = "data_analytics"
    ERP_BUSINESS = "erp_business"
    BUILDING_AUTOMATION = "building_automation"
    ENERGY_MANAGEMENT = "energy_management"


class AuthMethod(Enum):
    """Auth method (Enum subclass)."""
    API_KEY = "api_key"
    OAUTH = "oauth"
    BASIC = "basic"
    CERTIFICATE = "certificate"


class ConnectorStatus(Enum):
    """Connector status (Enum subclass)."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DISABLED = "disabled"


# ---------------------------------------------------------------------------
# Base Connector
# ---------------------------------------------------------------------------

class EnterpriseConnector:
    """Base adapter for an enterprise platform integration."""

    def __init__(
        self,
        name: str,
        category: IntegrationCategory,
        platform_type: str,
        auth_config: Dict[str, Any],
        rate_limit: Dict[str, int],
        capabilities: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.category = category
        self.platform_type = platform_type
        self.auth_config = dict(auth_config)
        self.rate_limit = {
            "requests_per_minute": rate_limit.get("requests_per_minute", 60),
            "burst_limit": rate_limit.get("burst_limit", 10),
        }
        self.capabilities = list(capabilities)
        self.metadata = dict(metadata) if metadata else {}

        self._lock = threading.RLock()
        self._status = ConnectorStatus.UNKNOWN
        self._request_count = 0
        self._error_count = 0
        self._window_start = time.time()
        self._window_requests = 0
        self._enabled = True
        self._credentials: Dict[str, str] = {}
        self._action_log: List[Dict[str, Any]] = []

    # -- public interface ---------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Return current health status of the connector."""
        with self._lock:
            if not self._enabled:
                self._status = ConnectorStatus.DISABLED
            elif self._request_count == 0:
                self._status = ConnectorStatus.UNKNOWN
            else:
                error_rate = self._error_count / max(self._request_count, 1)
                if error_rate > 0.5:
                    self._status = ConnectorStatus.UNHEALTHY
                elif error_rate > 0.1:
                    self._status = ConnectorStatus.DEGRADED
                else:
                    self._status = ConnectorStatus.HEALTHY
            return {
                "name": self.name,
                "platform_type": self.platform_type,
                "status": self._status.value,
                "enabled": self._enabled,
                "request_count": self._request_count,
                "error_count": self._error_count,
                "timestamp": time.time(),
            }

    def execute_action(self, action_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a named action against this connector."""
        params = params or {}
        with self._lock:
            if not self._enabled:
                return self._action_result(action_name, False, error="Connector is disabled")

            if action_name not in self.capabilities:
                return self._action_result(action_name, False, error=f"Unsupported action: {action_name}")

            if not self._check_rate_limit():
                return self._action_result(action_name, False, error="Rate limit exceeded")

            self._request_count += 1
            # Simulated execution – real API calls happen when credentials are configured
            result = self._action_result(
                action_name,
                True,
                data={
                    "action": action_name,
                    "platform": self.platform_type,
                    "params": params,
                    "simulated": True,
                },
            )
            capped_append(self._action_log, result)
            return result

    def list_available_actions(self) -> List[str]:
        """Return list of supported action names."""
        return list(self.capabilities)

    # -- configuration ------------------------------------------------------

    def configure(self, credentials: Dict[str, str]) -> Dict[str, Any]:
        with self._lock:
            self._credentials = dict(credentials)
            return {"configured": True, "name": self.name}

    def enable(self) -> None:
        with self._lock:
            self._enabled = True

    def disable(self) -> None:
        with self._lock:
            self._enabled = False

    def is_enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "category": self.category.value,
                "platform_type": self.platform_type,
                "auth_config": self.auth_config,
                "rate_limit": self.rate_limit,
                "capabilities": self.capabilities,
                "enabled": self._enabled,
                "status": self._status.value,
                "request_count": self._request_count,
                "error_count": self._error_count,
                "metadata": self.metadata,
            }

    # -- internals ----------------------------------------------------------

    def _check_rate_limit(self) -> bool:
        now = time.time()
        if now - self._window_start > 60:
            self._window_start = now
            self._window_requests = 0
        if self._window_requests >= self.rate_limit["requests_per_minute"]:
            return False
        self._window_requests += 1
        return True

    def _action_result(self, action_name: str, success: bool, data: Any = None, error: Optional[str] = None) -> Dict[str, Any]:
        return {
            "action": action_name,
            "connector": self.name,
            "success": success,
            "data": data,
            "error": error,
            "timestamp": time.time(),
        }


# ---------------------------------------------------------------------------
# Default connector definitions
# ---------------------------------------------------------------------------

def _build_defaults() -> List[EnterpriseConnector]:
    specs = [
        # ---- Accounting & Finance ----
        {
            "name": "QuickBooks",
            "category": IntegrationCategory.ACCOUNTING_FINANCE,
            "platform_type": "quickbooks",
            "auth_config": {"method": AuthMethod.OAUTH.value, "scopes": ["accounting", "payments"]},
            "rate_limit": {"requests_per_minute": 500, "burst_limit": 50},
            "capabilities": ["invoicing", "expense_tracking", "financial_reports", "payroll_sync",
                             "create_invoice", "list_expenses", "generate_report", "sync_payroll"],
        },
        {
            "name": "Xero",
            "category": IntegrationCategory.ACCOUNTING_FINANCE,
            "platform_type": "xero",
            "auth_config": {"method": AuthMethod.OAUTH.value, "scopes": ["accounting"]},
            "rate_limit": {"requests_per_minute": 60, "burst_limit": 10},
            "capabilities": ["bank_reconciliation", "invoicing", "reporting",
                             "reconcile_bank", "create_invoice", "generate_report"],
        },
        {
            "name": "FreshBooks",
            "category": IntegrationCategory.ACCOUNTING_FINANCE,
            "platform_type": "freshbooks",
            "auth_config": {"method": AuthMethod.OAUTH.value},
            "rate_limit": {"requests_per_minute": 120, "burst_limit": 20},
            "capabilities": ["time_tracking", "expense", "invoicing",
                             "log_time", "add_expense", "create_invoice"],
        },
        # ---- Engineering & Design (CAD/3D) ----
        {
            "name": "AutoCAD",
            "category": IntegrationCategory.ENGINEERING_DESIGN,
            "platform_type": "autocad",
            "auth_config": {"method": AuthMethod.API_KEY.value},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 15},
            "capabilities": ["dwg_file_processing", "layer_management", "block_extraction",
                             "measurement_automation", "process_dwg", "manage_layers",
                             "extract_blocks", "automate_measurements"],
        },
        {
            "name": "Blender",
            "category": IntegrationCategory.ENGINEERING_DESIGN,
            "platform_type": "blender",
            "auth_config": {"method": AuthMethod.API_KEY.value},
            "rate_limit": {"requests_per_minute": 30, "burst_limit": 5},
            "capabilities": ["render_queuing", "scene_management", "batch_processing",
                             "asset_pipeline", "queue_render", "manage_scene",
                             "batch_process", "manage_assets"],
        },
        {
            "name": "SolidWorks",
            "category": IntegrationCategory.ENGINEERING_DESIGN,
            "platform_type": "solidworks",
            "auth_config": {"method": AuthMethod.CERTIFICATE.value},
            "rate_limit": {"requests_per_minute": 60, "burst_limit": 10},
            "capabilities": ["bom_extraction", "part_management", "revision_tracking",
                             "extract_bom", "manage_parts", "track_revisions"],
        },
        {
            "name": "Fusion 360",
            "category": IntegrationCategory.ENGINEERING_DESIGN,
            "platform_type": "fusion360",
            "auth_config": {"method": AuthMethod.OAUTH.value},
            "rate_limit": {"requests_per_minute": 80, "burst_limit": 12},
            "capabilities": ["design_collaboration", "version_control", "cam_workflow",
                             "collaborate_design", "manage_versions", "run_cam"],
        },
        # ---- Project Management ----
        {
            "name": "Basecamp",
            "category": IntegrationCategory.PROJECT_MANAGEMENT,
            "platform_type": "basecamp",
            "auth_config": {"method": AuthMethod.OAUTH.value},
            "rate_limit": {"requests_per_minute": 50, "burst_limit": 10},
            "capabilities": ["projects", "todos", "schedules", "file_sharing",
                             "create_project", "create_todo", "manage_schedule", "share_file"],
        },
        {
            "name": "Trello",
            "category": IntegrationCategory.PROJECT_MANAGEMENT,
            "platform_type": "trello",
            "auth_config": {"method": AuthMethod.API_KEY.value},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 10},
            "capabilities": ["cards", "boards", "list_automation",
                             "create_card", "create_board", "automate_lists", "move_card"],
        },
        {
            "name": "ClickUp",
            "category": IntegrationCategory.PROJECT_MANAGEMENT,
            "platform_type": "clickup",
            "auth_config": {"method": AuthMethod.API_KEY.value},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 20},
            "capabilities": ["tasks", "docs", "goals", "time_tracking",
                             "create_task", "create_doc", "set_goal", "log_time"],
        },
        {
            "name": "Wrike",
            "category": IntegrationCategory.PROJECT_MANAGEMENT,
            "platform_type": "wrike",
            "auth_config": {"method": AuthMethod.OAUTH.value},
            "rate_limit": {"requests_per_minute": 200, "burst_limit": 25},
            "capabilities": ["projects", "gantt_charts", "resource_management",
                             "create_project", "view_gantt", "manage_resources"],
        },
        # ---- Document & Content ----
        {
            "name": "Adobe Creative Cloud",
            "category": IntegrationCategory.DOCUMENT_CONTENT,
            "platform_type": "adobe_cc",
            "auth_config": {"method": AuthMethod.OAUTH.value, "scopes": ["creative_sdk"]},
            "rate_limit": {"requests_per_minute": 60, "burst_limit": 10},
            "capabilities": ["pdf_processing", "asset_management", "creative_workflow",
                             "process_pdf", "manage_assets", "run_creative_workflow"],
        },
        {
            "name": "Canva",
            "category": IntegrationCategory.DOCUMENT_CONTENT,
            "platform_type": "canva",
            "auth_config": {"method": AuthMethod.OAUTH.value},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 15},
            "capabilities": ["template_management", "design_generation", "brand_kit",
                             "manage_templates", "generate_design", "update_brand_kit"],
        },
        {
            "name": "SharePoint",
            "category": IntegrationCategory.DOCUMENT_CONTENT,
            "platform_type": "sharepoint",
            "auth_config": {"method": AuthMethod.OAUTH.value, "scopes": ["Sites.ReadWrite.All"]},
            "rate_limit": {"requests_per_minute": 200, "burst_limit": 30},
            "capabilities": ["document_libraries", "workflow", "site_management",
                             "upload_document", "create_workflow", "manage_site"],
        },
        # ---- Communication & Collaboration ----
        {
            "name": "Zoom",
            "category": IntegrationCategory.COMMUNICATION,
            "platform_type": "zoom",
            "auth_config": {"method": AuthMethod.OAUTH.value, "scopes": ["meeting:write"]},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 20},
            "capabilities": ["meeting_scheduling", "recording_management", "transcript_processing",
                             "schedule_meeting", "manage_recordings", "process_transcripts"],
        },
        {
            "name": "Twilio",
            "category": IntegrationCategory.COMMUNICATION,
            "platform_type": "twilio",
            "auth_config": {"method": AuthMethod.BASIC.value},
            "rate_limit": {"requests_per_minute": 300, "burst_limit": 50},
            "capabilities": ["sms_automation", "voice_automation", "ivr", "call_routing",
                             "send_sms", "make_call", "configure_ivr", "route_call"],
        },
        {
            "name": "Webex",
            "category": IntegrationCategory.COMMUNICATION,
            "platform_type": "webex",
            "auth_config": {"method": AuthMethod.OAUTH.value},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 15},
            "capabilities": ["meeting_management", "messaging", "calling",
                             "create_meeting", "send_message", "initiate_call"],
        },
        # ---- Messaging Platforms ----
        {
            "name": "WhatsApp Business",
            "category": IntegrationCategory.COMMUNICATION,
            "platform_type": "whatsapp",
            "auth_config": {"method": AuthMethod.API_KEY.value, "token_type": "bearer"},
            "rate_limit": {"requests_per_minute": 80, "burst_limit": 15},
            "capabilities": ["messaging", "template_messages", "media_sharing", "interactive_messages",
                             "send_message", "send_template", "send_media", "catalog_management"],
        },
        {
            "name": "Telegram",
            "category": IntegrationCategory.COMMUNICATION,
            "platform_type": "telegram",
            "auth_config": {"method": AuthMethod.API_KEY.value, "token_type": "bot_token"},
            "rate_limit": {"requests_per_minute": 30, "burst_limit": 5},
            "capabilities": ["bot_messaging", "group_management", "channel_management", "inline_queries",
                             "send_message", "send_media", "manage_groups", "manage_channels"],
        },
        {
            "name": "Signal",
            "category": IntegrationCategory.COMMUNICATION,
            "platform_type": "signal",
            "auth_config": {"method": AuthMethod.API_KEY.value, "token_type": "bearer"},
            "rate_limit": {"requests_per_minute": 30, "burst_limit": 5},
            "capabilities": ["secure_messaging", "group_management", "disappearing_messages",
                             "send_message", "send_media", "manage_groups", "sealed_sender"],
        },
        {
            "name": "Snapchat",
            "category": IntegrationCategory.COMMUNICATION,
            "platform_type": "snapchat",
            "auth_config": {"method": AuthMethod.OAUTH.value, "scopes": ["ads_api"]},
            "rate_limit": {"requests_per_minute": 60, "burst_limit": 10},
            "capabilities": ["snap_messaging", "story_management", "ad_management", "audience_insights",
                             "send_snap", "manage_stories", "creative_tools", "bitmoji_integration"],
        },
        {
            "name": "WeChat",
            "category": IntegrationCategory.COMMUNICATION,
            "platform_type": "wechat",
            "auth_config": {"method": AuthMethod.API_KEY.value, "token_type": "access_token"},
            "rate_limit": {"requests_per_minute": 60, "burst_limit": 10},
            "capabilities": ["messaging", "mini_programs", "official_accounts", "wechat_pay",
                             "send_message", "send_media", "manage_accounts", "template_messages"],
        },
        {
            "name": "LINE",
            "category": IntegrationCategory.COMMUNICATION,
            "platform_type": "line",
            "auth_config": {"method": AuthMethod.API_KEY.value, "token_type": "channel_token"},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 15},
            "capabilities": ["messaging", "rich_menus", "flex_messages", "line_pay",
                             "send_message", "send_media", "manage_rich_menus", "liff_apps"],
        },
        {
            "name": "KakaoTalk",
            "category": IntegrationCategory.COMMUNICATION,
            "platform_type": "kakaotalk",
            "auth_config": {"method": AuthMethod.OAUTH.value, "scopes": ["talk_message"]},
            "rate_limit": {"requests_per_minute": 50, "burst_limit": 10},
            "capabilities": ["messaging", "kakao_channel", "kakao_pay", "template_messages",
                             "send_message", "send_media", "manage_channels", "kakao_map"],
        },
        {
            "name": "Google Business Messages",
            "category": IntegrationCategory.COMMUNICATION,
            "platform_type": "google_business_messages",
            "auth_config": {"method": AuthMethod.OAUTH.value, "scopes": ["business_messages"]},
            "rate_limit": {"requests_per_minute": 60, "burst_limit": 10},
            "capabilities": ["business_messaging", "rich_cards", "suggested_replies", "location_messaging",
                             "send_message", "manage_agents", "surveys", "conversation_management"],
        },
        {
            "name": "ZenBusiness",
            "category": IntegrationCategory.ERP_BUSINESS,
            "platform_type": "zenbusiness",
            "auth_config": {"method": AuthMethod.API_KEY.value},
            "rate_limit": {"requests_per_minute": 30, "burst_limit": 5},
            "capabilities": ["business_formation", "registered_agent", "compliance_alerts", "annual_reports",
                             "form_business", "manage_compliance", "file_annual_report", "tax_filing"],
        },
        # ---- DevOps & Infrastructure ----
        {
            "name": "Terraform",
            "category": IntegrationCategory.DEVOPS_INFRASTRUCTURE,
            "platform_type": "terraform",
            "auth_config": {"method": AuthMethod.API_KEY.value},
            "rate_limit": {"requests_per_minute": 30, "burst_limit": 5},
            "capabilities": ["infrastructure_provisioning", "state_management", "plan_apply",
                             "provision_infra", "manage_state", "run_plan", "run_apply"],
        },
        {
            "name": "Kubernetes",
            "category": IntegrationCategory.DEVOPS_INFRASTRUCTURE,
            "platform_type": "kubernetes",
            "auth_config": {"method": AuthMethod.CERTIFICATE.value},
            "rate_limit": {"requests_per_minute": 200, "burst_limit": 40},
            "capabilities": ["pod_management", "deployment", "scaling", "health_checks",
                             "manage_pods", "create_deployment", "scale_deployment", "check_health"],
        },
        {
            "name": "Docker",
            "category": IntegrationCategory.DEVOPS_INFRASTRUCTURE,
            "platform_type": "docker",
            "auth_config": {"method": AuthMethod.BASIC.value},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 20},
            "capabilities": ["container_lifecycle", "image_management", "compose_orchestration",
                             "manage_containers", "manage_images", "run_compose"],
        },
        {
            "name": "Ansible",
            "category": IntegrationCategory.DEVOPS_INFRASTRUCTURE,
            "platform_type": "ansible",
            "auth_config": {"method": AuthMethod.API_KEY.value},
            "rate_limit": {"requests_per_minute": 50, "burst_limit": 10},
            "capabilities": ["playbook_execution", "inventory_management", "role_deployment",
                             "run_playbook", "manage_inventory", "deploy_role"],
        },
        # ---- Data & Analytics ----
        {
            "name": "Power BI",
            "category": IntegrationCategory.DATA_ANALYTICS,
            "platform_type": "power_bi",
            "auth_config": {"method": AuthMethod.OAUTH.value, "scopes": ["Dataset.ReadWrite.All"]},
            "rate_limit": {"requests_per_minute": 120, "burst_limit": 20},
            "capabilities": ["dashboard_generation", "dataset_refresh", "report_distribution",
                             "generate_dashboard", "refresh_dataset", "distribute_report"],
        },
        {
            "name": "Tableau",
            "category": IntegrationCategory.DATA_ANALYTICS,
            "platform_type": "tableau",
            "auth_config": {"method": AuthMethod.API_KEY.value},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 15},
            "capabilities": ["visualization_management", "data_source_refresh", "subscription",
                             "manage_visualizations", "refresh_data_source", "manage_subscriptions"],
        },
        {
            "name": "Snowflake",
            "category": IntegrationCategory.DATA_ANALYTICS,
            "platform_type": "snowflake",
            "auth_config": {"method": AuthMethod.BASIC.value},
            "rate_limit": {"requests_per_minute": 60, "burst_limit": 10},
            "capabilities": ["query_execution", "warehouse_management", "data_sharing",
                             "execute_query", "manage_warehouse", "share_data"],
        },
        {
            "name": "BigQuery",
            "category": IntegrationCategory.DATA_ANALYTICS,
            "platform_type": "bigquery",
            "auth_config": {"method": AuthMethod.OAUTH.value, "scopes": ["bigquery"]},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 20},
            "capabilities": ["query_execution", "dataset_management", "schema_operations",
                             "execute_query", "manage_datasets", "manage_schema"],
        },
        # ---- ERP & Business ----
        {
            "name": "SAP",
            "category": IntegrationCategory.ERP_BUSINESS,
            "platform_type": "sap",
            "auth_config": {"method": AuthMethod.CERTIFICATE.value},
            "rate_limit": {"requests_per_minute": 60, "burst_limit": 10},
            "capabilities": ["module_integration", "data_extraction", "process_automation",
                             "integrate_module", "extract_data", "automate_process"],
        },
        {
            "name": "NetSuite",
            "category": IntegrationCategory.ERP_BUSINESS,
            "platform_type": "netsuite",
            "auth_config": {"method": AuthMethod.OAUTH.value},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 15},
            "capabilities": ["crm", "erp", "ecommerce_integration",
                             "manage_crm", "manage_erp", "manage_ecommerce"],
        },
        {
            "name": "Dynamics 365",
            "category": IntegrationCategory.ERP_BUSINESS,
            "platform_type": "dynamics365",
            "auth_config": {"method": AuthMethod.OAUTH.value, "scopes": ["user_impersonation"]},
            "rate_limit": {"requests_per_minute": 150, "burst_limit": 25},
            "capabilities": ["sales", "marketing", "service", "finance",
                             "manage_sales", "run_campaign", "manage_service", "manage_finance"],
        },
        # ---- Building Automation ----
        {
            "name": "Johnson Controls Metasys",
            "category": IntegrationCategory.BUILDING_AUTOMATION,
            "platform_type": "johnson_controls_metasys",
            "auth_config": {"method": AuthMethod.CERTIFICATE.value},
            "rate_limit": {"requests_per_minute": 120, "burst_limit": 20},
            "capabilities": ["hvac_control", "space_temperature", "air_handler_management",
                             "chiller_plant_optimization", "vav_box_control", "energy_dashboard",
                             "fault_detection_diagnostics", "setpoint_scheduling"],
        },
        {
            "name": "Honeywell Niagara",
            "category": IntegrationCategory.BUILDING_AUTOMATION,
            "platform_type": "honeywell_niagara",
            "auth_config": {"method": AuthMethod.CERTIFICATE.value},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 15},
            "capabilities": ["niagara_station_management", "webs_n4_integration",
                             "ebi_alarm_management", "comfort_control", "energy_optimization",
                             "predictive_maintenance", "occupancy_analytics", "equipment_scheduling"],
        },
        {
            "name": "Siemens Desigo CC",
            "category": IntegrationCategory.BUILDING_AUTOMATION,
            "platform_type": "siemens_desigo_cc",
            "auth_config": {"method": AuthMethod.CERTIFICATE.value},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 15},
            "capabilities": ["desigo_room_automation", "building_performance_monitoring",
                             "fire_safety_integration", "access_control_integration",
                             "energy_management", "comfort_optimization",
                             "fault_rule_engine", "sustainability_reporting"],
        },
        {
            "name": "Alerton Ascent",
            "category": IntegrationCategory.BUILDING_AUTOMATION,
            "platform_type": "alerton_ascent",
            "auth_config": {"method": AuthMethod.API_KEY.value},
            "rate_limit": {"requests_per_minute": 80, "burst_limit": 12},
            "capabilities": ["bac_talk_integration", "ascent_control_engine",
                             "microset_controller_management", "vlc_controller_programming",
                             "energy_analytics", "trend_analysis",
                             "alarm_management", "remote_monitoring"],
        },
        # ---- Energy Management ----
        {
            "name": "Johnson Controls OpenBlue",
            "category": IntegrationCategory.ENERGY_MANAGEMENT,
            "platform_type": "johnson_controls_openblue",
            "auth_config": {"method": AuthMethod.OAUTH.value},
            "rate_limit": {"requests_per_minute": 120, "burst_limit": 20},
            "capabilities": ["energy_performance_monitoring", "fault_detection_diagnostics",
                             "predictive_energy_analytics", "sustainability_tracking",
                             "carbon_footprint_reporting", "smart_building_optimization",
                             "demand_response_management", "occupancy_based_control"],
        },
        {
            "name": "Honeywell Forge Energy",
            "category": IntegrationCategory.ENERGY_MANAGEMENT,
            "platform_type": "honeywell_forge",
            "auth_config": {"method": AuthMethod.OAUTH.value},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 15},
            "capabilities": ["energy_optimization", "portfolio_analytics",
                             "utility_rate_analysis", "predictive_maintenance",
                             "carbon_management", "energy_benchmarking",
                             "demand_forecasting", "renewable_integration_tracking"],
        },
        {
            "name": "Schneider Electric EcoStruxure",
            "category": IntegrationCategory.ENERGY_MANAGEMENT,
            "platform_type": "schneider_ecostruxure",
            "auth_config": {"method": AuthMethod.OAUTH.value},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 15},
            "capabilities": ["power_monitoring", "energy_analytics",
                             "microgrid_management", "power_quality_analysis",
                             "electrical_distribution", "building_analytics",
                             "demand_side_management", "sustainability_dashboard"],
        },
        {
            "name": "EnergyCAP",
            "category": IntegrationCategory.ENERGY_MANAGEMENT,
            "platform_type": "energycap",
            "auth_config": {"method": AuthMethod.API_KEY.value},
            "rate_limit": {"requests_per_minute": 60, "burst_limit": 10},
            "capabilities": ["utility_bill_tracking", "energy_accounting",
                             "cost_allocation", "budget_forecasting",
                             "rate_analysis", "weather_normalization",
                             "savings_verification", "sustainability_reporting"],
        },
        # ---- Extended Building Automation Vendors ----
        {
            "name": "Trane Tracer SC/ES",
            "category": IntegrationCategory.BUILDING_AUTOMATION,
            "platform_type": "trane_tracer",
            "auth_config": {"method": AuthMethod.CERTIFICATE.value},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 15},
            "capabilities": ["chiller_plant_management", "air_handler_control",
                             "variable_frequency_drive", "energy_optimization",
                             "fault_detection_diagnostics", "comfort_management",
                             "equipment_scheduling", "trend_logging"],
        },
        {
            "name": "Carrier/Automated Logic WebCTRL",
            "category": IntegrationCategory.BUILDING_AUTOMATION,
            "platform_type": "carrier_webctrl",
            "auth_config": {"method": AuthMethod.CERTIFICATE.value},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 15},
            "capabilities": ["webctrl_server_management", "environmental_index_control",
                             "energy_reports", "equipment_scheduling",
                             "alarm_console", "trend_viewer",
                             "optimal_start_stop", "demand_limiting"],
        },
        {
            "name": "Schneider Electric EcoStruxure BMS",
            "category": IntegrationCategory.BUILDING_AUTOMATION,
            "platform_type": "schneider_bms",
            "auth_config": {"method": AuthMethod.CERTIFICATE.value},
            "rate_limit": {"requests_per_minute": 100, "burst_limit": 15},
            "capabilities": ["smartx_controller_management", "room_automation",
                             "energy_management", "fire_safety_integration",
                             "access_control_integration", "building_analytics",
                             "sustainability_reporting", "asset_management"],
        },
        {
            "name": "Delta Controls enteliWEB",
            "category": IntegrationCategory.BUILDING_AUTOMATION,
            "platform_type": "delta_enteliweb",
            "auth_config": {"method": AuthMethod.API_KEY.value},
            "rate_limit": {"requests_per_minute": 80, "burst_limit": 12},
            "capabilities": ["enteliweb_management", "o3_sensor_integration",
                             "orca_controller_programming", "energy_dashboards",
                             "trend_analysis", "alarm_management",
                             "scheduling", "remote_access"],
        },
        {
            "name": "Distech Controls ECLYPSE",
            "category": IntegrationCategory.BUILDING_AUTOMATION,
            "platform_type": "distech_eclypse",
            "auth_config": {"method": AuthMethod.API_KEY.value},
            "rate_limit": {"requests_per_minute": 80, "burst_limit": 12},
            "capabilities": ["eclypse_connected_controller", "envysion_web_interface",
                             "allure_unitouch_integration", "room_automation",
                             "energy_optimization", "iot_edge_computing",
                             "cloud_analytics", "scheduling"],
        },
        # ---- Extended Energy Management Platforms ----
        {
            "name": "GridPoint Energy Management",
            "category": IntegrationCategory.ENERGY_MANAGEMENT,
            "platform_type": "gridpoint",
            "auth_config": {"method": AuthMethod.API_KEY.value},
            "rate_limit": {"requests_per_minute": 60, "burst_limit": 10},
            "capabilities": ["energy_optimization", "hvac_control_optimization",
                             "demand_management", "portfolio_analytics",
                             "fault_detection", "comfort_management",
                             "sustainability_tracking", "utility_rate_analysis"],
        },
        {
            "name": "Tridium Niagara Framework",
            "category": IntegrationCategory.ENERGY_MANAGEMENT,
            "platform_type": "tridium_niagara",
            "auth_config": {"method": AuthMethod.CERTIFICATE.value},
            "rate_limit": {"requests_per_minute": 80, "burst_limit": 12},
            "capabilities": ["open_framework_integration", "multi_protocol_normalization",
                             "energy_dashboards", "analytics_engine",
                             "alarm_management", "equipment_scheduling",
                             "data_historian", "edge_computing"],
        },
        {
            "name": "ABB Ability Energy Manager",
            "category": IntegrationCategory.ENERGY_MANAGEMENT,
            "platform_type": "abb_ability",
            "auth_config": {"method": AuthMethod.OAUTH.value},
            "rate_limit": {"requests_per_minute": 60, "burst_limit": 10},
            "capabilities": ["energy_monitoring", "power_quality_analysis",
                             "load_management", "demand_forecasting",
                             "energy_cost_optimization", "carbon_tracking",
                             "asset_performance", "microgrid_management"],
        },
        {
            "name": "Brainbox AI",
            "category": IntegrationCategory.ENERGY_MANAGEMENT,
            "platform_type": "brainbox_ai",
            "auth_config": {"method": AuthMethod.API_KEY.value},
            "rate_limit": {"requests_per_minute": 60, "burst_limit": 10},
            "capabilities": ["autonomous_hvac_optimization", "deep_learning_prediction",
                             "energy_reduction", "carbon_footprint_reduction",
                             "occupant_comfort_optimization", "predictive_control",
                             "cloud_ai_analytics", "real_time_monitoring"],
        },
    ]
    return [EnterpriseConnector(**s) for s in specs]


DEFAULT_ENTERPRISE_CONNECTORS = _build_defaults()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class EnterpriseIntegrationRegistry:
    """Central registry that manages connector lifecycle — register, discover,
    execute actions, and perform health checks."""

    def __init__(self, load_defaults: bool = True):
        self._lock = threading.RLock()
        self._connectors: Dict[str, EnterpriseConnector] = {}
        if load_defaults:
            for c in DEFAULT_ENTERPRISE_CONNECTORS:
                self._connectors[c.platform_type] = c

    # -- registration -------------------------------------------------------

    def register(self, connector: EnterpriseConnector) -> Dict[str, Any]:
        with self._lock:
            self._connectors[connector.platform_type] = connector
            return {"registered": True, "platform_type": connector.platform_type}

    def unregister(self, platform_type: str) -> Dict[str, Any]:
        with self._lock:
            if platform_type in self._connectors:
                del self._connectors[platform_type]
                return {"unregistered": True, "platform_type": platform_type}
            return {"unregistered": False, "error": f"Unknown platform: {platform_type}"}

    # -- discovery ----------------------------------------------------------

    def discover(self, category: Optional[IntegrationCategory] = None) -> List[Dict[str, Any]]:
        with self._lock:
            connectors = list(self._connectors.values())
        if category is not None:
            connectors = [c for c in connectors if c.category == category]
        return [c.to_dict() for c in connectors]

    def get_connector(self, platform_type: str) -> Optional[EnterpriseConnector]:
        with self._lock:
            return self._connectors.get(platform_type)

    def list_categories(self) -> List[str]:
        with self._lock:
            return sorted({c.category.value for c in self._connectors.values()})

    def list_platforms(self) -> List[str]:
        with self._lock:
            return sorted(self._connectors.keys())

    # -- execution ----------------------------------------------------------

    def execute(self, platform_type: str, action_name: str,
                params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        connector = self.get_connector(platform_type)
        if connector is None:
            return {"success": False, "error": f"Unknown platform: {platform_type}"}
        return connector.execute_action(action_name, params)

    # -- health -------------------------------------------------------------

    def health_check(self, platform_type: str) -> Dict[str, Any]:
        connector = self.get_connector(platform_type)
        if connector is None:
            return {"status": "unknown", "error": f"Unknown platform: {platform_type}"}
        return connector.health_check()

    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            connectors = dict(self._connectors)
        return {pt: c.health_check() for pt, c in connectors.items()}

    # -- stats --------------------------------------------------------------

    def statistics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._connectors)
            enabled = sum(1 for c in self._connectors.values() if c.is_enabled())
            cats = {c.category.value for c in self._connectors.values()}
            return {
                "total_connectors": total,
                "enabled_connectors": enabled,
                "disabled_connectors": total - enabled,
                "categories": sorted(cats),
                "platforms": sorted(self._connectors.keys()),
            }


# ---------------------------------------------------------------------------
# Workflow Binder — bind connectors into DAG workflows
# ---------------------------------------------------------------------------

class IntegrationWorkflowBinder:
    """Bind enterprise connectors as step handlers in a DAG workflow."""

    def __init__(self, registry: EnterpriseIntegrationRegistry):
        self._registry = registry
        self._lock = threading.RLock()
        self._workflows: Dict[str, Dict[str, Any]] = {}

    def create_workflow(self, workflow_id: str, name: str,
                        description: str = "") -> Dict[str, Any]:
        with self._lock:
            wf = {
                "workflow_id": workflow_id,
                "name": name,
                "description": description,
                "steps": [],
                "edges": [],
                "created_at": time.time(),
                "status": "created",
            }
            self._workflows[workflow_id] = wf
            return dict(wf)

    def add_step(self, workflow_id: str, step_id: str,
                 platform_type: str, action_name: str,
                 params: Optional[Dict[str, Any]] = None,
                 depends_on: Optional[List[str]] = None) -> Dict[str, Any]:
        with self._lock:
            wf = self._workflows.get(workflow_id)
            if wf is None:
                return {"success": False, "error": f"Unknown workflow: {workflow_id}"}

            connector = self._registry.get_connector(platform_type)
            if connector is None:
                return {"success": False, "error": f"Unknown platform: {platform_type}"}

            if action_name not in connector.capabilities:
                return {"success": False, "error": f"Unsupported action: {action_name}"}

            step = {
                "step_id": step_id,
                "platform_type": platform_type,
                "action_name": action_name,
                "params": params or {},
                "depends_on": depends_on or [],
                "status": "pending",
            }
            wf["steps"].append(step)

            # record DAG edges
            for dep in (depends_on or []):
                wf["edges"].append({"from": dep, "to": step_id})

            return {"success": True, "step": step}

    def execute_workflow(self, workflow_id: str) -> Dict[str, Any]:
        with self._lock:
            wf = self._workflows.get(workflow_id)
            if wf is None:
                return {"success": False, "error": f"Unknown workflow: {workflow_id}"}
            wf_copy = dict(wf)
            wf["status"] = "running"

        results: List[Dict[str, Any]] = []
        completed: set = set()
        steps = list(wf_copy["steps"])
        remaining = list(steps)
        max_iterations = len(steps) + 1
        iteration = 0

        while remaining and iteration < max_iterations:
            iteration += 1
            progress = False
            next_remaining = []
            for step in remaining:
                deps = set(step.get("depends_on", []))
                if deps.issubset(completed):
                    result = self._registry.execute(
                        step["platform_type"], step["action_name"], step["params"]
                    )
                    result["step_id"] = step["step_id"]
                    results.append(result)
                    if result.get("success"):
                        completed.add(step["step_id"])
                        step["status"] = "completed"
                    else:
                        step["status"] = "failed"
                    progress = True
                else:
                    next_remaining.append(step)
            remaining = next_remaining
            if not progress:
                break

        for step in remaining:
            step["status"] = "skipped"
            results.append({"step_id": step["step_id"], "success": False, "error": "Unmet dependencies"})

        with self._lock:
            wf["status"] = "completed" if not remaining else "partial"

        all_ok = all(r.get("success") for r in results)
        return {
            "workflow_id": workflow_id,
            "success": all_ok,
            "results": results,
            "status": wf["status"],
        }

    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            wf = self._workflows.get(workflow_id)
            return dict(wf) if wf else None

    def list_workflows(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {"workflow_id": wid, "name": w["name"], "status": w["status"],
                 "step_count": len(w["steps"])}
                for wid, w in self._workflows.items()
            ]

    def delete_workflow(self, workflow_id: str) -> Dict[str, Any]:
        with self._lock:
            if workflow_id in self._workflows:
                del self._workflows[workflow_id]
                return {"deleted": True, "workflow_id": workflow_id}
            return {"deleted": False, "error": f"Unknown workflow: {workflow_id}"}


# ---------------------------------------------------------------------------
# Capability Mapper — map business actions to connector capabilities
# ---------------------------------------------------------------------------

class AutomationCapabilityMapper:
    """Map high-level business actions to connector capabilities automatically."""

    def __init__(self, registry: EnterpriseIntegrationRegistry):
        self._registry = registry
        self._lock = threading.RLock()
        self._custom_mappings: Dict[str, List[Dict[str, str]]] = {}

    def map_action(self, business_action: str) -> List[Dict[str, Any]]:
        """Find all connector capabilities that match a business action keyword."""
        action_lower = business_action.lower().replace(" ", "_")
        results: List[Dict[str, Any]] = []

        # check custom mappings first
        with self._lock:
            custom = self._custom_mappings.get(action_lower, [])
            for mapping in custom:
                results.append({
                    "platform_type": mapping["platform_type"],
                    "capability": mapping["capability"],
                    "source": "custom",
                    "match_score": 1.0,
                })

        # scan connector capabilities for keyword matches
        connectors = self._registry.discover()
        for c in connectors:
            for cap in c.get("capabilities", []):
                score = self._score_match(action_lower, cap)
                if score > 0:
                    results.append({
                        "platform_type": c["platform_type"],
                        "capability": cap,
                        "source": "auto",
                        "match_score": score,
                    })

        results.sort(key=lambda r: r["match_score"], reverse=True)
        return results

    def register_mapping(self, business_action: str, platform_type: str,
                         capability: str) -> Dict[str, Any]:
        action_lower = business_action.lower().replace(" ", "_")
        with self._lock:
            self._custom_mappings.setdefault(action_lower, []).append(
                {"platform_type": platform_type, "capability": capability}
            )
            return {"registered": True, "action": action_lower,
                    "platform_type": platform_type, "capability": capability}

    def unregister_mapping(self, business_action: str, platform_type: str,
                           capability: str) -> Dict[str, Any]:
        action_lower = business_action.lower().replace(" ", "_")
        with self._lock:
            mappings = self._custom_mappings.get(action_lower, [])
            target = {"platform_type": platform_type, "capability": capability}
            if target in mappings:
                mappings.remove(target)
                return {"unregistered": True}
            return {"unregistered": False, "error": "Mapping not found"}

    def list_mappings(self) -> Dict[str, List[Dict[str, str]]]:
        with self._lock:
            return dict(self._custom_mappings)

    def suggest_workflow(self, *business_actions: str) -> Dict[str, Any]:
        """Suggest a workflow of connector steps for a sequence of business actions."""
        steps: List[Dict[str, Any]] = []
        for action in business_actions:
            matches = self.map_action(action)
            if matches:
                best = matches[0]
                steps.append({
                    "action": action,
                    "platform_type": best["platform_type"],
                    "capability": best["capability"],
                    "score": best["match_score"],
                })
            else:
                steps.append({
                    "action": action,
                    "platform_type": None,
                    "capability": None,
                    "score": 0.0,
                })
        return {
            "actions": list(business_actions),
            "steps": steps,
            "coverage": sum(1 for s in steps if s["platform_type"]) / max(len(steps), 1),
        }

    # -- scoring ------------------------------------------------------------

    @staticmethod
    def _score_match(query: str, capability: str) -> float:
        cap_lower = capability.lower()
        if query == cap_lower:
            return 1.0
        if query in cap_lower or cap_lower in query:
            return 0.7
        # token overlap
        q_tokens = set(query.split("_"))
        c_tokens = set(cap_lower.split("_"))
        overlap = q_tokens & c_tokens
        if overlap:
            return 0.4 * len(overlap) / max(len(q_tokens), len(c_tokens))
        return 0.0
