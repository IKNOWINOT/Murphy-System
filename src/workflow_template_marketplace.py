"""
Workflow Template Marketplace — package, publish, search, install, rate,
and version community workflow templates.

Implements RECOMMENDATIONS.md Section 6.2.2.
"""

import hashlib
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TemplateCategory(str):
    """Template category (str subclass)."""
    pass


CATEGORIES = [
    "data_pipeline", "ci_cd", "incident_response", "customer_service",
    "hr_onboarding", "marketing_automation", "financial_reporting",
    "security_compliance", "devops", "content_management", "general",
]


class WorkflowTemplateMarketplace:
    """
    Marketplace for workflow templates enabling packaging, publishing,
    searching, installing, rating, and versioning of community templates.
    """

    def __init__(self):
        self._templates: Dict[str, Dict[str, Any]] = {}
        self._installed: Dict[str, Dict[str, Any]] = {}
        self._ratings: Dict[str, List[Dict[str, Any]]] = {}
        self._downloads: Dict[str, int] = {}
        self._lock = threading.RLock()

    def publish_template(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """Publish a workflow template to the marketplace."""
        required = ["name", "version", "author", "description", "category", "steps"]
        errors = []
        for field in required:
            if field not in template:
                errors.append(f"Missing required field: {field}")
        if errors:
            return {"published": False, "errors": errors}

        name = template["name"]
        category = template.get("category", "general")
        if category not in CATEGORIES:
            return {"published": False, "errors": [f"Invalid category '{category}'. Must be one of: {CATEGORIES}"]}

        template_id = hashlib.sha256(
            f"{name}:{template['version']}".encode()
        ).hexdigest()[:12]

        with self._lock:
            if name in self._templates:
                existing = self._templates[name]
                if existing["version"] == template["version"]:
                    return {"published": False, "errors": ["Version already published"]}
                existing["version_history"].append({
                    "version": existing["version"],
                    "published_at": existing["published_at"],
                })

            entry = {
                "template_id": template_id,
                "name": name,
                "version": template["version"],
                "author": template["author"],
                "description": template["description"],
                "category": category,
                "steps": template["steps"],
                "tags": template.get("tags", []),
                "config_schema": template.get("config_schema", {}),
                "published_at": datetime.now(timezone.utc).isoformat(),
                "version_history": self._templates.get(name, {}).get("version_history", []),
            }
            self._templates[name] = entry
            if name not in self._downloads:
                self._downloads[name] = 0
            if name not in self._ratings:
                self._ratings[name] = []

        return {
            "published": True,
            "template_id": template_id,
            "name": name,
            "version": template["version"],
        }

    def search_templates(self, query: Optional[str] = None,
                         category: Optional[str] = None,
                         tags: Optional[List[str]] = None,
                         min_rating: float = 0.0,
                         sort_by: str = "relevance") -> List[Dict[str, Any]]:
        """Search marketplace templates."""
        with self._lock:
            results = []
            for name, tmpl in self._templates.items():
                score = 0.0
                if query:
                    q = query.lower()
                    if q in tmpl["name"].lower():
                        score += 3.0
                    if q in tmpl["description"].lower():
                        score += 2.0
                    tag_match = sum(1 for t in tmpl.get("tags", []) if q in t.lower())
                    score += tag_match
                    if score == 0:
                        continue
                else:
                    score = 1.0

                if category and tmpl["category"] != category:
                    continue

                if tags:
                    tmpl_tags = set(tmpl.get("tags", []))
                    if not any(t in tmpl_tags for t in tags):
                        continue

                avg_rating = self._avg_rating(name)
                if avg_rating < min_rating:
                    continue

                results.append({
                    "name": name,
                    "version": tmpl["version"],
                    "author": tmpl["author"],
                    "description": tmpl["description"],
                    "category": tmpl["category"],
                    "tags": tmpl.get("tags", []),
                    "rating": round(avg_rating, 2),
                    "downloads": self._downloads.get(name, 0),
                    "relevance_score": round(score, 2),
                })

            if sort_by == "rating":
                results.sort(key=lambda r: r["rating"], reverse=True)
            elif sort_by == "downloads":
                results.sort(key=lambda r: r["downloads"], reverse=True)
            else:
                results.sort(key=lambda r: r["relevance_score"], reverse=True)

            return results

    def install_template(self, template_name: str,
                         config: Optional[Dict] = None) -> Dict[str, Any]:
        """Install a template from the marketplace."""
        with self._lock:
            if template_name not in self._templates:
                return {"installed": False, "error": f"Template '{template_name}' not found"}

            tmpl = self._templates[template_name]
            self._installed[template_name] = {
                "name": template_name,
                "version": tmpl["version"],
                "installed_at": datetime.now(timezone.utc).isoformat(),
                "config": config or {},
                "steps": list(tmpl["steps"]),
            }
            self._downloads[template_name] = self._downloads.get(template_name, 0) + 1

        return {
            "installed": True,
            "name": template_name,
            "version": tmpl["version"],
            "step_count": len(tmpl["steps"]),
        }

    def uninstall_template(self, template_name: str) -> Dict[str, Any]:
        with self._lock:
            if template_name not in self._installed:
                return {"uninstalled": False, "error": f"Template '{template_name}' not installed"}
            del self._installed[template_name]
        return {"uninstalled": True, "name": template_name}

    def rate_template(self, template_name: str, rating: float,
                      reviewer: str, comment: str = "") -> Dict[str, Any]:
        """Rate a marketplace template (1-5 stars)."""
        if not 1.0 <= rating <= 5.0:
            return {"rated": False, "error": "Rating must be between 1.0 and 5.0"}

        with self._lock:
            if template_name not in self._templates:
                return {"rated": False, "error": f"Template '{template_name}' not found"}

            if template_name not in self._ratings:
                self._ratings[template_name] = []

            self._ratings[template_name].append({
                "rating": rating,
                "reviewer": reviewer,
                "comment": comment,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return {
            "rated": True,
            "name": template_name,
            "your_rating": rating,
            "avg_rating": round(self._avg_rating(template_name), 2),
            "total_ratings": len(self._ratings[template_name]),
        }

    def get_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get full template details."""
        with self._lock:
            if template_name not in self._templates:
                return None
            tmpl = dict(self._templates[template_name])
            tmpl["rating"] = round(self._avg_rating(template_name), 2)
            tmpl["total_ratings"] = len(self._ratings.get(template_name, []))
            tmpl["downloads"] = self._downloads.get(template_name, 0)
            tmpl["installed"] = template_name in self._installed
            return tmpl

    def list_installed(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "name": name,
                    "version": info["version"],
                    "installed_at": info["installed_at"],
                    "step_count": len(info["steps"]),
                }
                for name, info in self._installed.items()
            ]

    def list_categories(self) -> List[str]:
        return list(CATEGORIES)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "module": "workflow_template_marketplace",
                "total_templates": len(self._templates),
                "installed_templates": len(self._installed),
                "total_downloads": sum(self._downloads.values()),
                "total_ratings": sum(len(r) for r in self._ratings.values()),
                "categories": CATEGORIES,
            }

    def _avg_rating(self, template_name: str) -> float:
        ratings = self._ratings.get(template_name, [])
        if not ratings:
            return 0.0
        return sum(r["rating"] for r in ratings) / len(ratings)
