# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
connector_registry.py — Murphy System App Connector Ecosystem
50+ pre-registered connectors across 20 categories with plugin SDK support.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ConnectorCategory(Enum):
    CRM = "crm"
    COMMUNICATION = "communication"
    PROJECT_MANAGEMENT = "project_management"
    CLOUD = "cloud"
    DEVOPS = "devops"
    ERP = "erp"
    PAYMENT = "payment"
    KNOWLEDGE = "knowledge"
    ITSM = "itsm"
    ANALYTICS = "analytics"
    SECURITY = "security"
    IOT = "iot"
    SOCIAL = "social"
    MARKETING = "marketing"
    HR = "hr"
    FINANCE = "finance"
    HEALTHCARE = "healthcare"
    LEGAL = "legal"
    EDUCATION = "education"
    CUSTOM = "custom"


class AuthType(Enum):
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    JWT = "jwt"
    MTLS = "mtls"
    NONE = "none"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Connector:
    name: str
    category: ConnectorCategory
    description: str
    auth_type: AuthType
    endpoints: List[str]
    version: str = "1.0.0"
    enabled: bool = True
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["category"] = self.category.value
        d["auth_type"] = self.auth_type.value
        return d


# ---------------------------------------------------------------------------
# Connector Registry
# ---------------------------------------------------------------------------

class ConnectorRegistry:
    """Central registry for all Murphy System connectors."""

    def __init__(self) -> None:
        self._connectors: Dict[str, Connector] = {}

    def register(self, connector: Connector) -> None:
        """Register a connector (overwrites if same name)."""
        self._connectors[connector.name] = connector

    def get(self, name: str) -> Optional[Connector]:
        return self._connectors.get(name)

    def list_all(self) -> List[Connector]:
        return list(self._connectors.values())

    def list_by_category(self, category: ConnectorCategory) -> List[Connector]:
        return [c for c in self._connectors.values() if c.category == category]

    def search(self, query: str) -> List[Connector]:
        q = query.lower()
        return [
            c for c in self._connectors.values()
            if q in c.name.lower() or q in c.description.lower() or any(q in t for t in c.tags)
        ]

    def count(self) -> int:
        return len(self._connectors)

    def categories_covered(self) -> List[str]:
        return list({c.category.value for c in self._connectors.values()})

    def export_catalog(self, indent: int = 2) -> str:
        return json.dumps(
            {"total": self.count(), "connectors": [c.to_dict() for c in self.list_all()]},
            indent=indent,
        )

    def unregister(self, name: str) -> bool:
        if name in self._connectors:
            del self._connectors[name]
            return True
        return False


# ---------------------------------------------------------------------------
# Pre-registered Connectors (50+)
# ---------------------------------------------------------------------------

