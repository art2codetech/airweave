"""Redmine source implementation for syncing projects and issues."""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import RedmineAuthConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.redmine import RedmineIssueEntity, RedmineProjectEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod


@source(
    name="Redmine",
    short_name="redmine",
    auth_methods=[AuthenticationMethod.DIRECT],
    auth_config_class="RedmineAuthConfig",
    config_class="RedmineConfig",
    labels=["Project Management", "Issues"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class RedmineSource(BaseSource):
    """Redmine source connector integrates with the Redmine REST API.

    Synchronizes projects and issues for Redmine instances using API key authentication.
    """

    REDMINE_API_LIMIT = 100

    def __init__(self):
        """Initialize Redmine source."""
        super().__init__()
        self._api_key: Optional[str] = None
        self.base_url: str = ""
        self.project_identifier: str = ""
        self.include_closed: bool = False

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @classmethod
    async def create(
        cls, credentials: RedmineAuthConfig, config: Optional[Dict[str, Any]] = None
    ) -> "RedmineSource":
        """Create a new Redmine source instance."""
        instance = cls()
        instance._api_key = credentials.api_key

        if config:
            instance.base_url = (config.get("base_url") or "").strip().rstrip("/")
            instance.project_identifier = (config.get("project_identifier") or "").strip()
            instance.include_closed = bool(config.get("include_closed", False))
        else:
            instance.base_url = ""
            instance.project_identifier = ""
            instance.include_closed = False

        if not instance.base_url:
            raise ValueError("Redmine base_url is required")

        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        headers = {"X-Redmine-API-Key": self._api_key}
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    async def _get_paginated_results(
        self,
        client: httpx.AsyncClient,
        url: str,
        root_key: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if params is None:
            params = {}
        params = dict(params)
        params["limit"] = self.REDMINE_API_LIMIT

        results: List[Dict[str, Any]] = []
        offset = 0

        while True:
            params["offset"] = offset
            payload = await self._get_with_auth(client, url, params)
            batch = payload.get(root_key, [])
            results.extend(batch)

            total = payload.get("total_count", len(results))
            offset += payload.get("limit", self.REDMINE_API_LIMIT)
            if offset >= total:
                break

        return results

    async def _get_projects(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/projects.json"
        projects = await self._get_paginated_results(client, url, "projects")

        if self.project_identifier:
            filtered = [
                project
                for project in projects
                if project.get("identifier") == self.project_identifier
            ]
            if not filtered:
                raise ValueError(
                    f"Project identifier '{self.project_identifier}' not found in Redmine."
                )
            return filtered

        return projects

    async def _get_project_issues(
        self, client: httpx.AsyncClient, project_id: str
    ) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/issues.json"
        params: Dict[str, Any] = {"project_id": project_id}
        if self.include_closed:
            params["status_id"] = "*"
        return await self._get_paginated_results(client, url, "issues", params)

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate project and issue entities from Redmine."""
        async with self.http_client() as client:
            projects = await self._get_projects(client)

            for project in projects:
                project_entity = RedmineProjectEntity(
                    breadcrumbs=[],
                    project_id=str(project["id"]),
                    identifier=project.get("identifier", ""),
                    name=project.get("name", ""),
                    description=project.get("description"),
                    status=str(project.get("status")) if project.get("status") else None,
                    web_url_value=(
                        f"{self.base_url}/projects/{project.get('identifier')}"
                        if project.get("identifier")
                        else None
                    ),
                )
                yield project_entity

                project_breadcrumb = Breadcrumb(
                    entity_id=str(project_entity.project_id),
                    name=project_entity.name,
                    entity_type=RedmineProjectEntity.__name__,
                )

                issues = await self._get_project_issues(client, str(project["id"]))
                for issue in issues:
                    project_data = issue.get("project", {})
                    status = issue.get("status", {})
                    tracker = issue.get("tracker", {})
                    priority = issue.get("priority", {})
                    author = issue.get("author", {})
                    assigned_to = issue.get("assigned_to", {})

                    issue_entity = RedmineIssueEntity(
                        breadcrumbs=[project_breadcrumb],
                        issue_id=str(issue["id"]),
                        subject=issue.get("subject", ""),
                        description=issue.get("description"),
                        status=status.get("name"),
                        tracker=tracker.get("name"),
                        priority=priority.get("name"),
                        author=author.get("name"),
                        assignee=assigned_to.get("name"),
                        project_id=str(project_data.get("id", project.get("id"))),
                        project_identifier=project.get("identifier"),
                        created_time=self._parse_datetime(issue.get("created_on"))
                        or datetime.utcnow(),
                        updated_time=self._parse_datetime(issue.get("updated_on"))
                        or self._parse_datetime(issue.get("created_on"))
                        or datetime.utcnow(),
                        web_url_value=f"{self.base_url}/issues/{issue.get('id')}",
                    )
                    yield issue_entity

    async def validate(self) -> bool:
        """Verify Redmine API key by pinging the /users/current endpoint."""
        try:
            async with self.http_client() as client:
                await self._get_with_auth(client, f"{self.base_url}/users/current.json")
            return True
        except Exception as e:
            self.logger.error(f"Redmine validation failed: {e}")
            return False
