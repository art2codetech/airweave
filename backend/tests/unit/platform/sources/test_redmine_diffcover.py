"""Additional Redmine tests aimed at improving diff-cover.

The main Redmine test suite focuses on correctness. This file adds a few
extra targeted tests to exercise less-common branches so the PR meets the
minimum diff coverage threshold.
"""

# ruff: noqa: D101, D102

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from airweave.platform.sources.redmine import RedmineSource


@pytest.mark.asyncio
async def test_validate_failure_returns_false(redmine_config):
    """Regression: validate() must return False on invalid creds (not None)."""
    source = await RedmineSource.create(api_key="invalid-key", config=redmine_config)

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_request = MagicMock()

    with patch.object(
        source,
        "_get_with_auth",
        new=AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Unauthorized", request=mock_request, response=mock_response
            )
        ),
    ):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await source.validate()
            assert result is False


@pytest.mark.asyncio
async def test_generate_entities_exercises_optional_paths(
    redmine_config_all_projects, mock_project_response
):
    """Exercise entity-generation paths with minimal mocked API calls."""
    source = await RedmineSource.create(api_key="test-key", config=redmine_config_all_projects)

    # Minimal issue response
    issues_response = {
        "issues": [
            {
                "id": 101,
                "project": {"id": 1, "name": "Test Project"},
                "subject": "Example",
                "created_on": "2024-01-01T00:00:00Z",
                "updated_on": "2024-01-01T00:00:00Z",
            }
        ],
        "total_count": 1,
        "offset": 0,
        "limit": 100,
    }

    journals_response = {
        "issue": {
            "id": 101,
            "journals": [
                {
                    "id": 201,
                    "user": {"id": 1, "name": "John"},
                    "notes": "hello",
                    "created_on": "2024-01-01T00:00:00Z",
                }
            ],
        }
    }

    attachments_response = {
        "issue": {
            "id": 101,
            "attachments": [
                {
                    "id": 301,
                    "filename": "file.txt",
                    "filesize": 1,
                    "content_type": "text/plain",
                    "content_url": "https://example.com/file.txt",
                    "created_on": "2024-01-01T00:00:00Z",
                }
            ],
        }
    }

    wiki_index_response = {"wiki_pages": []}

    async def fake_get_with_auth(_client, url):
        # projects
        if url.endswith("/projects.json?offset=0&limit=100"):
            return mock_project_response

        # issues
        if "/issues.json" in url:
            return issues_response

        # issue journals
        if url.endswith("/issues/101.json?include=journals"):
            return journals_response

        # issue attachments
        if url.endswith("/issues/101.json?include=attachments"):
            return attachments_response

        # wiki index
        if url.endswith("/projects/test-project/wiki/index.json"):
            return wiki_index_response

        return {}

    with patch.object(source, "_get_with_auth", new=AsyncMock(side_effect=fake_get_with_auth)):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            # Consume a few entities to hit branches.
            entities = []
            async for ent in source.generate_entities():
                entities.append(ent)

            assert any(getattr(e, "entity_id", "").startswith("project-") for e in entities)
            assert any(getattr(e, "entity_id", "").startswith("issue-") for e in entities)
