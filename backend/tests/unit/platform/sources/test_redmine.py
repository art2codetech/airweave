"""Unit tests for Redmine source implementation.

Tests entity creation, API interactions, pagination, authentication,
and error handling using mocked responses.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from airweave.platform.sources.redmine import RedmineSource
from airweave.platform.entities.redmine import (
    RedmineProjectEntity,
    RedmineIssueEntity,
    RedmineWikiPageEntity,
    RedmineJournalEntity,
    RedmineAttachmentEntity,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def redmine_config():
    """Standard Redmine configuration for testing."""
    return {
        "base_url": "https://redmine.example.com",
        "project_identifiers": ["test-project", "dev-team"],
        "include_closed_issues": False,
        "include_attachments": False,
        "include_wiki_pages": True,
    }


@pytest.fixture
def redmine_config_all_projects():
    """Configuration that syncs all projects (no filter)."""
    return {
        "base_url": "https://redmine.example.com",
        "project_identifiers": None,  # Sync all
        "include_closed_issues": True,
        "include_attachments": True,
        "include_wiki_pages": True,
    }


@pytest.fixture
def mock_project_response():
    """Mock Redmine API response for projects."""
    return {
        "projects": [
            {
                "id": 1,
                "name": "Test Project",
                "identifier": "test-project",
                "description": "A test project",
                "homepage": "https://example.com",
                "is_public": True,
                "parent": None,
                "status": 1,
                "created_on": "2024-01-01T00:00:00Z",
                "updated_on": "2024-01-15T10:30:00Z",
            },
            {
                "id": 2,
                "name": "Dev Team",
                "identifier": "dev-team",
                "description": "Development team project",
                "homepage": "",
                "is_public": False,
                "status": 1,
                "created_on": "2024-01-05T00:00:00Z",
                "updated_on": "2024-01-20T14:20:00Z",
            }
        ],
        "total_count": 2,
        "offset": 0,
        "limit": 100,
    }


@pytest.fixture
def mock_issue_response():
    """Mock Redmine API response for issues."""
    return {
        "issues": [
            {
                "id": 101,
                "project": {"id": 1, "name": "Test Project"},
                "tracker": {"id": 1, "name": "Bug"},
                "status": {"id": 1, "name": "New"},
                "priority": {"id": 2, "name": "Normal"},
                "author": {"id": 1, "name": "John Doe"},
                "assigned_to": {"id": 2, "name": "Jane Smith"},
                "subject": "Fix login issue",
                "description": "Users cannot log in with special characters in password",
                "start_date": "2024-01-10",
                "due_date": "2024-01-20",
                "done_ratio": 50,
                "estimated_hours": 8.0,
                "spent_hours": 4.0,
                "created_on": "2024-01-10T09:00:00Z",
                "updated_on": "2024-01-15T14:30:00Z",
                "closed_on": None,
            },
            {
                "id": 102,
                "project": {"id": 1, "name": "Test Project"},
                "tracker": {"id": 2, "name": "Feature"},
                "status": {"id": 3, "name": "Closed"},
                "priority": {"id": 3, "name": "High"},
                "author": {"id": 3, "name": "Bob Wilson"},
                "subject": "Add dark mode",
                "description": "Implement dark mode theme",
                "start_date": "2024-01-05",
                "due_date": None,
                "done_ratio": 100,
                "estimated_hours": 16.0,
                "spent_hours": 18.5,
                "created_on": "2024-01-05T10:00:00Z",
                "updated_on": "2024-01-18T16:45:00Z",
                "closed_on": "2024-01-18T16:45:00Z",
            }
        ],
        "total_count": 2,
        "offset": 0,
        "limit": 100,
    }


@pytest.fixture
def mock_wiki_index_response():
    """Mock Redmine API response for wiki page index."""
    return {
        "wiki_pages": [
            {"title": "Wiki", "version": 5, "created_on": "2024-01-01T00:00:00Z", "updated_on": "2024-01-10T12:00:00Z"},
            {"title": "Installation", "version": 3, "created_on": "2024-01-02T00:00:00Z", "updated_on": "2024-01-08T09:30:00Z"},
            {"title": "API_Documentation", "version": 1, "created_on": "2024-01-05T00:00:00Z", "updated_on": "2024-01-05T00:00:00Z"},
        ]
    }


@pytest.fixture
def mock_wiki_page_response():
    """Mock Redmine API response for a single wiki page."""
    return {
        "wiki_page": {
            "title": "Wiki",
            "text": "h1. Welcome\n\nThis is the main wiki page.\n\n* Item 1\n* Item 2",
            "version": 5,
            "author": {"id": 1, "name": "John Doe"},
            "comments": "Updated introduction",
            "created_on": "2024-01-01T00:00:00Z",
            "updated_on": "2024-01-10T12:00:00Z",
        }
    }


@pytest.fixture
def mock_issue_with_journals_response():
    """Mock Redmine API response for issue with journals (comments)."""
    return {
        "issue": {
            "id": 101,
            "project": {"id": 1, "name": "Test Project"},
            "subject": "Fix login issue",
            "description": "Users cannot log in",
            "journals": [
                {
                    "id": 201,
                    "user": {"id": 1, "name": "John Doe"},
                    "notes": "I've started working on this issue.",
                    "created_on": "2024-01-11T10:00:00Z",
                    "details": [],
                },
                {
                    "id": 202,
                    "user": {"id": 2, "name": "Jane Smith"},
                    "notes": "Please prioritize this.",
                    "created_on": "2024-01-12T14:30:00Z",
                    "details": [
                        {"property": "attr", "name": "priority_id", "old_value": "2", "new_value": "3"}
                    ],
                }
            ]
        }
    }


@pytest.fixture
def mock_attachment_response():
    """Mock Redmine API response for attachments on an issue."""
    return {
        "issue": {
            "id": 101,
            "attachments": [
                {
                    "id": 301,
                    "filename": "screenshot.png",
                    "filesize": 45678,
                    "content_type": "image/png",
                    "description": "Login error screenshot",
                    "content_url": "https://redmine.example.com/attachments/download/301/screenshot.png",
                    "author": {"id": 1, "name": "John Doe"},
                    "created_on": "2024-01-10T09:30:00Z",
                },
                {
                    "id": 302,
                    "filename": "error.log",
                    "filesize": 12345,
                    "content_type": "text/plain",
                    "description": "Server error log",
                    "content_url": "https://redmine.example.com/attachments/download/302/error.log",
                    "author": {"id": 1, "name": "John Doe"},
                    "created_on": "2024-01-10T09:35:00Z",
                }
            ]
        }
    }


# ============================================================================
# ENTITY CREATION TESTS
# ============================================================================

class TestRedmineEntityCreation:
    """Test entity creation from API responses."""

    @pytest.mark.asyncio
    async def test_create_project_entity(self, redmine_config, mock_project_response):
        """Test creating RedmineProjectEntity from API data."""
        source = await RedmineSource.create(api_key="test-key", config=redmine_config)

        project_data = mock_project_response["projects"][0]
        entity = source._create_project_entity(project_data)

        assert isinstance(entity, RedmineProjectEntity)
        assert entity.entity_id == "project-1"
        assert entity.name == "Test Project"
        assert entity.identifier == "test-project"
        assert entity.description == "A test project"
        assert entity.project_id == 1
        assert entity.is_public is True
        assert entity.breadcrumbs == []

    @pytest.mark.asyncio
    async def test_create_issue_entity(self, redmine_config, mock_issue_response, mock_project_response):
        """Test creating RedmineIssueEntity from API data."""
        source = await RedmineSource.create(api_key="test-key", config=redmine_config)

        # Create project entity first (for breadcrumbs)
        project_data = mock_project_response["projects"][0]
        project_entity = source._create_project_entity(project_data)

        issue_data = mock_issue_response["issues"][0]
        entity = source._create_issue_entity(issue_data, project_entity)

        assert isinstance(entity, RedmineIssueEntity)
        assert entity.entity_id == "issue-101"
        assert entity.name == "Fix login issue"
        assert entity.issue_id == 101
        assert entity.subject == "Fix login issue"
        assert entity.description == "Users cannot log in with special characters in password"
        assert entity.tracker_name == "Bug"
        assert entity.status_name == "New"
        assert entity.priority_name == "Normal"
        assert entity.assigned_to == "Jane Smith"
        assert entity.author == "John Doe"
        assert entity.done_ratio == 50
        assert entity.estimated_hours == 8.0
        assert len(entity.breadcrumbs) == 1
        assert entity.breadcrumbs[0].entity_id == project_entity.entity_id

    @pytest.mark.asyncio
    async def test_create_wiki_page_entity(self, redmine_config, mock_wiki_page_response):
        """Test creating RedmineWikiPageEntity from API data."""
        source = await RedmineSource.create(api_key="test-key", config=redmine_config)

        wiki_data = mock_wiki_page_response["wiki_page"]
        project_id = 1
        project_name = "Test Project"
        project_entity_id = "project-1"

        entity = source._create_wiki_page_entity(wiki_data, project_id, project_name, project_entity_id)

        assert isinstance(entity, RedmineWikiPageEntity)
        assert entity.name == "Wiki"
        assert entity.title == "Wiki"
        assert "Welcome" in entity.text
        assert entity.version == 5
        assert entity.author == "John Doe"
        assert entity.project_id == 1
        assert entity.project_name == "Test Project"
        assert len(entity.breadcrumbs) == 1

    @pytest.mark.asyncio
    async def test_create_journal_entity(self, redmine_config, mock_issue_with_journals_response):
        """Test creating RedmineJournalEntity from journal data."""
        source = await RedmineSource.create(api_key="test-key", config=redmine_config)

        journal_data = mock_issue_with_journals_response["issue"]["journals"][0]
        issue_id = 101
        issue_entity_id = "issue-101"

        entity = source._create_journal_entity(journal_data, issue_id, issue_entity_id)

        assert isinstance(entity, RedmineJournalEntity)
        assert entity.journal_id == 201
        assert entity.notes == "I've started working on this issue."
        assert entity.issue_id == 101
        assert entity.author == "John Doe"
        assert len(entity.breadcrumbs) == 1
        assert entity.breadcrumbs[0].entity_id == issue_entity_id

    @pytest.mark.asyncio
    async def test_create_attachment_entity(self, redmine_config, mock_attachment_response):
        """Test creating RedmineAttachmentEntity from attachment data."""
        source = await RedmineSource.create(api_key="test-key", config=redmine_config)

        attachment_data = mock_attachment_response["issue"]["attachments"][0]
        issue_id = 101
        issue_entity_id = "issue-101"

        entity = source._create_attachment_entity(attachment_data, issue_id, issue_entity_id)

        assert isinstance(entity, RedmineAttachmentEntity)
        assert entity.attachment_id == 301
        assert entity.filename == "screenshot.png"
        assert entity.filesize == 45678
        assert entity.content_type == "image/png"
        assert entity.description == "Login error screenshot"
        assert entity.issue_id == 101
        assert len(entity.breadcrumbs) == 1


# ============================================================================
# API INTERACTION TESTS
# ============================================================================

class TestRedmineAPIInteractions:
    """Test API request methods and authentication."""

    @pytest.mark.asyncio
    async def test_get_with_auth_api_key(self, redmine_config):
        """Test authenticated GET request using API key."""
        source = await RedmineSource.create(api_key="test-api-key-12345", config=redmine_config)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"test": "data"}
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await source._get_with_auth(mock_client, "https://redmine.example.com/projects.json")

        # Verify API key was included in headers
        call_args = mock_client.get.call_args
        headers = call_args.kwargs.get("headers", call_args.args[1] if len(call_args.args) > 1 else {})
        assert headers["X-Redmine-API-Key"] == "test-api-key-12345"
        assert headers["Accept"] == "application/json"
        assert result == {"test": "data"}

    @pytest.mark.asyncio
    async def test_get_with_auth_handles_401(self, redmine_config):
        """Test that 401 errors are handled appropriately."""
        source = await RedmineSource.create(api_key="invalid-key", config=redmine_config)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_request = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "Unauthorized",
            request=mock_request,
            response=mock_response
        ))

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await source._get_with_auth(mock_client, "https://redmine.example.com/projects.json")

        assert exc_info.value.response.status_code == 401

    @pytest.mark.asyncio
    async def test_validate_success(self, redmine_config):
        """Test successful validation of Redmine connection."""
        source = await RedmineSource.create(api_key="valid-key", config=redmine_config)

        with patch.object(source, '_get_with_auth', new=AsyncMock(return_value={"user": {"id": 1, "login": "testuser"}})):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()
                mock_client_class.return_value = mock_client

                result = await source.validate()
                assert result is True

    @pytest.mark.asyncio
    async def test_validate_failure(self, redmine_config):
        """Test validation failure with invalid credentials."""
        source = await RedmineSource.create(api_key="invalid-key", config=redmine_config)

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_request = MagicMock()

        with patch.object(source, '_get_with_auth', new=AsyncMock(
            side_effect=httpx.HTTPStatusError("Unauthorized", request=mock_request, response=mock_response)
        )):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()
                mock_client_class.return_value = mock_client

                result = await source.validate()
                assert result is False


# ============================================================================
# PAGINATION TESTS
# ============================================================================

class TestRedminePagination:
    """Test pagination logic for API requests."""

    @pytest.mark.asyncio
    async def test_project_pagination_single_page(self, redmine_config, mock_project_response):
        """Test project fetching with single page of results."""
        source = await RedmineSource.create(api_key="test-key", config=redmine_config)

        mock_client = MagicMock()

        with patch.object(source, '_get_with_auth', return_value=mock_project_response):
            projects = []
            async for project in source._generate_project_entities(mock_client):
                projects.append(project)

            assert len(projects) == 2
            assert all(isinstance(p, RedmineProjectEntity) for p in projects)

    @pytest.mark.asyncio
    async def test_project_pagination_multiple_pages(self, redmine_config):
        """Test project fetching with multiple pages."""
        source = await RedmineSource.create(api_key="test-key", config={**redmine_config, "project_identifiers": None})

        # First page
        page1_response = {
            "projects": [{"id": i, "name": f"Project {i}", "identifier": f"proj-{i}"}
                        for i in range(1, 101)],
            "total_count": 150,
            "offset": 0,
            "limit": 100,
        }

        # Second page
        page2_response = {
            "projects": [{"id": i, "name": f"Project {i}", "identifier": f"proj-{i}"}
                        for i in range(101, 151)],
            "total_count": 150,
            "offset": 100,
            "limit": 100,
        }

        mock_client = MagicMock()

        with patch.object(source, '_get_with_auth', side_effect=[page1_response, page2_response]):
            projects = []
            async for project in source._generate_project_entities(mock_client):
                projects.append(project)

            assert len(projects) == 150

    @pytest.mark.asyncio
    async def test_issue_pagination(self, redmine_config, mock_issue_response):
        """Test issue fetching with pagination."""
        source = await RedmineSource.create(api_key="test-key", config=redmine_config)

        project_entity = RedmineProjectEntity(
            entity_id="project-1",
            breadcrumbs=[],
            name="Test Project",
            created_at=None,
            updated_at=None,
            project_id=1,
            identifier="test-project",
        )

        mock_client = MagicMock()

        with patch.object(source, '_get_with_auth', return_value=mock_issue_response):
            issues = []
            async for issue in source._generate_issue_entities(mock_client, project_entity):
                issues.append(issue)

            assert len(issues) == 2
            assert all(isinstance(i, RedmineIssueEntity) for i in issues)


# ============================================================================
# FILTERING TESTS
# ============================================================================

class TestRedmineFiltering:
    """Test filtering logic for projects and issues."""

    @pytest.mark.asyncio
    async def test_project_identifier_filtering(self, redmine_config, mock_project_response):
        """Test that only specified project identifiers are included."""
        # Config specifies only "test-project"
        config = {**redmine_config, "project_identifiers": ["test-project"]}
        source = await RedmineSource.create(api_key="test-key", config=config)

        mock_client = MagicMock()

        with patch.object(source, '_get_with_auth', return_value=mock_project_response):
            projects = []
            async for project in source._generate_project_entities(mock_client):
                projects.append(project)

            # Should only get the one matching project
            assert len(projects) == 1
            assert projects[0].identifier == "test-project"

    @pytest.mark.asyncio
    async def test_all_projects_when_no_filter(self, redmine_config_all_projects, mock_project_response):
        """Test that all projects are included when no filter is specified."""
        source = await RedmineSource.create(api_key="test-key", config=redmine_config_all_projects)

        mock_client = MagicMock()

        with patch.object(source, '_get_with_auth', return_value=mock_project_response):
            projects = []
            async for project in source._generate_project_entities(mock_client):
                projects.append(project)

            assert len(projects) == 2

    @pytest.mark.asyncio
    async def test_closed_issues_filtering(self, redmine_config):
        """Test filtering of closed issues based on config."""
        # Config with include_closed_issues = False
        config = {**redmine_config, "include_closed_issues": False}
        source = await RedmineSource.create(api_key="test-key", config=config)

        project_entity = RedmineProjectEntity(
            entity_id="project-1",
            breadcrumbs=[],
            name="Test Project",
            created_at=None,
            updated_at=None,
            project_id=1,
            identifier="test-project",
        )

        # Verify the API URL includes status_id=open parameter
        mock_client = MagicMock()
        with patch.object(source, '_get_with_auth', return_value={"issues": [], "total_count": 0}) as mock_get:
            issues = []
            async for issue in source._generate_issue_entities(mock_client, project_entity):
                issues.append(issue)

            # Verify API was called with open status filter
            call_args = mock_get.call_args_list[0]
            url = call_args[0][1]
            assert "status_id=open" in url


# ============================================================================
# WIKI PAGE TESTS
# ============================================================================

class TestRedmineWikiPages:
    """Test wiki page fetching and entity creation."""

    @pytest.mark.asyncio
    async def test_generate_wiki_page_entities(self, redmine_config, mock_wiki_index_response, mock_wiki_page_response):
        """Test generating wiki page entities for a project."""
        source = await RedmineSource.create(api_key="test-key", config=redmine_config)

        project_entity = RedmineProjectEntity(
            entity_id="project-1",
            breadcrumbs=[],
            name="Test Project",
            created_at=None,
            updated_at=None,
            project_id=1,
            identifier="test-project",
        )

        mock_client = MagicMock()

        # Mock responses: first for index, then for each page
        with patch.object(source, '_get_with_auth', side_effect=[
            mock_wiki_index_response,
            mock_wiki_page_response,
            mock_wiki_page_response,  # Reuse for other pages
            mock_wiki_page_response,
        ]):
            wiki_pages = []
            async for page in source._generate_wiki_page_entities(mock_client, project_entity):
                wiki_pages.append(page)

            assert len(wiki_pages) == 3
            assert all(isinstance(p, RedmineWikiPageEntity) for p in wiki_pages)

    @pytest.mark.asyncio
    async def test_wiki_pages_skipped_when_disabled(self, redmine_config):
        """Test that wiki pages are skipped when include_wiki_pages is False."""
        config = {**redmine_config, "include_wiki_pages": False}
        source = await RedmineSource.create(api_key="test-key", config=config)

        project_entity = RedmineProjectEntity(
            entity_id="project-1",
            breadcrumbs=[],
            name="Test Project",
            created_at=None,
            updated_at=None,
            project_id=1,
            identifier="test-project",
        )

        mock_client = MagicMock()

        # Should not make any API calls
        with patch.object(source, '_get_with_auth') as mock_get:
            wiki_pages = []
            async for page in source._generate_wiki_page_entities(mock_client, project_entity):
                wiki_pages.append(page)

            assert len(wiki_pages) == 0
            mock_get.assert_not_called()


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestRedmineErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_handles_missing_optional_fields(self, redmine_config):
        """Test handling of missing optional fields in API responses."""
        source = await RedmineSource.create(api_key="test-key", config=redmine_config)

        # Minimal project data with many fields missing
        minimal_project = {
            "id": 1,
            "name": "Minimal Project",
            "identifier": "minimal",
            # Missing: description, homepage, parent, etc.
        }

        entity = source._create_project_entity(minimal_project)

        assert entity.name == "Minimal Project"
        assert entity.description is None
        assert entity.homepage is None

    @pytest.mark.asyncio
    async def test_handles_network_errors(self, redmine_config):
        """Test handling of network errors during API calls."""
        source = await RedmineSource.create(api_key="test-key", config=redmine_config)

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.NetworkError("Connection failed"))

        with pytest.raises(httpx.NetworkError):
            await source._get_with_auth(mock_client, "https://redmine.example.com/projects.json")

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self, redmine_config):
        """Test handling of invalid JSON responses."""
        source = await RedmineSource.create(api_key="test-key", config=redmine_config)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(ValueError):
            await source._get_with_auth(mock_client, "https://redmine.example.com/projects.json")

    @pytest.mark.asyncio
    async def test_empty_project_list(self, redmine_config):
        """Test handling of empty project list."""
        source = await RedmineSource.create(api_key="test-key", config=redmine_config)

        empty_response = {
            "projects": [],
            "total_count": 0,
            "offset": 0,
            "limit": 100,
        }

        mock_client = MagicMock()

        with patch.object(source, '_get_with_auth', return_value=empty_response):
            projects = []
            async for project in source._generate_project_entities(mock_client):
                projects.append(project)

            assert len(projects) == 0

    @pytest.mark.asyncio
    async def test_base_url_validation(self):
        """Test that base_url is required in config."""
        with pytest.raises(ValueError, match="base_url is required"):
            await RedmineSource.create(api_key="test-key", config={})

    @pytest.mark.asyncio
    async def test_base_url_trailing_slash_removed(self):
        """Test that trailing slash is removed from base_url."""
        config = {
            "base_url": "https://redmine.example.com/",
            "project_identifiers": None,
        }
        source = await RedmineSource.create(api_key="test-key", config=config)
        assert source.base_url == "https://redmine.example.com"
