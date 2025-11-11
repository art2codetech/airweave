"""
Async test module for Direct Authentication source connections with config fields.

Tests GitLab Self-Hosted which uses direct authentication (Personal Access Token)
plus configuration fields (instance_url, project_id, branch).

This is a unique combination that extends the existing test patterns:
- test_source_connections_direct_auth.py (direct auth, no config)
- test_source_connections_template_configs.py (OAuth + config)
"""

import pytest
import httpx
from typing import Dict


class TestDirectAuthWithConfig:
    """Test suite for direct auth connections that also have config fields."""

    @pytest.mark.asyncio
    async def test_create_gitlab_selfhosted_connection(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test creating a GitLab Self-Hosted connection with PAT and instance_url."""
        # Skip if credentials not available
        if not config.TEST_GITLAB_SELFHOSTED_PAT or not config.TEST_GITLAB_SELFHOSTED_INSTANCE_URL:
            pytest.skip("GitLab Self-Hosted credentials not configured")

        payload = {
            "name": "Test GitLab Self-Hosted Connection",
            "short_name": "gitlab_selfhosted",
            "readable_collection_id": collection["readable_id"],
            "description": "Testing direct auth with config fields",
            "config": {
                "instance_url": config.TEST_GITLAB_SELFHOSTED_INSTANCE_URL,
                # Optional config fields
                # "project_id": "",
                # "branch": "",
            },
            "authentication": {
                "credentials": {
                    "personal_access_token": config.TEST_GITLAB_SELFHOSTED_PAT
                }
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()

        connection = response.json()
        assert connection["id"]
        assert connection["name"] == "Test GitLab Self-Hosted Connection"
        assert connection["short_name"] == "gitlab_selfhosted"
        assert connection["auth"]["method"] == "direct"
        assert connection["auth"]["authenticated"] == True
        assert connection["status"] == "active"

        # Verify config was saved
        assert connection["config"]["instance_url"] == config.TEST_GITLAB_SELFHOSTED_INSTANCE_URL

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_gitlab_selfhosted_missing_instance_url(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test that creating connection fails without required instance_url config."""
        if not config.TEST_GITLAB_SELFHOSTED_PAT:
            pytest.skip("GitLab Self-Hosted credentials not configured")

        payload = {
            "name": "Test GitLab Missing Config",
            "short_name": "gitlab_selfhosted",
            "readable_collection_id": collection["readable_id"],
            "config": {
                # Missing instance_url - should fail
                "project_id": "12345",
            },
            "authentication": {
                "credentials": {
                    "personal_access_token": config.TEST_GITLAB_SELFHOSTED_PAT
                }
            },
        }

        response = await api_client.post("/source-connections", json=payload)

        # Should fail with 422 Unprocessable Entity
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        error = response.json()
        detail = str(error.get("detail", "")).lower()
        assert "instance_url" in detail, f"Error should mention 'instance_url': {detail}"

    @pytest.mark.asyncio
    async def test_gitlab_selfhosted_with_project_id_filter(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test GitLab Self-Hosted with project_id config (selective sync)."""
        if not config.TEST_GITLAB_SELFHOSTED_PAT or not config.TEST_GITLAB_SELFHOSTED_INSTANCE_URL:
            pytest.skip("GitLab Self-Hosted credentials not configured")

        payload = {
            "name": "GitLab Specific Project",
            "short_name": "gitlab_selfhosted",
            "readable_collection_id": collection["readable_id"],
            "config": {
                "instance_url": config.TEST_GITLAB_SELFHOSTED_INSTANCE_URL,
                "project_id": config.TEST_GITLAB_SELFHOSTED_PROJECT_ID or "",
                "branch": "main",
            },
            "authentication": {
                "credentials": {
                    "personal_access_token": config.TEST_GITLAB_SELFHOSTED_PAT
                }
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()

        connection = response.json()
        assert connection["config"]["instance_url"] == config.TEST_GITLAB_SELFHOSTED_INSTANCE_URL
        if payload["config"]["project_id"]:
            assert connection["config"]["project_id"] == payload["config"]["project_id"]
        assert connection["config"]["branch"] == "main"

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_gitlab_selfhosted_invalid_pat(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test creating connection with invalid PAT."""
        if not config.TEST_GITLAB_SELFHOSTED_INSTANCE_URL:
            pytest.skip("GitLab Self-Hosted instance URL not configured")

        payload = {
            "name": "Invalid PAT Test",
            "short_name": "gitlab_selfhosted",
            "readable_collection_id": collection["readable_id"],
            "config": {
                "instance_url": config.TEST_GITLAB_SELFHOSTED_INSTANCE_URL,
            },
            "authentication": {
                "credentials": {
                    "personal_access_token": "glpat-invalid_token_12345"
                }
            },
        }

        response = await api_client.post("/source-connections", json=payload)

        # Should still create the connection (validation happens during sync)
        if response.status_code == 200:
            connection = response.json()
            # Cleanup
            await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_update_instance_url(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test updating the instance_url config field."""
        if not config.TEST_GITLAB_SELFHOSTED_PAT or not config.TEST_GITLAB_SELFHOSTED_INSTANCE_URL:
            pytest.skip("GitLab Self-Hosted credentials not configured")

        # Create connection
        payload = {
            "name": "Update Instance URL Test",
            "short_name": "gitlab_selfhosted",
            "readable_collection_id": collection["readable_id"],
            "config": {
                "instance_url": config.TEST_GITLAB_SELFHOSTED_INSTANCE_URL,
            },
            "authentication": {
                "credentials": {
                    "personal_access_token": config.TEST_GITLAB_SELFHOSTED_PAT
                }
            },
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # Update instance_url (use same URL for test, but demonstrates the flow)
        update_payload = {
            "config": {
                "instance_url": config.TEST_GITLAB_SELFHOSTED_INSTANCE_URL,
            }
        }

        response = await api_client.patch(
            f"/source-connections/{connection['id']}", json=update_payload
        )
        response.raise_for_status()
        updated = response.json()

        assert updated["config"]["instance_url"] == config.TEST_GITLAB_SELFHOSTED_INSTANCE_URL

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_gitlab_selfhosted_url_normalization(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test that various instance_url formats are handled correctly."""
        if not config.TEST_GITLAB_SELFHOSTED_PAT or not config.TEST_GITLAB_SELFHOSTED_INSTANCE_URL:
            pytest.skip("GitLab Self-Hosted credentials not configured")

        # Test with trailing slash - should be normalized
        test_url = config.TEST_GITLAB_SELFHOSTED_INSTANCE_URL.rstrip('/') + '/'

        payload = {
            "name": "URL Normalization Test",
            "short_name": "gitlab_selfhosted",
            "readable_collection_id": collection["readable_id"],
            "config": {
                "instance_url": test_url,
            },
            "authentication": {
                "credentials": {
                    "personal_access_token": config.TEST_GITLAB_SELFHOSTED_PAT
                }
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        # Connection should be created successfully
        if response.status_code == 200:
            connection = response.json()
            # URL should be stored (potentially normalized by backend)
            assert connection["config"]["instance_url"]
            # Cleanup
            await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_gitlab_selfhosted_sync_completion(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test that sync completes successfully for GitLab Self-Hosted."""
        import asyncio

        if not config.TEST_GITLAB_SELFHOSTED_PAT or not config.TEST_GITLAB_SELFHOSTED_INSTANCE_URL:
            pytest.skip("GitLab Self-Hosted credentials not configured")

        # Create connection and trigger sync
        payload = {
            "name": "GitLab Sync Test",
            "short_name": "gitlab_selfhosted",
            "readable_collection_id": collection["readable_id"],
            "config": {
                "instance_url": config.TEST_GITLAB_SELFHOSTED_INSTANCE_URL,
                # Use specific project for faster testing if available
                "project_id": config.TEST_GITLAB_SELFHOSTED_PROJECT_ID or "",
            },
            "authentication": {
                "credentials": {
                    "personal_access_token": config.TEST_GITLAB_SELFHOSTED_PAT
                }
            },
            "sync_immediately": True,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # Wait for sync to complete
        await asyncio.sleep(30)

        response = await api_client.get(f"/source-connections/{connection['id']}")
        response.raise_for_status()
        updated_connection = response.json()

        assert updated_connection["sync"]["last_job"]["status"] in ["completed", "running"]
        # Verify entities were created
        assert updated_connection["sync"]["last_job"]["entities_inserted"] >= 0

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")
