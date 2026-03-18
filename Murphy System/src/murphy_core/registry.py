from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .contracts import EffectiveCapability, ModuleRecord, ModuleStatus


class ModuleRegistry:
    """Merged registry over baseline inventory, manifest metadata, file existence, and runtime usage."""

    def __init__(self) -> None:
        self._root = Path(__file__).resolve().parent.parent.parent
        self._records: Dict[str, ModuleRecord] = {}
        self.reload()

    def reload(self) -> None:
        self._records = {}
        self._load_baseline()
        self._load_manifest()
        self._resolve_source_files()
        self._apply_core_defaults()

    def list(self) -> List[ModuleRecord]:
        return sorted(self._records.values(), key=lambda r: r.module_name)

    def get(self, module_name: str) -> Optional[ModuleRecord]:
        return self._records.get(module_name)

    def to_dicts(self) -> List[Dict[str, object]]:
        return [r.to_dict() for r in self.list()]

    def _ensure(self, module_name: str) -> ModuleRecord:
        if module_name not in self._records:
            self._records[module_name] = ModuleRecord(module_name=module_name)
        return self._records[module_name]

    def _load_baseline(self) -> None:
        baseline_path = self._root / "docs" / "capability_baseline.json"
        if not baseline_path.exists():
            return
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
        for module_name in data.get("modules", []):
            rec = self._ensure(module_name)
            rec.present_in_baseline = True

    def _load_manifest(self) -> None:
        manifest_path = self._root / "src" / "matrix_bridge" / "module_manifest.py"
        if not manifest_path.exists():
            return
        text = manifest_path.read_text(encoding="utf-8")
        marker = "ModuleEntry(\n        module=\""
        parts = text.split(marker)
        for part in parts[1:]:
            module_name = part.split("\"", 1)[0]
            rec = self._ensure(module_name)
            rec.present_in_manifest = True
            rec.source_path = f"src/{module_name}.py"
            # light-weight extraction from manifest text block
            block = marker + part.split("ModuleEntry(", 1)[0]
            for key, attr in [("commands=[", "commands"), ("persona=\"", "persona"), ("emits=[", "emits"), ("consumes=[", "consumes")]:
                try:
                    if attr == "persona":
                        rec.persona = block.split(key, 1)[1].split("\"", 1)[0]
                    else:
                        raw = block.split(key, 1)[1].split("]", 1)[0]
                        items = [x.strip().strip('"') for x in raw.split(",") if x.strip()]
                        setattr(rec, attr, items)
                except Exception:
                    pass

    def _resolve_source_files(self) -> None:
        src_dir = self._root / "src"
        for rec in self._records.values():
            candidate_py = src_dir / f"{rec.module_name}.py"
            candidate_pkg = src_dir / rec.module_name / "__init__.py"
            if candidate_py.exists():
                rec.source_exists = True
                rec.source_path = str(candidate_py.relative_to(self._root))
            elif candidate_pkg.exists():
                rec.source_exists = True
                rec.source_path = str(candidate_pkg.parent.relative_to(self._root))
            else:
                rec.source_exists = False
                if rec.present_in_manifest or rec.present_in_baseline:
                    rec.notes.append("declared but source file not verified")

    def _apply_core_defaults(self) -> None:
        core_modules = {
            "murphy_core": ModuleStatus.CORE,
            "runtime": ModuleStatus.ADAPTER,
            "control_plane_separation": ModuleStatus.ADAPTER,
            "deterministic_routing_engine": ModuleStatus.ADAPTER,
            "ai_workflow_generator": ModuleStatus.ADAPTER,
            "self_codebase_swarm": ModuleStatus.ADAPTER,
            "visual_swarm_builder": ModuleStatus.ADAPTER,
            "event_backbone": ModuleStatus.OPTIONAL,
            "integration_bus": ModuleStatus.OPTIONAL,
            "security_plane": ModuleStatus.ADAPTER,
            "rosetta": ModuleStatus.DECLARED_ONLY,
        }
        for module_name, status in core_modules.items():
            rec = self._ensure(module_name)
            rec.status = status
            rec.used_by_runtime = module_name in {"runtime", "control_plane_separation", "deterministic_routing_engine", "ai_workflow_generator", "self_codebase_swarm"}
            if status == ModuleStatus.CORE:
                rec.effective_capability = EffectiveCapability.LIVE
            elif status == ModuleStatus.ADAPTER:
                rec.effective_capability = EffectiveCapability.AVAILABLE if rec.source_exists else EffectiveCapability.DRIFTED
            elif status == ModuleStatus.OPTIONAL:
                rec.effective_capability = EffectiveCapability.AVAILABLE if rec.source_exists else EffectiveCapability.MISSING_DEPENDENCY
            elif status == ModuleStatus.DECLARED_ONLY:
                rec.effective_capability = EffectiveCapability.DRIFTED if not rec.source_exists else EffectiveCapability.NOT_WIRED

        for rec in self._records.values():
            if rec.status == ModuleStatus.DECLARED_ONLY and rec.source_exists:
                rec.effective_capability = EffectiveCapability.NOT_WIRED
            elif rec.status == ModuleStatus.DECLARED_ONLY and (rec.present_in_baseline or rec.present_in_manifest):
                rec.effective_capability = EffectiveCapability.DRIFTED
