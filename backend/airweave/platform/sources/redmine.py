"""Redmine source implementation.

Connector that retrieves Projects, Issues, Wiki Pages, and Journals from a Redmine instance.

Supports Redmine 4.2.x and newer with API key authentication.

References:
    https://www.redmine.org/projects/redmine/wiki/Rest_api
    https://www.redmine.org/projects/redmine/wiki/Rest_Projects
    https://www.redmine.org/projects/redmine/wiki/Rest_Issues
    https://www.redmine.org/projects/redmine/wiki/Rest_WikiPages
"""

from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.redmine import (
    RedmineAttachmentEntity,
    RedmineIssueEntity,
    RedmineJournalEntity,
    RedmineProjectEntity,
    RedmineWikiPageEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod


@source(
    name="Redmine",
    short_name="redmine",
    auth_methods=[
        AuthenticationMethod.DIRECT,  # API key authentication
    ],
    oauth_type=None,
    auth_config_class=None,
    config_class="RedmineConfig",
    labels=["Project Management", "Issue Tracking"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.CONNECTION,  # Per-instance rate limiting
)
class RedmineSource(BaseSource):
    """Redmine source connector integrates with the Redmine REST API to extract project management data.

    Connects to your Redmine instance (self-hosted or cloud).

    It provides comprehensive access to projects, issues, wiki pages, and their
    relationships for agile development and issue tracking workflows.

    Supports Redmine 4.2.x and newer.
    """

    @classmethod
    async def create(cls, api_key: str, config: Optional[Dict[str, Any]] = None) -> "RedmineSource":
        """Create a new Redmine source instance.

        Args:
            api_key: Redmine API key for authentication
            config: Configuration dictionary with base_url, project_identifiers, etc.

        Returns:
            Configured RedmineSource instance
        """
        instance = cls()
        instance.api_key = api_key
        instance.config = config or {}

        # Validate base_url is provided
        if not instance.config.get("base_url"):
            raise ValueError("base_url is required in Redmine configuration")

        # Remove trailing slash from base_url if present
        instance.base_url = instance.config["base_url"].rstrip("/")

        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Any:
        """Make an authenticated GET request to the Redmine REST API.

        Args:
            client: HTTP client to use for the request
            url: Full URL to request

        Returns:
            JSON response data

        Raises:
            httpx.HTTPStatusError: On HTTP errors (401, 403, 404, etc.)
        """
        self.logger.debug(f"Making authenticated request to {url}")

        headers = {
            "X-Redmine-API-Key": self.api_key,
            "Accept": "application/json",
        }

        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            self.logger.debug(f"Response status: {response.status_code}")
            return data
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            if e.response.status_code == 401:
                self.logger.error(
                    "Authentication failed. Please check your Redmine API key. "
                    "You can find your API key at: {base_url}/my/account (right sidebar)"
                )
            raise
        except Exception as e:
            self.logger.error(f"Request failed: {str(e)}")
            raise

    # ============================================================================
    # ENTITY CREATION METHODS
    # ============================================================================

    def _create_project_entity(self, project_data: Dict[str, Any]) -> RedmineProjectEntity:
        """Transform raw project data into a RedmineProjectEntity.

        Args:
            project_data: Project data from Redmine API

        Returns:
            RedmineProjectEntity instance
        """
        self.logger.debug(
            f"Creating project entity for: {project_data.get('identifier')} - {project_data.get('name')}"
        )

        entity_id = f"project-{project_data['id']}"

        # Handle parent project
        parent_id = None
        parent = project_data.get("parent")
        if parent:
            parent_id = parent.get("id") if isinstance(parent, dict) else parent

        return RedmineProjectEntity(
            # Base fields
            entity_id=entity_id,
            breadcrumbs=[],  # Projects are top-level
            name=project_data.get("name") or project_data["identifier"],
            created_at=project_data.get("created_on"),
            updated_at=project_data.get("updated_on"),
            # API fields
            project_id=project_data["id"],
            identifier=project_data["identifier"],
            description=project_data.get("description"),
            homepage=project_data.get("homepage"),
            is_public=project_data.get("is_public"),
            parent_id=parent_id,
            status=project_data.get("status"),
        )

    def _create_issue_entity(
        self, issue_data: Dict[str, Any], project: RedmineProjectEntity
    ) -> RedmineIssueEntity:
        """Transform raw issue data into a RedmineIssueEntity.

        Args:
            issue_data: Issue data from Redmine API
            project: Parent project entity

        Returns:
            RedmineIssueEntity instance
        """
        entity_id = f"issue-{issue_data['id']}"

        # Extract nested data safely
        project_info = issue_data.get("project", {})
        tracker_info = issue_data.get("tracker", {})
        status_info = issue_data.get("status", {})
        priority_info = issue_data.get("priority", {})
        author_info = issue_data.get("author", {})
        assigned_to_info = issue_data.get("assigned_to", {})

        project_name = project_info.get("name") if isinstance(project_info, dict) else None
        tracker_name = tracker_info.get("name") if isinstance(tracker_info, dict) else None
        status_name = status_info.get("name") if isinstance(status_info, dict) else None
        priority_name = priority_info.get("name") if isinstance(priority_info, dict) else None
        author = author_info.get("name") if isinstance(author_info, dict) else None
        assigned_to = assigned_to_info.get("name") if isinstance(assigned_to_info, dict) else None

        self.logger.debug(
            f"Creating issue entity: #{issue_data['id']} - {issue_data.get('subject')}"
        )

        return RedmineIssueEntity(
            # Base fields
            entity_id=entity_id,
            breadcrumbs=[
                Breadcrumb(
                    entity_id=project.entity_id,
                    name=project.name,
                    entity_type=project.__class__.__name__,
                )
            ],
            name=issue_data.get("subject") or f"Issue #{issue_data['id']}",
            created_at=issue_data.get("created_on"),
            updated_at=issue_data.get("updated_on"),
            # API fields
            issue_id=issue_data["id"],
            subject=issue_data.get("subject", ""),
            description=issue_data.get("description"),
            project_id=project.project_id,
            project_name=project_name,
            tracker_name=tracker_name,
            status_name=status_name,
            priority_name=priority_name,
            assigned_to=assigned_to,
            author=author,
            start_date=issue_data.get("start_date"),
            due_date=issue_data.get("due_date"),
            done_ratio=issue_data.get("done_ratio"),
            estimated_hours=issue_data.get("estimated_hours"),
            spent_hours=issue_data.get("spent_hours"),
            closed_on=issue_data.get("closed_on"),
        )

    def _create_wiki_page_entity(
        self,
        wiki_data: Dict[str, Any],
        project_id: int,
        project_name: str,
        project_entity_id: str,
    ) -> RedmineWikiPageEntity:
        """Transform raw wiki page data into a RedmineWikiPageEntity.

        Args:
            wiki_data: Wiki page data from Redmine API
            project_id: ID of the parent project
            project_name: Name of the parent project
            project_entity_id: Entity ID of the parent project

        Returns:
            RedmineWikiPageEntity instance
        """
        title = wiki_data.get("title", "")
        entity_id = f"wiki-{project_id}-{title}"

        # Extract author name safely
        author_info = wiki_data.get("author", {})
        author = author_info.get("name") if isinstance(author_info, dict) else None

        self.logger.debug(f"Creating wiki page entity: {title}")

        return RedmineWikiPageEntity(
            # Base fields
            entity_id=entity_id,
            breadcrumbs=[
                Breadcrumb(
                    entity_id=project_entity_id,
                    name=project_name,
                    entity_type=RedmineProjectEntity.__name__,
                )
            ],
            name=title,
            created_at=wiki_data.get("created_on"),
            updated_at=wiki_data.get("updated_on"),
            # API fields
            title=title,
            text=wiki_data.get("text", ""),
            version=wiki_data.get("version"),
            author=author,
            comments=wiki_data.get("comments"),
            project_id=project_id,
            project_name=project_name,
        )

    def _create_journal_entity(
        self, journal_data: Dict[str, Any], issue_id: int, issue_entity_id: str
    ) -> RedmineJournalEntity:
        """Transform raw journal data into a RedmineJournalEntity.

        Args:
            journal_data: Journal entry data from Redmine API
            issue_id: ID of the parent issue
            issue_entity_id: Entity ID of the parent issue

        Returns:
            RedmineJournalEntity instance
        """
        journal_id = journal_data["id"]
        entity_id = f"journal-{journal_id}"

        # Extract author name safely
        user_info = journal_data.get("user", {})
        author = user_info.get("name") if isinstance(user_info, dict) else None

        notes = journal_data.get("notes", "")

        # Create name from notes preview or indicate it's a change log
        if notes:
            name = notes[:50] + "..." if len(notes) > 50 else notes
        else:
            name = "Change log entry"

        self.logger.debug(f"Creating journal entity: {entity_id}")

        return RedmineJournalEntity(
            # Base fields
            entity_id=entity_id,
            breadcrumbs=[
                Breadcrumb(
                    entity_id=issue_entity_id,
                    name=f"Issue #{issue_id}",
                    entity_type=RedmineIssueEntity.__name__,
                )
            ],
            name=name,
            created_at=journal_data.get("created_on"),
            updated_at=None,  # Journals don't update
            # API fields
            journal_id=journal_id,
            notes=notes,
            issue_id=issue_id,
            author=author,
        )

    def _create_attachment_entity(
        self, attachment_data: Dict[str, Any], issue_id: int, issue_entity_id: str
    ) -> RedmineAttachmentEntity:
        """Transform raw attachment data into a RedmineAttachmentEntity.

        Args:
            attachment_data: Attachment data from Redmine API
            issue_id: ID of the parent issue
            issue_entity_id: Entity ID of the parent issue

        Returns:
            RedmineAttachmentEntity instance
        """
        attachment_id = attachment_data["id"]
        entity_id = f"attachment-{attachment_id}"

        # Extract author name safely
        author_info = attachment_data.get("author", {})
        author = author_info.get("name") if isinstance(author_info, dict) else None

        filename = attachment_data.get("filename", "")

        self.logger.debug(f"Creating attachment entity: {filename}")

        return RedmineAttachmentEntity(
            # Base fields
            entity_id=entity_id,
            breadcrumbs=[
                Breadcrumb(
                    entity_id=issue_entity_id,
                    name=f"Issue #{issue_id}",
                    entity_type=RedmineIssueEntity.__name__,
                )
            ],
            name=filename,
            created_at=attachment_data.get("created_on"),
            updated_at=None,  # Attachments don't update
            # API fields
            attachment_id=attachment_id,
            filename=filename,
            filesize=attachment_data.get("filesize"),
            content_type=attachment_data.get("content_type"),
            description=attachment_data.get("description"),
            content_url=attachment_data.get("content_url"),
            author=author,
            issue_id=issue_id,
        )

    # ============================================================================
    # ENTITY GENERATION METHODS
    # ============================================================================

    async def _generate_project_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[RedmineProjectEntity, None]:
        """Generate RedmineProjectEntity objects with pagination.

        Args:
            client: HTTP client to use for requests

        Yields:
            RedmineProjectEntity instances
        """
        self.logger.info("Starting project entity generation")

        # Get project filter from config (optional)
        project_identifiers_filter = (
            self.config.get("project_identifiers", []) if hasattr(self, "config") else []
        )

        if project_identifiers_filter:
            # Convert to set for faster lookup
            project_identifiers_set = set(
                identifier.lower() for identifier in project_identifiers_filter
            )
            self.logger.info(
                f"Project filter: will sync only projects with identifiers {project_identifiers_filter}"
            )
        else:
            project_identifiers_set = None
            self.logger.info("No project filter configured - syncing all accessible projects")

        # Pagination setup
        offset = 0
        limit = 100
        total_projects = 0
        filtered_projects = 0
        found_identifiers = set()

        while True:
            # Construct URL with pagination
            url = f"{self.base_url}/projects.json?offset={offset}&limit={limit}"
            self.logger.info(f"Fetching projects from offset {offset}")

            # Get project data
            data = await self._get_with_auth(client, url)
            projects = data.get("projects", [])
            total_count = data.get("total_count", 0)

            self.logger.info(f"Retrieved {len(projects)} projects (total available: {total_count})")

            # Process each project
            for project_data in projects:
                total_projects += 1
                identifier = project_data.get("identifier", "").lower()

                # Apply filter if configured
                if project_identifiers_set and identifier not in project_identifiers_set:
                    filtered_projects += 1
                    self.logger.debug(f"Skipping project {identifier} - not in filter list")
                    continue

                # Track which projects we found
                if project_identifiers_set:
                    found_identifiers.add(identifier)

                project_entity = self._create_project_entity(project_data)
                yield project_entity

            # Check if we've fetched all projects
            if offset + len(projects) >= total_count or len(projects) == 0:
                # Log summary
                matched_count = total_projects - filtered_projects

                if project_identifiers_set:
                    missing_identifiers = project_identifiers_set - found_identifiers
                    if missing_identifiers:
                        self.logger.warning(
                            f"⚠️ Some requested projects were not found: {sorted(missing_identifiers)}"
                        )

                    if matched_count == 0:
                        self.logger.error(
                            f"❌ No projects matched the filter! Requested: {project_identifiers_filter}"
                        )
                    else:
                        self.logger.info(
                            f"✅ Completed project sync: {matched_count} project(s) included "
                            f"({filtered_projects} filtered out)"
                        )
                else:
                    self.logger.info(f"✅ Completed project sync: {matched_count} project(s)")

                break

            # Move to next page
            offset += limit
            self.logger.debug(f"Moving to next page, offset={offset}")

    async def _generate_issue_entities(
        self, client: httpx.AsyncClient, project: RedmineProjectEntity
    ) -> AsyncGenerator[RedmineIssueEntity, None]:
        """Generate RedmineIssueEntity for each issue in the given project.

        Args:
            client: HTTP client to use for requests
            project: Parent project entity

        Yields:
            RedmineIssueEntity instances
        """
        project_id = project.project_id
        self.logger.info(f"Starting issue generation for project: {project.identifier}")

        # Get config options
        include_closed = self.config.get("include_closed_issues", False)

        # Build query parameters
        status_filter = "*" if include_closed else "open"

        # Pagination setup
        offset = 0
        limit = 100

        while True:
            # Construct URL with pagination and filters
            url = (
                f"{self.base_url}/issues.json?"
                f"project_id={project_id}&"
                f"status_id={status_filter}&"
                f"offset={offset}&"
                f"limit={limit}"
            )

            self.logger.info(f"Fetching issues for project {project.identifier}, offset {offset}")

            data = await self._get_with_auth(client, url)
            issues = data.get("issues", [])
            total_count = data.get("total_count", 0)

            self.logger.info(f"Retrieved {len(issues)} issues (total available: {total_count})")

            # Process each issue
            for issue_data in issues:
                issue_entity = self._create_issue_entity(issue_data, project)
                yield issue_entity

            # Check if we've fetched all issues
            if offset + len(issues) >= total_count or len(issues) == 0:
                self.logger.info(
                    f"Completed issue sync for project {project.identifier}: {total_count} issue(s)"
                )
                break

            # Move to next page
            offset += limit

    async def _generate_journal_entities(
        self, client: httpx.AsyncClient, issue: RedmineIssueEntity
    ) -> AsyncGenerator[RedmineJournalEntity, None]:
        """Generate RedmineJournalEntity for journals (comments) on an issue.

        Args:
            client: HTTP client to use for requests
            issue: Parent issue entity

        Yields:
            RedmineJournalEntity instances
        """
        issue_id = issue.issue_id

        # Fetch issue with journals included
        url = f"{self.base_url}/issues/{issue_id}.json?include=journals"

        self.logger.debug(f"Fetching journals for issue #{issue_id}")

        try:
            data = await self._get_with_auth(client, url)
            issue_data = data.get("issue", {})
            journals = issue_data.get("journals", [])

            self.logger.debug(f"Found {len(journals)} journal entries for issue #{issue_id}")

            for journal_data in journals:
                # Only create entities for journals with notes (comments)
                # Skip journals that only track field changes
                if journal_data.get("notes"):
                    journal_entity = self._create_journal_entity(
                        journal_data, issue_id, issue.entity_id
                    )
                    yield journal_entity

        except Exception as e:
            self.logger.warning(f"Failed to fetch journals for issue #{issue_id}: {str(e)}")
            # Don't fail the entire sync if journals fail for one issue

    async def _generate_attachment_entities(
        self, client: httpx.AsyncClient, issue: RedmineIssueEntity
    ) -> AsyncGenerator[RedmineAttachmentEntity, None]:
        """Generate RedmineAttachmentEntity for attachments on an issue.

        Args:
            client: HTTP client to use for requests
            issue: Parent issue entity

        Yields:
            RedmineAttachmentEntity instances
        """
        # Check if attachments are enabled in config
        include_attachments = self.config.get("include_attachments", False)
        if not include_attachments:
            return

        issue_id = issue.issue_id

        # Fetch issue with attachments included
        url = f"{self.base_url}/issues/{issue_id}.json?include=attachments"

        self.logger.debug(f"Fetching attachments for issue #{issue_id}")

        try:
            data = await self._get_with_auth(client, url)
            issue_data = data.get("issue", {})
            attachments = issue_data.get("attachments", [])

            self.logger.debug(f"Found {len(attachments)} attachments for issue #{issue_id}")

            for attachment_data in attachments:
                attachment_entity = self._create_attachment_entity(
                    attachment_data, issue_id, issue.entity_id
                )
                yield attachment_entity

        except Exception as e:
            self.logger.warning(f"Failed to fetch attachments for issue #{issue_id}: {str(e)}")
            # Don't fail the entire sync if attachments fail for one issue

    async def _generate_wiki_page_entities(
        self, client: httpx.AsyncClient, project: RedmineProjectEntity
    ) -> AsyncGenerator[RedmineWikiPageEntity, None]:
        """Generate RedmineWikiPageEntity for wiki pages in a project.

        Args:
            client: HTTP client to use for requests
            project: Parent project entity

        Yields:
            RedmineWikiPageEntity instances
        """
        # Check if wiki pages are enabled in config
        include_wiki = self.config.get("include_wiki_pages", True)
        if not include_wiki:
            return

        project_identifier = project.identifier
        self.logger.info(f"Starting wiki page generation for project: {project_identifier}")

        # First, get the list of wiki pages
        index_url = f"{self.base_url}/projects/{project_identifier}/wiki/index.json"

        try:
            index_data = await self._get_with_auth(client, index_url)
            wiki_pages = index_data.get("wiki_pages", [])

            self.logger.info(f"Found {len(wiki_pages)} wiki pages in project {project_identifier}")

            # Fetch full content for each wiki page
            for wiki_page_info in wiki_pages:
                page_title = wiki_page_info.get("title")
                if not page_title:
                    continue

                # Get full wiki page content
                page_url = f"{self.base_url}/projects/{project_identifier}/wiki/{page_title}.json"

                try:
                    page_data = await self._get_with_auth(client, page_url)
                    wiki_page = page_data.get("wiki_page", {})

                    wiki_entity = self._create_wiki_page_entity(
                        wiki_page, project.project_id, project.name, project.entity_id
                    )
                    yield wiki_entity

                except Exception as e:
                    self.logger.warning(
                        f"Failed to fetch wiki page '{page_title}' in project {project_identifier}: {str(e)}"
                    )
                    # Continue with other wiki pages

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                self.logger.info(f"Project {project_identifier} has no wiki enabled")
            else:
                self.logger.warning(
                    f"Failed to fetch wiki index for project {project_identifier}: {str(e)}"
                )
        except Exception as e:
            self.logger.warning(
                f"Failed to fetch wiki pages for project {project_identifier}: {str(e)}"
            )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Redmine.

        This is the main entry point for entity generation.

        Yields:
            All Redmine entities (projects, issues, journals, wiki pages, attachments)
        """
        self.logger.info("Starting Redmine entity generation process")

        async with httpx.AsyncClient(timeout=30.0) as client:
            project_count = 0
            issue_count = 0
            journal_count = 0
            wiki_count = 0
            attachment_count = 0

            # Generate projects
            async for project_entity in self._generate_project_entities(client):
                project_count += 1
                self.logger.info(f"Yielding project: {project_entity.identifier}")
                yield project_entity

                # Generate issues for this project
                async for issue_entity in self._generate_issue_entities(client, project_entity):
                    issue_count += 1
                    self.logger.debug(f"Yielding issue: #{issue_entity.issue_id}")
                    yield issue_entity

                    # Generate journals (comments) for this issue
                    async for journal_entity in self._generate_journal_entities(
                        client, issue_entity
                    ):
                        journal_count += 1
                        self.logger.debug(f"Yielding journal: {journal_entity.entity_id}")
                        yield journal_entity

                    # Generate attachments for this issue (if enabled)
                    async for attachment_entity in self._generate_attachment_entities(
                        client, issue_entity
                    ):
                        attachment_count += 1
                        self.logger.debug(f"Yielding attachment: {attachment_entity.filename}")
                        yield attachment_entity

                # Generate wiki pages for this project (if enabled)
                async for wiki_entity in self._generate_wiki_page_entities(client, project_entity):
                    wiki_count += 1
                    self.logger.debug(f"Yielding wiki page: {wiki_entity.title}")
                    yield wiki_entity

            self.logger.info(
                f"Completed Redmine entity generation: "
                f"{project_count} projects, "
                f"{issue_count} issues, "
                f"{journal_count} journals, "
                f"{wiki_count} wiki pages, "
                f"{attachment_count} attachments"
            )

    async def validate(self) -> bool:
        """Verify Redmine API key by calling the current user endpoint.

        A successful call proves the API key is valid.

        Returns:
            True if validation succeeds, False otherwise
        """
        try:
            self.logger.info("Validating Redmine connection")

            # Use the /users/current.json endpoint to verify authentication
            url = f"{self.base_url}/users/current.json"

            async with httpx.AsyncClient(timeout=10.0) as client:
                data = await self._get_with_auth(client, url)

                user = data.get("user")
                if user:
                    user_name = user.get("login", "unknown")
                    self.logger.info(
                        f"✅ Redmine validation successful. Authenticated as: {user_name}"
                    )
                    return True
                else:
                    self.logger.error("Redmine validation failed: No user data returned")
                    return False

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                self.logger.error(
                    "❌ Redmine validation failed: Invalid API key. "
                    f"Please check your API key at: {self.base_url}/my/account"
                )
            else:
                self.logger.error(f"❌ Redmine validation failed: HTTP {e.response.status_code}")
            return False
        except Exception as e:
            self.logger.error(f"❌ Redmine validation failed: {str(e)}")
            return False

        # Defensive fallback: keep return type stable even if control-flow changes.
        return False
