"""
Asana Project Management Integration — Murphy System World Model Connector.

Uses Asana REST API v1.
Required credentials: ASANA_ACCESS_TOKEN (personal access token)
Setup: https://developers.asana.com/docs/authentication-quick-start
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class AsanaConnector(BaseIntegrationConnector):
    """Asana REST API connector."""

    INTEGRATION_NAME = "Asana"
    BASE_URL = "https://app.asana.com/api/1.0"
    CREDENTIAL_KEYS = ["ASANA_ACCESS_TOKEN"]
    REQUIRED_CREDENTIALS = ["ASANA_ACCESS_TOKEN"]
    FREE_TIER = True
    SETUP_URL = "https://app.asana.com/0/developer-console"
    DOCUMENTATION_URL = "https://developers.asana.com/reference/rest-api-reference"

    def _build_headers(self) -> Dict[str, str]:
        token = self._credentials.get("ASANA_ACCESS_TOKEN", "")
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # -- Workspaces --

    def list_workspaces(self) -> Dict[str, Any]:
        return self._get("/workspaces")

    # -- Projects --

    def list_projects(self, workspace_gid: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if workspace_gid:
            params["workspace"] = workspace_gid
        return self._get("/projects", params=params)

    def get_project(self, project_gid: str) -> Dict[str, Any]:
        return self._get(f"/projects/{project_gid}")

    def create_project(self, workspace_gid: str, name: str,
                       notes: str = "", public: bool = False) -> Dict[str, Any]:
        return self._post("/projects", json={"data": {
            "workspace": workspace_gid,
            "name": name,
            "notes": notes,
            "public": public,
        }})

    # -- Tasks --

    def list_tasks(self, project_gid: str) -> Dict[str, Any]:
        return self._get(f"/projects/{project_gid}/tasks",
                         params={"opt_fields": "gid,name,completed,due_on,assignee,notes"})

    def get_task(self, task_gid: str) -> Dict[str, Any]:
        return self._get(f"/tasks/{task_gid}")

    def create_task(self, project_gid: str, name: str, notes: str = "",
                    due_on: Optional[str] = None,
                    assignee: Optional[str] = None) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "name": name,
            "notes": notes,
            "projects": [project_gid],
        }
        if due_on:
            data["due_on"] = due_on
        if assignee:
            data["assignee"] = assignee
        return self._post("/tasks", json={"data": data})

    def update_task(self, task_gid: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        return self._http("PUT", f"/tasks/{task_gid}", json={"data": updates})

    def complete_task(self, task_gid: str) -> Dict[str, Any]:
        return self.update_task(task_gid, {"completed": True})

    def delete_task(self, task_gid: str) -> Dict[str, Any]:
        return self._delete(f"/tasks/{task_gid}")

    def add_comment(self, task_gid: str, text: str) -> Dict[str, Any]:
        return self._post(f"/tasks/{task_gid}/stories", json={"data": {"text": text}})

    def assign_task(self, task_gid: str, assignee_gid: str) -> Dict[str, Any]:
        return self.update_task(task_gid, {"assignee": assignee_gid})

    # -- Sections --

    def list_sections(self, project_gid: str) -> Dict[str, Any]:
        return self._get(f"/projects/{project_gid}/sections")

    def create_section(self, project_gid: str, name: str) -> Dict[str, Any]:
        return self._post(f"/projects/{project_gid}/sections", json={"data": {"name": name}})

    # -- Users / Teams --

    def get_current_user(self) -> Dict[str, Any]:
        return self._get("/users/me")

    def list_teams(self, workspace_gid: str) -> Dict[str, Any]:
        return self._get(f"/workspaces/{workspace_gid}/teams")

    # -- Search --

    def search_tasks(self, workspace_gid: str, text: str) -> Dict[str, Any]:
        return self._get(f"/workspaces/{workspace_gid}/tasks/search",
                         params={"text": text})

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self.get_current_user()
        result["integration"] = self.INTEGRATION_NAME
        return result
