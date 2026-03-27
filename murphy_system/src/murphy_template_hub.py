"""
Murphy System - Murphy Template Hub
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1

Workflow template marketplace for Murphy System.
Provides JSON-based template storage, search, installation, and export.
Integrates with: workflow_dag_engine.py, plugin_extension_sdk.py
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TemplateCategory(str, Enum):
    """TemplateCategory enumeration."""
    FACTORY = "factory"
    CONTENT = "content"
    DATA = "data"
    SYSTEM = "system"
    AGENT = "agent"
    BUSINESS = "business"


class Template(BaseModel):
    """Template — template definition."""
    template_id: str
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "murphy_system"
    tags: List[str] = []
    category: TemplateCategory
    flow_json: Dict[str, Any] = {}
    requirements: List[str] = []
    rating: float = 0.0
    downloads: int = 0
    created_at: str
    updated_at: str


class TemplateSearchQuery(BaseModel):
    """Query parameters for template search."""
    query: Optional[str] = None
    category: Optional[TemplateCategory] = None
    tags: List[str] = []
    min_rating: float = 0.0
    limit: int = 20


class TemplateStore:
    """TemplateStore — template store definition."""
    def __init__(self, templates_dir: Optional[str] = None) -> None:
        self._templates_dir = templates_dir
        self._store: Dict[str, Template] = {}
        self._lock = threading.Lock()

        if templates_dir:
            os.makedirs(templates_dir, exist_ok=True)
            self._load_from_dir()

    def _load_from_dir(self) -> None:
        if not self._templates_dir:
            return
        for filename in os.listdir(self._templates_dir):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(self._templates_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                template = Template(**data)
                self._store[template.template_id] = template
            except Exception as exc:
                logger.error("Failed to load template file %s: %s", filepath, exc)

    def save(self, template: Template) -> None:
        with self._lock:
            self._store[template.template_id] = template
            if self._templates_dir:
                filepath = os.path.join(
                    self._templates_dir, f"{template.template_id}.json"
                )
                try:
                    with open(filepath, "w", encoding="utf-8") as fh:
                        json.dump(template.model_dump(), fh, indent=2)
                except Exception as exc:
                    logger.error(
                        "Failed to persist template %s: %s", template.template_id, exc
                    )

    def get(self, template_id: str) -> Optional[Template]:
        with self._lock:
            return self._store.get(template_id)

    def delete(self, template_id: str) -> bool:
        with self._lock:
            if template_id not in self._store:
                return False
            del self._store[template_id]
            if self._templates_dir:
                filepath = os.path.join(
                    self._templates_dir, f"{template_id}.json"
                )
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except Exception as exc:
                    logger.error(
                        "Failed to delete template file %s: %s", filepath, exc
                    )
            return True

    def list_all(self) -> List[Template]:
        with self._lock:
            return list(self._store.values())

    def count(self) -> int:
        with self._lock:
            return len(self._store)


class TemplateRegistry:
    """TemplateRegistry — template registry definition."""
    def __init__(self, store: TemplateStore) -> None:
        self._store = store

    def register(self, template: Template) -> str:
        self._store.save(template)
        return template.template_id

    def search(self, query: TemplateSearchQuery) -> List[Template]:
        results: List[Template] = []
        query_lower = query.query.lower() if query.query else None

        for template in self._store.list_all():
            if query.category and template.category != query.category:
                continue
            if template.rating < query.min_rating:
                continue
            if query.tags:
                template_tags_lower = [t.lower() for t in template.tags]
                if not any(tag.lower() in template_tags_lower for tag in query.tags):
                    continue
            if query_lower:
                searchable = (
                    template.name.lower()
                    + " "
                    + template.description.lower()
                    + " "
                    + " ".join(t.lower() for t in template.tags)
                )
                if query_lower not in searchable:
                    continue
            results.append(template)

        return results[: query.limit]

    def list_by_category(self, category: TemplateCategory) -> List[Template]:
        return [t for t in self._store.list_all() if t.category == category]

    def get_popular(self, limit: int = 10) -> List[Template]:
        all_templates = self._store.list_all()
        return sorted(all_templates, key=lambda t: t.downloads, reverse=True)[:limit]

    def rate(self, template_id: str, rating: float) -> bool:
        template = self._store.get(template_id)
        if template is None:
            return False
        clamped = max(0.0, min(5.0, rating))
        updated = template.model_copy(
            update={
                "rating": (template.rating + clamped) / 2.0,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._store.save(updated)
        return True


_FORBIDDEN_STRINGS = ["eval", "exec", "__import__", "subprocess", "os.system"]


class TemplateValidator:
    """TemplateValidator — template validator definition."""
    def validate(self, template: Template) -> List[str]:
        errors: List[str] = []

        if not template.name.strip():
            errors.append("Template name must not be empty.")
        if len(template.description) < 10:
            errors.append("Description must be at least 10 characters.")
        if not isinstance(template.category, TemplateCategory):
            errors.append("Invalid category value.")
        if not template.flow_json:
            errors.append("flow_json must not be empty.")

        flow_str = json.dumps(template.flow_json)
        for forbidden in _FORBIDDEN_STRINGS:
            if forbidden in flow_str:
                errors.append(
                    f"flow_json contains forbidden string: '{forbidden}'."
                )

        return errors


class TemplateInstaller:
    """TemplateInstaller — template installer definition."""
    def __init__(
        self, registry: TemplateRegistry, validator: TemplateValidator
    ) -> None:
        self._registry = registry
        self._validator = validator

    def install(self, template: Template) -> Dict[str, Any]:
        errors = self._validator.validate(template)
        if errors:
            return {"success": False, "template_id": None, "errors": errors}
        try:
            template_id = self._registry.register(template)
            return {"success": True, "template_id": template_id, "errors": []}
        except Exception as exc:
            logger.error("Install failed for template %s: %s", template.template_id, exc)
            return {
                "success": False,
                "template_id": None,
                "errors": [str(exc)],
            }

    def check_compatibility(
        self, template: Template, available_modules: List[str]
    ) -> List[str]:
        available_set = set(available_modules)
        return [req for req in template.requirements if req not in available_set]

    def uninstall(self, template_id: str) -> bool:
        return self._registry._store.delete(template_id)


class TemplateExporter:
    """TemplateExporter — template exporter definition."""
    def export(self, template: Template) -> str:
        return template.model_dump_json(indent=2)

    def export_all(self, registry: TemplateRegistry) -> str:
        all_templates = registry._store.list_all()
        return json.dumps(
            [t.model_dump() for t in all_templates], indent=2
        )

    def import_from_json(self, json_str: str) -> Template:
        try:
            data = json.loads(json_str)
        except Exception as exc:
            logger.error("Failed to parse JSON for template import: %s", exc)
            raise
        try:
            return Template(**data)
        except Exception as exc:
            logger.error("Failed to construct Template from data: %s", exc)
            raise


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_factory_template() -> Template:
    now = _now_iso()
    return Template(
        template_id="tpl-factory-001",
        name="Standard Factory Workflow",
        description="Automates a factory production line with quality checks and output routing.",
        version="1.0.0",
        author="murphy_system",
        tags=["factory", "production", "automation"],
        category=TemplateCategory.FACTORY,
        flow_json={
            "nodes": [
                {"id": "start", "type": "trigger", "label": "Production Start"},
                {"id": "quality_check", "type": "task", "label": "Quality Check"},
                {"id": "route_output", "type": "decision", "label": "Route Output"},
                {"id": "end", "type": "terminal", "label": "Production End"},
            ],
            "edges": [
                {"from": "start", "to": "quality_check"},
                {"from": "quality_check", "to": "route_output"},
                {"from": "route_output", "to": "end"},
            ],
        },
        requirements=["factory_module"],
        rating=4.5,
        downloads=120,
        created_at=now,
        updated_at=now,
    )


def _make_content_template() -> Template:
    now = _now_iso()
    return Template(
        template_id="tpl-content-001",
        name="Content Generation Pipeline",
        description="End-to-end content creation pipeline from ideation to publishing.",
        version="1.0.0",
        author="murphy_system",
        tags=["content", "generation", "publishing"],
        category=TemplateCategory.CONTENT,
        flow_json={
            "nodes": [
                {"id": "ideation", "type": "trigger", "label": "Ideation"},
                {"id": "draft", "type": "task", "label": "Draft Content"},
                {"id": "review", "type": "task", "label": "Review"},
                {"id": "publish", "type": "terminal", "label": "Publish"},
            ],
            "edges": [
                {"from": "ideation", "to": "draft"},
                {"from": "draft", "to": "review"},
                {"from": "review", "to": "publish"},
            ],
        },
        requirements=["content_module"],
        rating=4.2,
        downloads=98,
        created_at=now,
        updated_at=now,
    )


def _make_data_template() -> Template:
    now = _now_iso()
    return Template(
        template_id="tpl-data-001",
        name="Data Ingestion and Transform",
        description="Ingest raw data from sources, transform, validate, and load into storage.",
        version="1.0.0",
        author="murphy_system",
        tags=["data", "etl", "ingestion", "transform"],
        category=TemplateCategory.DATA,
        flow_json={
            "nodes": [
                {"id": "ingest", "type": "trigger", "label": "Ingest Data"},
                {"id": "transform", "type": "task", "label": "Transform"},
                {"id": "validate", "type": "task", "label": "Validate"},
                {"id": "load", "type": "terminal", "label": "Load to Store"},
            ],
            "edges": [
                {"from": "ingest", "to": "transform"},
                {"from": "transform", "to": "validate"},
                {"from": "validate", "to": "load"},
            ],
        },
        requirements=["data_module"],
        rating=4.7,
        downloads=210,
        created_at=now,
        updated_at=now,
    )


def _make_system_template() -> Template:
    now = _now_iso()
    return Template(
        template_id="tpl-system-001",
        name="System Health Monitor",
        description="Monitors system health metrics and triggers alerts on threshold breach.",
        version="1.0.0",
        author="murphy_system",
        tags=["system", "monitoring", "alerts", "health"],
        category=TemplateCategory.SYSTEM,
        flow_json={
            "nodes": [
                {"id": "collect_metrics", "type": "trigger", "label": "Collect Metrics"},
                {"id": "evaluate", "type": "task", "label": "Evaluate Thresholds"},
                {"id": "alert", "type": "task", "label": "Send Alert"},
                {"id": "done", "type": "terminal", "label": "Done"},
            ],
            "edges": [
                {"from": "collect_metrics", "to": "evaluate"},
                {"from": "evaluate", "to": "alert"},
                {"from": "alert", "to": "done"},
            ],
        },
        requirements=["system_module"],
        rating=4.8,
        downloads=305,
        created_at=now,
        updated_at=now,
    )


def _make_agent_template() -> Template:
    now = _now_iso()
    return Template(
        template_id="tpl-agent-001",
        name="Autonomous Agent Workflow",
        description="Deploys an autonomous agent with perception, planning, and action loops.",
        version="1.0.0",
        author="murphy_system",
        tags=["agent", "autonomous", "planning", "action"],
        category=TemplateCategory.AGENT,
        flow_json={
            "nodes": [
                {"id": "perceive", "type": "trigger", "label": "Perceive Environment"},
                {"id": "plan", "type": "task", "label": "Plan Actions"},
                {"id": "act", "type": "task", "label": "Execute Actions"},
                {"id": "evaluate", "type": "decision", "label": "Evaluate Outcome"},
                {"id": "done", "type": "terminal", "label": "Done"},
            ],
            "edges": [
                {"from": "perceive", "to": "plan"},
                {"from": "plan", "to": "act"},
                {"from": "act", "to": "evaluate"},
                {"from": "evaluate", "to": "done"},
            ],
        },
        requirements=["agent_module"],
        rating=4.6,
        downloads=178,
        created_at=now,
        updated_at=now,
    )


def _make_business_template() -> Template:
    now = _now_iso()
    return Template(
        template_id="tpl-business-001",
        name="Business Process Orchestrator",
        description="Orchestrates a standard business approval and fulfillment process.",
        version="1.0.0",
        author="murphy_system",
        tags=["business", "approval", "orchestration", "fulfillment"],
        category=TemplateCategory.BUSINESS,
        flow_json={
            "nodes": [
                {"id": "request", "type": "trigger", "label": "Receive Request"},
                {"id": "approve", "type": "task", "label": "Approval Step"},
                {"id": "fulfill", "type": "task", "label": "Fulfill Request"},
                {"id": "notify", "type": "task", "label": "Notify Requester"},
                {"id": "done", "type": "terminal", "label": "Done"},
            ],
            "edges": [
                {"from": "request", "to": "approve"},
                {"from": "approve", "to": "fulfill"},
                {"from": "fulfill", "to": "notify"},
                {"from": "notify", "to": "done"},
            ],
        },
        requirements=["business_module"],
        rating=4.4,
        downloads=144,
        created_at=now,
        updated_at=now,
    )


def get_default_templates() -> List[Template]:
    return [
        _make_factory_template(),
        _make_content_template(),
        _make_data_template(),
        _make_system_template(),
        _make_agent_template(),
        _make_business_template(),
    ]


_GLOBAL_STORE: TemplateStore = TemplateStore()
_GLOBAL_REGISTRY: TemplateRegistry = TemplateRegistry(_GLOBAL_STORE)

for _tpl in get_default_templates():
    _GLOBAL_REGISTRY.register(_tpl)


def get_registry() -> TemplateRegistry:
    return _GLOBAL_REGISTRY
