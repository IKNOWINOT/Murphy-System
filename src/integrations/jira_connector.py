"""
Jira Integration — Murphy System World Model Connector.

Uses Jira Cloud REST API v3.
Required credentials: JIRA_API_TOKEN, JIRA_EMAIL, JIRA_BASE_URL
Setup: https://id.atlassian.com/manage-profile/security/api-tokens
"""
from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class JiraConnector(BaseIntegrationConnector):
    """Jira Cloud REST API v3 connector."""

    INTEGRATION_NAME = "Jira"
    BASE_URL = ""  # Overridden from JIRA_BASE_URL credential
    CREDENTIAL_KEYS = ["JIRA_API_TOKEN", "JIRA_EMAIL", "JIRA_BASE_URL"]
    REQUIRED_CREDENTIALS = ["JIRA_API_TOKEN", "JIRA_EMAIL"]
    FREE_TIER = True
    SETUP_URL = "https://id.atlassian.com/manage-profile/security/api-tokens"
    DOCUMENTATION_URL = "https://developer.atlassian.com/cloud/jira/platform/rest/v3/"

    def __init__(self, credentials=None, **kwargs):
        super().__init__(credentials=credentials, **kwargs)
        # Base URL comes from credentials
        base = (self._credentials.get("JIRA_BASE_URL") or "").rstrip("/")
        if base:
            self.BASE_URL = f"{base}/rest/api/3"

    def _build_headers(self) -> Dict[str, str]:
        email = self._credentials.get("JIRA_EMAIL", "")
        token = self._credentials.get("JIRA_API_TOKEN", "")
        encoded = base64.b64encode(f"{email}:{token}".encode()).decode()
        return {
            "Authorization": f"Basic {encoded}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # -- Projects --

    def list_projects(self, max_results: int = 50) -> Dict[str, Any]:
        return self._get("/project/search", params={"maxResults": min(max_results, 50)})

    def get_project(self, project_key: str) -> Dict[str, Any]:
        return self._get(f"/project/{project_key}")

    # -- Issues --

    def search_issues(self, jql: str, max_results: int = 50,
                      fields: Optional[List[str]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "jql": jql,
            "maxResults": min(max_results, 100),
        }
        if fields:
            payload["fields"] = fields
        return self._post("/issue/search", json=payload)

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        return self._get(f"/issue/{issue_key}")

    def create_issue(self, project_key: str, summary: str,
                     issue_type: str = "Task", description: str = "",
                     priority: Optional[str] = None,
                     assignee_id: Optional[str] = None) -> Dict[str, Any]:
        fields: Dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
        if description:
            fields["description"] = {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph",
                              "content": [{"type": "text", "text": description}]}],
            }
        if priority:
            fields["priority"] = {"name": priority}
        if assignee_id:
            fields["assignee"] = {"id": assignee_id}
        return self._post("/issue", json={"fields": fields})

    def update_issue(self, issue_key: str,
                     fields: Dict[str, Any]) -> Dict[str, Any]:
        return self._http("PUT", f"/issue/{issue_key}", json={"fields": fields})

    def transition_issue(self, issue_key: str,
                         transition_id: str) -> Dict[str, Any]:
        return self._post(f"/issue/{issue_key}/transitions",
                          json={"transition": {"id": transition_id}})

    def add_comment(self, issue_key: str, body: str) -> Dict[str, Any]:
        return self._post(f"/issue/{issue_key}/comment", json={
            "body": {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph",
                              "content": [{"type": "text", "text": body}]}],
            }
        })

    def get_transitions(self, issue_key: str) -> Dict[str, Any]:
        return self._get(f"/issue/{issue_key}/transitions")

    # -- Users --

    def get_current_user(self) -> Dict[str, Any]:
        return self._get("/myself")

    def search_users(self, query: str, max_results: int = 20) -> Dict[str, Any]:
        return self._get("/user/search",
                         params={"query": query, "maxResults": min(max_results, 50)})
