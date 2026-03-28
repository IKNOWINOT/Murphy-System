"""
GitHub Integration — Murphy System World Model Connector.

Uses GitHub REST API v3.
Required credentials: GITHUB_TOKEN (personal access token or fine-grained PAT)
Setup: https://github.com/settings/tokens
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class GitHubConnector(BaseIntegrationConnector):
    """GitHub REST API v3 connector."""

    INTEGRATION_NAME = "GitHub"
    BASE_URL = "https://api.github.com"
    CREDENTIAL_KEYS = ["GITHUB_TOKEN"]
    REQUIRED_CREDENTIALS = ["GITHUB_TOKEN"]
    FREE_TIER = True
    SETUP_URL = "https://github.com/settings/tokens/new"
    DOCUMENTATION_URL = "https://docs.github.com/en/rest"

    def _build_headers(self) -> Dict[str, str]:
        token = self._credentials.get("GITHUB_TOKEN", "")
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    # -- Repositories --

    def list_repos(self, visibility: str = "all", per_page: int = 100) -> Dict[str, Any]:
        """List authenticated user's repos."""
        return self._get("/user/repos",
                         params={"visibility": visibility, "per_page": min(per_page, 100)})

    def get_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        return self._get(f"/repos/{owner}/{repo}")

    def create_repo(self, name: str, description: str = "",
                    private: bool = False, auto_init: bool = True) -> Dict[str, Any]:
        return self._post("/user/repos", json={
            "name": name, "description": description,
            "private": private, "auto_init": auto_init,
        })

    # -- Issues --

    def list_issues(self, owner: str, repo: str,
                    state: str = "open", per_page: int = 30) -> Dict[str, Any]:
        return self._get(f"/repos/{owner}/{repo}/issues",
                         params={"state": state, "per_page": min(per_page, 100)})

    def create_issue(self, owner: str, repo: str, title: str,
                     body: str = "", labels: Optional[List[str]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        return self._post(f"/repos/{owner}/{repo}/issues", json=payload)

    def close_issue(self, owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        return self._http("PATCH", f"/repos/{owner}/{repo}/issues/{issue_number}",
                          json={"state": "closed"})

    # -- Pull Requests --

    def list_pull_requests(self, owner: str, repo: str,
                           state: str = "open") -> Dict[str, Any]:
        return self._get(f"/repos/{owner}/{repo}/pulls", params={"state": state})

    def create_pull_request(self, owner: str, repo: str, title: str,
                            head: str, base: str, body: str = "") -> Dict[str, Any]:
        return self._post(f"/repos/{owner}/{repo}/pulls",
                          json={"title": title, "head": head, "base": base, "body": body})

    # -- Actions / Workflows --

    def list_workflows(self, owner: str, repo: str) -> Dict[str, Any]:
        return self._get(f"/repos/{owner}/{repo}/actions/workflows")

    def trigger_workflow(self, owner: str, repo: str, workflow_id: str,
                         ref: str = "main", inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._post(f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
                          json={"ref": ref, "inputs": inputs or {}})

    def list_workflow_runs(self, owner: str, repo: str,
                           workflow_id: str, per_page: int = 10) -> Dict[str, Any]:
        return self._get(f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs",
                         params={"per_page": min(per_page, 100)})

    # -- Releases --

    def list_releases(self, owner: str, repo: str) -> Dict[str, Any]:
        return self._get(f"/repos/{owner}/{repo}/releases")

    def create_release(self, owner: str, repo: str, tag_name: str,
                       name: str = "", body: str = "",
                       draft: bool = False, prerelease: bool = False) -> Dict[str, Any]:
        return self._post(f"/repos/{owner}/{repo}/releases", json={
            "tag_name": tag_name, "name": name, "body": body,
            "draft": draft, "prerelease": prerelease,
        })

    # -- User --

    def get_authenticated_user(self) -> Dict[str, Any]:
        return self._get("/user")

    def search_code(self, query: str, per_page: int = 30) -> Dict[str, Any]:
        return self._get("/search/code",
                         params={"q": query, "per_page": min(per_page, 100)})