def _make_registry() -> ConnectorRegistry:
    reg = ConnectorRegistry()
    _connectors = [
        # ── CRM ─────────────────────────────────────────────────────────────
        Connector("Salesforce", ConnectorCategory.CRM,
                  "World's #1 CRM — leads, opportunities, accounts, contacts",
                  AuthType.OAUTH2, ["/sobjects", "/query", "/composite"], "58.0",
                  tags=["crm", "enterprise", "cloud"]),
        Connector("HubSpot", ConnectorCategory.CRM,
                  "Inbound CRM — contacts, deals, pipelines, marketing hub",
                  AuthType.OAUTH2, ["/crm/v3/objects", "/crm/v3/pipelines"], "v3",
                  tags=["crm", "marketing", "sme"]),
        Connector("Zoho CRM", ConnectorCategory.CRM,
                  "Full-featured CRM with AI — Zia assistant included",
                  AuthType.OAUTH2, ["/crm/v4/Leads", "/crm/v4/Contacts"], "v4",
                  tags=["crm", "zoho"]),
        Connector("Pipedrive", ConnectorCategory.CRM,
                  "Sales-focused CRM with visual pipeline management",
                  AuthType.API_KEY, ["/deals", "/persons", "/organizations"], "v1",
                  tags=["crm", "sales"]),

        # ── COMMUNICATION ────────────────────────────────────────────────────
        Connector("Slack", ConnectorCategory.COMMUNICATION,
                  "Team messaging — channels, DMs, threads, Bolt apps",
                  AuthType.OAUTH2, ["/chat.postMessage", "/conversations.list"], "v2",
                  tags=["messaging", "team", "notifications"]),
        Connector("Microsoft Teams", ConnectorCategory.COMMUNICATION,
                  "Enterprise chat and video — channels, meetings, bots",
                  AuthType.OAUTH2, ["/teams", "/channels", "/chats"], "v1.0",
                  tags=["messaging", "enterprise", "microsoft"]),
        Connector("Twilio SMS", ConnectorCategory.COMMUNICATION,
                  "SMS/MMS/voice API — global messaging platform",
                  AuthType.BASIC, ["/Messages", "/Calls", "/Verify"], "2010-04-01",
                  tags=["sms", "voice", "otp"]),
        Connector("SendGrid", ConnectorCategory.COMMUNICATION,
                  "Transactional and marketing email delivery",
                  AuthType.API_KEY, ["/mail/send", "/marketing/contacts"], "v3",
                  tags=["email", "marketing"]),
        Connector("Mailchimp", ConnectorCategory.COMMUNICATION,
                  "Email marketing — audiences, campaigns, automations",
                  AuthType.OAUTH2, ["/lists", "/campaigns", "/automations"], "3.0",
                  tags=["email", "marketing"]),
        Connector("Zoom", ConnectorCategory.COMMUNICATION,
                  "Video meetings, webinars, phone system",
                  AuthType.OAUTH2, ["/meetings", "/webinars", "/users"], "v2",
                  tags=["video", "meetings"]),

        # ── PROJECT MANAGEMENT ───────────────────────────────────────────────
        Connector("Jira", ConnectorCategory.PROJECT_MANAGEMENT,
                  "Issue and project tracking — sprints, epics, boards",
                  AuthType.OAUTH2, ["/issue", "/project", "/sprint"], "v3",
                  tags=["agile", "atlassian", "tracking"]),
        Connector("Confluence", ConnectorCategory.KNOWLEDGE,
                  "Team wiki and knowledge base — pages, spaces, macros",
                  AuthType.OAUTH2, ["/content", "/space", "/search"], "v2",
                  tags=["wiki", "docs", "atlassian"]),
        Connector("Asana", ConnectorCategory.PROJECT_MANAGEMENT,
                  "Work management — tasks, projects, portfolios, goals",
                  AuthType.OAUTH2, ["/tasks", "/projects", "/portfolios"], "v1",
                  tags=["tasks", "projects"]),
        Connector("Trello", ConnectorCategory.PROJECT_MANAGEMENT,
                  "Kanban boards — cards, lists, checklists, power-ups",
                  AuthType.OAUTH2, ["/boards", "/cards", "/lists"], "1",
                  tags=["kanban", "boards", "atlassian"]),
        Connector("Monday.com", ConnectorCategory.PROJECT_MANAGEMENT,
                  "Work OS — boards, automations, integrations",
                  AuthType.API_KEY, ["/boards", "/items", "/updates"], "v2",
                  tags=["work-os", "no-code"]),
        Connector("Linear", ConnectorCategory.PROJECT_MANAGEMENT,
                  "Engineering issue tracking — cycles, roadmaps, insights",
                  AuthType.API_KEY, ["/issues", "/cycles", "/teams"], "v1",
                  tags=["engineering", "agile"]),

        # ── CLOUD ────────────────────────────────────────────────────────────
        Connector("AWS S3", ConnectorCategory.CLOUD,
                  "Amazon Simple Storage Service — buckets, objects, presigned URLs",
                  AuthType.API_KEY, ["/", "/{bucket}", "/{bucket}/{key}"], "2006-03-01",
                  tags=["aws", "storage", "cloud"]),
        Connector("AWS Lambda", ConnectorCategory.CLOUD,
                  "Serverless functions — invoke, manage, monitor",
                  AuthType.API_KEY, ["/functions", "/functions/{name}/invocations"], "2015-03-31",
                  tags=["aws", "serverless"]),
        Connector("Google Cloud Storage", ConnectorCategory.CLOUD,
                  "GCS — buckets, objects, ACLs, lifecycle policies",
                  AuthType.OAUTH2, ["/b", "/b/{bucket}/o"], "v1",
                  tags=["gcp", "storage", "cloud"]),
        Connector("Google BigQuery", ConnectorCategory.CLOUD,
                  "Serverless data warehouse — queries, jobs, datasets",
                  AuthType.OAUTH2, ["/projects/{proj}/datasets", "/projects/{proj}/queries"], "v2",
                  tags=["gcp", "analytics", "bigquery"]),
        Connector("Azure Blob Storage", ConnectorCategory.CLOUD,
                  "Azure object storage — containers, blobs, SAS tokens",
                  AuthType.API_KEY, ["/", "/{container}", "/{container}/{blob}"], "2023-08-03",
                  tags=["azure", "storage", "cloud"]),
        Connector("Azure OpenAI", ConnectorCategory.CLOUD,
                  "Azure-hosted OpenAI models — completions, embeddings, fine-tuning",
                  AuthType.API_KEY, ["/openai/deployments/{model}/completions"], "2024-02-01",
                  tags=["azure", "llm", "ai"]),

        # ── DEVOPS ──────────────────────────────────────────────────────────
        Connector("GitHub", ConnectorCategory.DEVOPS,
                  "Code hosting — repos, PRs, issues, Actions, Packages",
                  AuthType.OAUTH2, ["/repos", "/issues", "/pulls", "/actions"], "v3",
                  tags=["git", "ci-cd", "source-control"]),
        Connector("GitLab", ConnectorCategory.DEVOPS,
                  "DevOps platform — pipelines, MRs, container registry",
                  AuthType.OAUTH2, ["/projects", "/pipelines", "/merge_requests"], "v4",
                  tags=["git", "ci-cd", "devops"]),
        Connector("Datadog", ConnectorCategory.ANALYTICS,
                  "Cloud monitoring — metrics, logs, APM, synthetics, dashboards",
                  AuthType.API_KEY, ["/metrics", "/logs", "/monitors", "/dashboards"], "v2",
                  tags=["monitoring", "observability", "apm"]),
        Connector("PagerDuty", ConnectorCategory.ITSM,
                  "Incident management — alerts, escalations, on-call schedules",
                  AuthType.API_KEY, ["/incidents", "/services", "/schedules"], "v2",
                  tags=["incidents", "on-call", "alerting"]),
        Connector("Jenkins", ConnectorCategory.DEVOPS,
                  "CI/CD automation server — jobs, builds, pipelines",
                  AuthType.BASIC, ["/job/{name}/build", "/job/{name}/lastBuild"], "2.x",
                  tags=["ci", "cd", "builds"]),
        Connector("ArgoCD", ConnectorCategory.DEVOPS,
                  "GitOps continuous delivery for Kubernetes",
                  AuthType.JWT, ["/applications", "/clusters", "/repositories"], "v1",
                  tags=["gitops", "kubernetes", "cd"]),

        # ── ERP ─────────────────────────────────────────────────────────────
        Connector("SAP S/4HANA", ConnectorCategory.ERP,
                  "Enterprise resource planning — finance, procurement, manufacturing",
                  AuthType.OAUTH2, ["/sap/opu/odata/sap/API_BUSINESS_PARTNER"], "2023",
                  tags=["erp", "enterprise", "sap"]),
        Connector("Workday", ConnectorCategory.HR,
                  "HR and finance SaaS — workers, payroll, benefits, recruiting",
                  AuthType.OAUTH2, ["/workers", "/payroll", "/organizations"], "v39",
                  tags=["hr", "payroll", "enterprise"]),
        Connector("Oracle NetSuite", ConnectorCategory.ERP,
                  "Cloud ERP — accounting, inventory, CRM, e-commerce",
                  AuthType.OAUTH2, ["/record/v1", "/query/v1/suiteql"], "2023.2",
                  tags=["erp", "accounting", "oracle"]),

        # ── PAYMENT ─────────────────────────────────────────────────────────
        Connector("Stripe", ConnectorCategory.PAYMENT,
                  "Payments infrastructure — charges, subscriptions, payouts, fraud",
                  AuthType.API_KEY, ["/charges", "/subscriptions", "/payment_intents"], "2023-10-16",
                  tags=["payments", "subscriptions", "fintech"]),
        Connector("PayPal", ConnectorCategory.PAYMENT,
                  "Global payments — orders, subscriptions, invoicing",
                  AuthType.OAUTH2, ["/v2/checkout/orders", "/v1/billing/subscriptions"], "v2",
                  tags=["payments", "global"]),
        Connector("Square", ConnectorCategory.PAYMENT,
                  "Point-of-sale + online payments — catalog, inventory, orders",
                  AuthType.OAUTH2, ["/v2/payments", "/v2/orders", "/v2/catalog"], "2023-12-13",
                  tags=["pos", "payments", "retail"]),

        # ── FINANCE ─────────────────────────────────────────────────────────
        Connector("QuickBooks Online", ConnectorCategory.FINANCE,
                  "SMB accounting — invoices, expenses, payroll, tax",
                  AuthType.OAUTH2, ["/company/{id}/invoice", "/company/{id}/account"], "v3",
                  tags=["accounting", "sme", "intuit"]),
        Connector("Xero", ConnectorCategory.FINANCE,
                  "Cloud accounting — invoices, bank feeds, payroll",
                  AuthType.OAUTH2, ["/Invoices", "/Accounts", "/BankTransactions"], "2.0",
                  tags=["accounting", "sme", "australia"]),
        Connector("Plaid", ConnectorCategory.FINANCE,
                  "Open banking — account data, transactions, identity, income",
                  AuthType.API_KEY, ["/transactions/get", "/identity/get", "/balance/get"], "2020-09-14",
                  tags=["banking", "fintech", "open-banking"]),

        # ── ITSM ────────────────────────────────────────────────────────────
        Connector("ServiceNow", ConnectorCategory.ITSM,
                  "ITSM platform — incidents, change requests, CMDB, workflow",
                  AuthType.OAUTH2, ["/table/incident", "/table/change_request", "/table/cmdb_ci"], "latest",
                  tags=["itsm", "enterprise", "tickets"]),
        Connector("Zendesk", ConnectorCategory.ITSM,
                  "Customer support — tickets, macros, automations, chat",
                  AuthType.OAUTH2, ["/tickets", "/users", "/organizations"], "v2",
                  tags=["support", "helpdesk", "cx"]),
        Connector("Freshdesk", ConnectorCategory.ITSM,
                  "Help desk — tickets, agents, solutions, time tracking",
                  AuthType.API_KEY, ["/tickets", "/agents", "/solutions"], "v2",
                  tags=["support", "helpdesk", "sme"]),

        # ── SECURITY ────────────────────────────────────────────────────────
        Connector("Okta", ConnectorCategory.SECURITY,
                  "Identity platform — SSO, MFA, user lifecycle, SCIM",
                  AuthType.OAUTH2, ["/users", "/groups", "/apps", "/logs"], "v1",
                  tags=["identity", "sso", "mfa"]),
        Connector("CrowdStrike Falcon", ConnectorCategory.SECURITY,
                  "Endpoint security — detections, incidents, IOCs, device management",
                  AuthType.OAUTH2, ["/detects/queries", "/incidents/entities", "/devices/queries"], "v2",
                  tags=["edr", "security", "endpoint"]),
        Connector("Splunk", ConnectorCategory.SECURITY,
                  "SIEM and observability — search, alerts, dashboards, HEC",
                  AuthType.API_KEY, ["/services/search/jobs", "/services/data/inputs/http"], "9.x",
                  tags=["siem", "security", "logs"]),

        # ── IOT ─────────────────────────────────────────────────────────────
        Connector("AWS IoT Core", ConnectorCategory.IOT,
                  "Managed IoT cloud — device registry, MQTT broker, rules engine",
                  AuthType.MTLS, ["/things", "/jobs", "/topics/{topic}"], "2015-05-28",
                  tags=["iot", "aws", "mqtt"]),
        Connector("Azure IoT Hub", ConnectorCategory.IOT,
                  "IoT device management — telemetry, twins, direct methods",
                  AuthType.API_KEY, ["/devices", "/twins", "/messages/events"], "2021-04-12",
                  tags=["iot", "azure", "telemetry"]),

        # ── SOCIAL ──────────────────────────────────────────────────────────
        Connector("Twitter/X API", ConnectorCategory.SOCIAL,
                  "Social media — tweets, users, search, streams, DMs",
                  AuthType.OAUTH2, ["/tweets", "/users", "/dm_events", "/tweets/search/recent"], "v2",
                  tags=["social", "twitter", "media"]),
        Connector("LinkedIn API", ConnectorCategory.SOCIAL,
                  "Professional network — profile, posts, ads, company pages",
                  AuthType.OAUTH2, ["/people", "/organizations", "/posts", "/adAccounts"], "v2",
                  tags=["social", "linkedin", "b2b"]),

        # ── MARKETING ───────────────────────────────────────────────────────
        Connector("Google Ads", ConnectorCategory.MARKETING,
                  "Search and display advertising — campaigns, keywords, reports",
                  AuthType.OAUTH2, ["/customers/{id}/campaigns", "/customers/{id}/googleAds:search"], "v15",
                  tags=["ads", "ppc", "google"]),
        Connector("Meta Ads", ConnectorCategory.MARKETING,
                  "Facebook/Instagram ads — campaigns, adsets, insights",
                  AuthType.OAUTH2, ["/act_{id}/campaigns", "/act_{id}/insights"], "v19.0",
                  tags=["ads", "facebook", "instagram"]),
        Connector("Segment", ConnectorCategory.ANALYTICS,
                  "Customer data platform — identify, track, page, group",
                  AuthType.API_KEY, ["/v1/identify", "/v1/track", "/v1/page", "/v1/group"], "v1",
                  tags=["cdp", "analytics", "data"]),

        # ── HEALTHCARE ──────────────────────────────────────────────────────
        Connector("Epic MyChart FHIR", ConnectorCategory.HEALTHCARE,
                  "EHR FHIR R4 API — patient, observation, condition, medication",
                  AuthType.OAUTH2, ["/Patient", "/Observation", "/Condition", "/MedicationRequest"], "R4",
                  tags=["ehr", "fhir", "healthcare"]),
        Connector("Health Gorilla FHIR", ConnectorCategory.HEALTHCARE,
                  "Health data aggregation — labs, imaging, pharmacy, clinical notes",
                  AuthType.OAUTH2, ["/Patient", "/DiagnosticReport", "/DocumentReference"], "R4",
                  tags=["fhir", "lab", "healthcare"]),

        # ── KNOWLEDGE / AI ──────────────────────────────────────────────────
        Connector("Notion", ConnectorCategory.KNOWLEDGE,
                  "All-in-one workspace — pages, databases, comments, search",
                  AuthType.OAUTH2, ["/pages", "/databases", "/blocks", "/search"], "2022-06-28",
                  tags=["notes", "wiki", "database"]),
        Connector("OpenAI", ConnectorCategory.CUSTOM,
                  "GPT-4o, embeddings, DALL-E, Whisper, fine-tuning",
                  AuthType.API_KEY, ["/chat/completions", "/embeddings", "/images/generations"], "v1",
                  tags=["llm", "ai", "embeddings"]),
        Connector("Anthropic Claude", ConnectorCategory.CUSTOM,
                  "Claude 3 family — Opus, Sonnet, Haiku for enterprise AI",
                  AuthType.API_KEY, ["/messages", "/models"], "2023-06-01",
                  tags=["llm", "ai", "safety"]),

        # ── LEGAL / DOCUMENTS ───────────────────────────────────────────────
        Connector("DocuSign", ConnectorCategory.LEGAL,
                  "eSignature and contract lifecycle management",
                  AuthType.OAUTH2, ["/envelopes", "/templates", "/accounts"], "v2.1",
                  tags=["esignature", "contracts", "legal"]),
        Connector("Adobe Sign", ConnectorCategory.LEGAL,
                  "Digital signatures and agreement workflows",
                  AuthType.OAUTH2, ["/agreements", "/widgets", "/libraryDocuments"], "v6",
                  tags=["esignature", "adobe", "legal"]),

        # ── EDUCATION ───────────────────────────────────────────────────────
        Connector("Canvas LMS", ConnectorCategory.EDUCATION,
                  "Learning management — courses, assignments, grades, quizzes",
                  AuthType.API_KEY, ["/courses", "/assignments", "/submissions", "/quizzes"], "v1",
                  tags=["lms", "education", "courses"]),
    ]

    for c in _connectors:
        reg.register(c)

    return reg


# Module-level singleton registry (pre-populated)
registry: ConnectorRegistry = _make_registry()


def main() -> None:
    print(f"Murphy System Connector Registry — {registry.count()} connectors loaded")
    print()
    for cat in ConnectorCategory:
        items = registry.list_by_category(cat)
        if items:
            names = ", ".join(c.name for c in items)
            print(f"  [{cat.value.upper():>20}]  {names}")
    print()
    results = registry.search("healthcare")
    print(f"Search 'healthcare': {[c.name for c in results]}")


if __name__ == "__main__":
    main()
