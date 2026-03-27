""""SwissKiss Manual Loader Bot v2.0"""
from __future__ import annotations

import os, re, json, yaml, shutil, subprocess
try:
    import tomllib
except ModuleNotFoundError:  # Python <3.11 fallback
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List

REGISTRY_FILE = "module_registry.yaml"
MODULES_DIR = Path("./modules")
MODULES_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_LICENSES = {"MIT", "BSD", "Apache", "Apache-2.0", "ISC", "Unlicense", "CC0"}

class SwissKissLoader:
    """
    SwissKiss Manual Loader Bot v2.0
    - Manual repo load (clone or local path)
    - Module YAML generation
    - Registry w/ rank_1 / rank_2 preference per category
    - License + reqs + language audit
    - Basic risk heuristics (network/exec calls)
    - Roll-call support for orchestration
    - Handoff artifacts for AnalysisBot + CommissioningBot
    """
    def __init__(self):
        self.registry_path = Path(REGISTRY_FILE)
        self.registry = self.load_registry()

    # ---------- registry ----------
    def load_registry(self):
        if not self.registry_path.exists():
            return {}
        with open(self.registry_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save_registry(self):
        with open(self.registry_path, "w", encoding="utf-8") as f:
            yaml.dump(self.registry, f, default_flow_style=False)

    # ---------- repos -------------
    def clone_repo(self, url_or_path: str) -> Path:
        """
        If url_or_path is a git URL -> clone; if it's a local dir -> copy into modules.
        """
        name = str(url_or_path).rstrip("/").split("/")[-1]
        repo_path = MODULES_DIR / name
        if repo_path.exists():
            return repo_path

        if str(url_or_path).startswith(("http://", "https://", "git@")):
            subprocess.run(["git", "clone", str(url_or_path), str(repo_path)], check=True)
        else:
            src = Path(url_or_path)
            if not src.exists():
                raise FileNotFoundError(f"Source not found: {url_or_path}")
            shutil.copytree(src, repo_path)
        return repo_path

    def analyze_module(self, repo_path: Path) -> str:
        readme = repo_path / "README.md"
        if readme.exists():
            with open(readme, "r", encoding="utf-8") as f:
                return "\n".join(f.read().splitlines()[:10]) or "README present but empty."
        return "No README found."

    def detect_license(self, repo_path: Path) -> str:
        for fname in ["LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING"]:
            p = repo_path / fname
            if p.exists():
                txt = p.read_text(encoding="utf-8", errors="ignore")
                for key in ALLOWED_LICENSES | {"GPL", "LGPL", "AGPL", "MPL"}:
                    if key.lower() in txt.lower():
                        return key
                return "UNKNOWN"
        return "MISSING"

    def parse_requirements(self, repo_path: Path) -> list:
        reqs = []
        for fname in ["requirements.txt", "pyproject.toml", "package.json"]:
            p = repo_path / fname
            if p.exists():
                reqs.append({"file": fname, "size": p.stat().st_size})
        return reqs

    def extract_dependencies(self, repo_path: Path) -> dict:
        """Extract dependency details for Python and Node ecosystems."""
        deps = {"python": [], "node": [], "errors": []}

        def add_python_dep(name: str, spec: str, source: str) -> None:
            entry = {"name": name, "spec": spec, "source": source}
            deps["python"].append(entry)

        def add_node_dep(name: str, version: str, source: str) -> None:
            deps["node"].append({"name": name, "spec": version, "source": source})

        req_file = repo_path / "requirements.txt"
        if req_file.exists():
            for line in req_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                item = line.strip()
                if not item or item.startswith("#") or item.startswith("-"):
                    continue
                spec = item.split("#", 1)[0].strip()
                name = re.split(r"[<=>!~]", spec, 1)[0].strip()
                constraint = spec[len(name):].strip()
                add_python_dep(name, constraint, "requirements.txt")

        pyproject = repo_path / "pyproject.toml"
        if pyproject.exists():
            try:
                if tomllib is None:
                    raise ModuleNotFoundError(
                        "Cannot parse pyproject.toml: requires Python 3.11+ or tomli (pip install tomli)"
                    )
                data = tomllib.loads(pyproject.read_text(encoding="utf-8", errors="ignore"))
                project_deps = data.get("project", {}).get("dependencies", [])
                for dep in project_deps:
                    name = re.split(r"[<=>!~]", dep, 1)[0].strip()
                    constraint = dep[len(name):].strip()
                    add_python_dep(name, constraint, "pyproject.toml")
                poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
                for name, version in poetry_deps.items():
                    if name.lower() != "python":
                        if isinstance(version, str):
                            add_python_dep(name, version, "pyproject.toml")
                        elif isinstance(version, dict):
                            spec = version.get("version", "")
                            # Poetry dependency specs may be dictionaries; preserve metadata like extras, optional, markers, path, git.
                            metadata = {k: v for k, v in version.items() if k != "version"}
                            deps["python"].append({
                                "name": name,
                                "spec": spec,
                                "source": "pyproject.toml",
                                "metadata": metadata
                            })
            except Exception as exc:
                deps["errors"].append(f"pyproject.toml parse error: {exc}")

        package_json = repo_path / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text(encoding="utf-8", errors="ignore"))
                for section in ("dependencies", "devDependencies"):
                    for name, version in data.get(section, {}).items():
                        add_node_dep(name, version, f"package.json:{section}")
            except Exception as exc:
                deps["errors"].append(f"package.json parse error: {exc}")

        return deps

    def detect_languages(self, repo_path: Path) -> dict:
        counts: Dict[str, int] = {}
        ext_map = {
            ".py":"Python",".js":"JavaScript",".ts":"TypeScript",".rs":"Rust",".go":"Go",
            ".java":"Java",".c":"C",".cpp":"C++",".hpp":"C++",".cs":"C#",".php":"PHP",
            ".rb":"Ruby",".sh":"Shell",".swift":"Swift",".kt":"Kotlin",".m":"Objective-C",
            ".scala":"Scala",".r":"R",".jl":"Julia",".lua":"Lua"
        }
        for p in repo_path.rglob("*"):
            if p.is_file():
                lang = ext_map.get(p.suffix)
                if lang:
                    counts[lang] = counts.get(lang, 0) + 1
        return counts

    def risk_scan(self, repo_path: Path) -> dict:
        risky_patterns = [
            r"subprocess\.run", r"os\.system", r"eval\(", r"exec\(",
            r"requests\.(get|post)\(", r"socket\.", r"paramiko\.",
            r"child_process\.exec", r"fs\.unlink", r"rm -rf"
        ]
        hits = []
        for p in repo_path.rglob("*"):
            if p.is_file() and p.suffix in {".py", ".js", ".sh"} and p.stat().st_size < 1_000_000:
                try:
                    txt = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for pat in risky_patterns:
                    for m in re.finditer(pat, txt):
                        hits.append({"file": str(p), "pattern": pat, "pos": m.start()})
        return {"issues": hits, "count": len(hits)}

    def create_module_yaml(self, name, category, description, entry_script):
        module = {
            "module_name": name,
            "category": category,
            "entry_script": entry_script or "<define-entry-script>",
            "description": description,
            "inputs": [],
            "outputs": [],
            "test_command": None,
            "observer_required": False,
        }
        mod_dir = MODULES_DIR / name
        mod_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = mod_dir / "module.yaml"
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(module, f)
        return module

    def write_audit(self, repo_path: Path, audit: dict) -> Path:
        audit_path = repo_path / "audit.json"
        audit["timestamp"] = datetime.now(timezone.utc).isoformat() + "Z"
        audit_path.write_text(json.dumps(audit, indent=2))
        return audit_path

    def manual_load(self, url, category, entry_script=None):
        name = str(url).rstrip("/").split("/")[-1]
        repo_path = self.clone_repo(url)
        summary = self.analyze_module(repo_path)
        license_name = self.detect_license(repo_path)
        reqs = self.parse_requirements(repo_path)
        deps = self.extract_dependencies(repo_path)
        langs = self.detect_languages(repo_path)
        risk = self.risk_scan(repo_path)

        # registry with rank selection
        self.registry.setdefault(category, {"rank_1": None, "rank_2": None})
        if self.registry[category]["rank_1"] is None:
            self.registry[category]["rank_1"] = name
        elif self.registry[category]["rank_2"] is None and self.registry[category]["rank_1"] != name:
            self.registry[category]["rank_2"] = name

        module = self.create_module_yaml(name, category, summary, entry_script)
        self.save_registry()

        audit = {
            "module": name,
            "category": category,
            "license": license_name,
            "license_ok": license_name in ALLOWED_LICENSES,
            "requirements": reqs,
            "dependencies": deps,
            "languages": langs,
            "risk_scan": risk,
            "summary": summary
        }
        self.write_audit(repo_path, audit)
        return {"module": module, "audit": audit}

    # ---------- orchestration ----------
    def respond_to_roll_call(self, task_description: str) -> dict:
        # naive category guess
        cat = "general"
        td = task_description.lower()
        if any(k in td for k in ["vision","opencv","image"]): cat = "computer-vision"
        if any(k in td for k in ["robot","motor","servo"]): cat = "robotics"
        if any(k in td for k in ["nlp","text","language"]): cat = "nlp"
        suggestion = self.registry.get(cat, {})
        return {
            "can_help": True,
            "confidence": 0.88,
            "suggested_subtask": f"Load/attach top-ranked module for category '{cat}'.",
            "category": cat,
            "candidate": suggestion
        }

    def suggest_modules(self, category: str) -> list:
        entry = self.registry.get(category)
        if not entry:
            return []
        return [entry.get("rank_1"), entry.get("rank_2")]

    def handoff_for_analysis(self, module_name: str) -> dict:
        """Package key metadata for AnalysisBot."""
        repo_path = MODULES_DIR / module_name
        return {
            "module": module_name,
            "readme": (repo_path/"README.md").read_text(encoding="utf-8", errors="ignore")[:2000] if (repo_path/"README.md").exists() else "",
            "audit": json.loads((repo_path/"audit.json").read_text()) if (repo_path/"audit.json").exists() else {},
            "module_yaml": yaml.safe_load((repo_path/"module.yaml").read_text()) if (repo_path/"module.yaml").exists() else {},
        }

    def handoff_for_commissioning(self, module_name: str) -> dict:
        """Create a commissioning request structure to validate module quality."""
        repo_path = MODULES_DIR / module_name
        return {
            "task_id": f"commission_{module_name}",
            "target_bot": "SwissKissLoader",
            "input_parameters": {
                "module_name": module_name,
                "audit_path": str(repo_path / "audit.json"),
                "module_yaml": str(repo_path / "module.yaml"),
            },
            "expected_outcomes": {
                "license_ok": True,
                "risk_scan.count": "<= 3"
            }
        }
