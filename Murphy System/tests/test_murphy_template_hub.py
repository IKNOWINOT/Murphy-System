"""
Murphy System - Tests for Murphy Template Hub
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1
"""
import os

import json
import uuid
from datetime import datetime, timezone

import pytest

from murphy_template_hub import (
    TemplateCategory,
    Template,
    TemplateSearchQuery,
    TemplateStore,
    TemplateRegistry,
    TemplateValidator,
    TemplateInstaller,
    TemplateExporter,
    get_default_templates,
    get_registry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_template(
    name: str = None,
    category: TemplateCategory = TemplateCategory.AGENT,
    description: str = "A valid test template description.",
    flow_json: dict = None,
    tags: list = None,
    rating: float = 3.0,
    downloads: int = 10,
) -> Template:
    tid = f"tpl-{uuid.uuid4().hex[:8]}"
    now = _now()
    return Template(
        template_id=tid,
        name=name or f"Template {tid}",
        description=description,
        version="1.0.0",
        author="Test",
        tags=tags or ["test"],
        category=category,
        flow_json=flow_json or {"nodes": [{"id": "start"}], "edges": []},
        requirements=[],
        rating=rating,
        downloads=downloads,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# TestTemplateValidator
# ---------------------------------------------------------------------------

class TestTemplateValidator:
    def test_valid_template_no_errors(self):
        validator = TemplateValidator()
        template = _make_template()
        errors = validator.validate(template)
        assert errors == []

    def test_empty_name_is_invalid(self):
        validator = TemplateValidator()
        template = _make_template(name="   ")
        errors = validator.validate(template)
        assert any("name" in e.lower() for e in errors)

    def test_short_description_is_invalid(self):
        validator = TemplateValidator()
        template = _make_template(description="Too short")
        errors = validator.validate(template)
        assert any("description" in e.lower() for e in errors)

    def test_empty_flow_json_is_invalid(self):
        validator = TemplateValidator()
        now = _now()
        template = Template(
            template_id="tpl-empty-flow",
            name="Empty Flow Template",
            description="A valid description with enough length here.",
            category=TemplateCategory.AGENT,
            flow_json={},
            created_at=now,
            updated_at=now,
        )
        errors = validator.validate(template)
        assert any("flow_json" in e.lower() for e in errors)

    def test_forbidden_eval_in_flow_json(self):
        validator = TemplateValidator()
        template = _make_template(flow_json={"action": "eval(something)"})
        errors = validator.validate(template)
        assert any("eval" in e for e in errors)

    def test_forbidden_exec_in_flow_json(self):
        validator = TemplateValidator()
        template = _make_template(flow_json={"action": "exec(code)"})
        errors = validator.validate(template)
        assert any("exec" in e for e in errors)

    def test_multiple_errors_returned(self):
        validator = TemplateValidator()
        template = _make_template(name="  ", description="x", flow_json={})
        errors = validator.validate(template)
        assert len(errors) >= 2


# ---------------------------------------------------------------------------
# TestTemplateStore
# ---------------------------------------------------------------------------

class TestTemplateStore:
    def test_save_and_get(self):
        store = TemplateStore()
        template = _make_template()
        store.save(template)
        loaded = store.get(template.template_id)
        assert loaded is not None
        assert loaded.template_id == template.template_id

    def test_get_missing_returns_none(self):
        store = TemplateStore()
        assert store.get("no_such_id") is None

    def test_list_all_empty(self):
        store = TemplateStore()
        assert store.list_all() == []

    def test_list_all_returns_saved(self):
        store = TemplateStore()
        t1 = _make_template()
        t2 = _make_template()
        store.save(t1)
        store.save(t2)
        ids = [t.template_id for t in store.list_all()]
        assert t1.template_id in ids
        assert t2.template_id in ids

    def test_save_to_disk(self, tmp_path):
        store = TemplateStore(templates_dir=str(tmp_path))
        template = _make_template(name="Disk Template")
        store.save(template)
        loaded = store.get(template.template_id)
        assert loaded is not None
        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1

    def test_count(self):
        store = TemplateStore()
        assert store.count() == 0
        store.save(_make_template())
        assert store.count() == 1

    def test_delete(self):
        store = TemplateStore()
        template = _make_template()
        store.save(template)
        result = store.delete(template.template_id)
        assert result is True
        assert store.get(template.template_id) is None

    def test_delete_missing_returns_false(self):
        store = TemplateStore()
        assert store.delete("ghost_id") is False


# ---------------------------------------------------------------------------
# TestTemplateRegistry
# ---------------------------------------------------------------------------

class TestTemplateRegistry:
    def test_register_returns_template_id(self):
        store = TemplateStore()
        registry = TemplateRegistry(store)
        template = _make_template()
        returned_id = registry.register(template)
        assert returned_id == template.template_id

    def test_search_by_query(self):
        store = TemplateStore()
        registry = TemplateRegistry(store)
        template = _make_template(name="Unique Search Name ZYXWV")
        registry.register(template)
        results = registry.search(TemplateSearchQuery(query="ZYXWV"))
        assert any(t.template_id == template.template_id for t in results)

    def test_search_by_category(self):
        store = TemplateStore()
        registry = TemplateRegistry(store)
        factory_tpl = _make_template(category=TemplateCategory.FACTORY)
        content_tpl = _make_template(category=TemplateCategory.CONTENT)
        registry.register(factory_tpl)
        registry.register(content_tpl)
        results = registry.search(TemplateSearchQuery(category=TemplateCategory.FACTORY))
        ids = [t.template_id for t in results]
        assert factory_tpl.template_id in ids
        assert content_tpl.template_id not in ids

    def test_search_by_min_rating(self):
        store = TemplateStore()
        registry = TemplateRegistry(store)
        high = _make_template(rating=4.5)
        low = _make_template(rating=2.0)
        registry.register(high)
        registry.register(low)
        results = registry.search(TemplateSearchQuery(min_rating=4.0))
        ids = [t.template_id for t in results]
        assert high.template_id in ids
        assert low.template_id not in ids

    def test_list_by_category(self):
        store = TemplateStore()
        registry = TemplateRegistry(store)
        data_tpl = _make_template(category=TemplateCategory.DATA)
        system_tpl = _make_template(category=TemplateCategory.SYSTEM)
        registry.register(data_tpl)
        registry.register(system_tpl)
        data_results = registry.list_by_category(TemplateCategory.DATA)
        ids = [t.template_id for t in data_results]
        assert data_tpl.template_id in ids
        assert system_tpl.template_id not in ids

    def test_get_popular_returns_sorted_by_downloads(self):
        store = TemplateStore()
        registry = TemplateRegistry(store)
        low = _make_template(downloads=5)
        high = _make_template(downloads=999)
        registry.register(low)
        registry.register(high)
        popular = registry.get_popular(limit=1)
        assert popular[0].template_id == high.template_id


# ---------------------------------------------------------------------------
# TestTemplateInstaller
# ---------------------------------------------------------------------------

class TestTemplateInstaller:
    def _make_installer(self):
        store = TemplateStore()
        registry = TemplateRegistry(store)
        validator = TemplateValidator()
        return TemplateInstaller(registry=registry, validator=validator), registry

    def test_install_valid_template(self):
        installer, _ = self._make_installer()
        template = _make_template()
        result = installer.install(template)
        assert result["success"] is True
        assert result["template_id"] == template.template_id
        assert result["errors"] == []

    def test_install_invalid_template_fails(self):
        installer, _ = self._make_installer()
        bad = _make_template(name="  ", description="x", flow_json={})
        result = installer.install(bad)
        assert result["success"] is False
        assert len(result["errors"]) > 0

    def test_check_compatibility_all_present(self):
        installer, _ = self._make_installer()
        template = _make_template()
        template = template.model_copy(update={"requirements": ["mod_a", "mod_b"]})
        missing = installer.check_compatibility(template, ["mod_a", "mod_b", "mod_c"])
        assert missing == []

    def test_check_compatibility_missing_modules(self):
        installer, _ = self._make_installer()
        template = _make_template()
        template = template.model_copy(update={"requirements": ["mod_a", "mod_missing"]})
        missing = installer.check_compatibility(template, ["mod_a"])
        assert "mod_missing" in missing


# ---------------------------------------------------------------------------
# TestTemplateExporter
# ---------------------------------------------------------------------------

class TestTemplateExporter:
    def test_export_returns_json_string(self):
        exporter = TemplateExporter()
        template = _make_template()
        json_str = exporter.export(template)
        parsed = json.loads(json_str)
        assert parsed["template_id"] == template.template_id

    def test_import_from_json_round_trip(self):
        exporter = TemplateExporter()
        template = _make_template(name="Export Import Template")
        json_str = exporter.export(template)
        restored = exporter.import_from_json(json_str)
        assert restored.template_id == template.template_id
        assert restored.name == template.name

    def test_import_from_invalid_json_raises(self):
        exporter = TemplateExporter()
        with pytest.raises(Exception):
            exporter.import_from_json("{not valid json")

    def test_export_all_returns_list_json(self):
        store = TemplateStore()
        registry = TemplateRegistry(store)
        for _ in range(3):
            registry.register(_make_template())
        exporter = TemplateExporter()
        json_str = exporter.export_all(registry)
        parsed = json.loads(json_str)
        assert isinstance(parsed, list)
        assert len(parsed) == 3


# ---------------------------------------------------------------------------
# TestDefaultTemplates
# ---------------------------------------------------------------------------

class TestDefaultTemplates:
    def test_get_default_templates_returns_six(self):
        templates = get_default_templates()
        assert len(templates) == 6

    def test_default_templates_are_template_instances(self):
        templates = get_default_templates()
        for tpl in templates:
            assert isinstance(tpl, Template)

    def test_default_templates_have_unique_ids(self):
        templates = get_default_templates()
        ids = [t.template_id for t in templates]
        assert len(ids) == len(set(ids))

    def test_default_templates_cover_all_categories(self):
        templates = get_default_templates()
        categories = {t.category for t in templates}
        for cat in TemplateCategory:
            assert cat in categories, f"Missing category: {cat}"

    def test_default_templates_have_nonempty_flow_json(self):
        templates = get_default_templates()
        for tpl in templates:
            assert tpl.flow_json, f"Template {tpl.name} has empty flow_json"

    def test_default_templates_pass_validator_name_and_description(self):
        validator = TemplateValidator()
        templates = get_default_templates()
        for tpl in templates:
            errors = validator.validate(tpl)
            name_errors = [e for e in errors if "name" in e.lower()]
            desc_errors = [e for e in errors if "description" in e.lower()]
            assert name_errors == [], f"Template {tpl.name} name error: {name_errors}"
            assert desc_errors == [], f"Template {tpl.name} description error: {desc_errors}"


# ---------------------------------------------------------------------------
# TestGlobalRegistry
# ---------------------------------------------------------------------------

class TestGlobalRegistry:
    def test_get_registry_returns_template_registry(self):
        reg = get_registry()
        assert isinstance(reg, TemplateRegistry)

    def test_get_registry_is_stable(self):
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2

    def test_get_registry_pre_loaded_with_six_templates(self):
        reg = get_registry()
        all_templates = reg._store.list_all()
        assert len(all_templates) >= 6

    def test_get_registry_has_factory_category(self):
        reg = get_registry()
        factory_templates = reg.list_by_category(TemplateCategory.FACTORY)
        assert len(factory_templates) >= 1
