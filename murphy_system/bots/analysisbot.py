"""AnalysisBot - A high-level cognitive bot for scope detection and multi-source troubleshooting."""
from __future__ import annotations

import json
import requests
import datetime
from typing import Any, List, Dict
from .gpt_oss_runner import GPTOSSRunner
from .swisskiss_loader import load_github_module  # must be defined elsewhere


class AnalysisBot:
    def __init__(self, model_path: str = "./models/gpt-oss-20b") -> None:
        self.runner = GPTOSSRunner(model_path=model_path)
        self.sources: List[str] = []
        self.collected_insights: List[dict] = []

    def fetch_search_insights(self, query: str, sources: List[str]) -> List[str]:
        """Query external data sources (web APIs or databases) for overlapping knowledge."""
        results = []
        headers = {"User-Agent": "AnalysisBot/1.0"}
        for source in sources:
            try:
                res = requests.get(f"https://api.duckduckgo.com/?q={query}&format=json&no_redirect=1", headers=headers, timeout=5)
                data = res.json().get("RelatedTopics", [])
                snippets = [r["Text"] for r in data if "Text" in r]
                results.extend(snippets[:5])
            except Exception as e:
                results.append(f"[error: {str(e)}] from {source}")
        return results

    def analyze_scope(self, user_query: str) -> dict:
        """Extract relevant skills, bots, modules, or logic chains needed to fulfill a task."""
        sources = ["duckduckgo", "github", "pypi"]
        text_chunks = self.fetch_search_insights(user_query, sources)
        context = "\n".join(text_chunks)

        prompt = f"""
You are AnalysisBot.
Given the user inquiry and results from multiple web sources, infer the domain, required expertise, relevant bots, and execution chain.
Also recommend GitHub modules if applicable.

User Request: {user_query}

Multiple Independent Search Results:
{context}

Generate JSON in the format:
{{
  "domain": str,
  "required_bots": list[str],
  "recommended_modules": list[str],
  "skills_needed": list[str],
  "sensor_inputs": list[str],
  "complexity_estimate": str
}}
"""
        response = self.runner.chat(prompt, stop_token="}")
        try:
            return json.loads(response + "}")
        except Exception as e:
            return {"error": str(e), "raw": response}

    def fetch_module_knowledge(self, topic: str) -> dict:
        """Try to load task-specific GitHub modules using SwissKiss."""
        try:
            return load_github_module(topic)
        except Exception as e:
            return {"error": f"SwissKiss module load failed: {e}"}

    def propose_scope_profile(self, query: str) -> dict:
        """End-to-end: learns from multiple overlapping sources to propose task scope."""
        scope_data = self.analyze_scope(query)
        if isinstance(scope_data, dict) and scope_data.get("recommended_modules"):
            loaded_modules = [self.fetch_module_knowledge(mod) for mod in scope_data["recommended_modules"]]
            scope_data["module_previews"] = loaded_modules
        scope_data["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.collected_insights.append(scope_data)
        return scope_data