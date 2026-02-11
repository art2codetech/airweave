"""Unit tests for GitLab self-hosted connector.

These tests are intentionally lightweight and heavily mocked so we can
exercise the code paths added in the self-hosted connector without
needing a real GitLab instance.
"""

# ruff: noqa: D101, D102, B017

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.configs.config import GitLabSelfHostedConfig
from airweave.platform.sources.gitlab import GitLabSelfHostedSource, GitLabSource


class TestGitLabSelfHostedConfig:
    def test_requires_instance_url(self):
        with pytest.raises(Exception):
            GitLabSelfHostedConfig()  # type: ignore[call-arg]

    def test_accepts_instance_url(self):
        cfg = GitLabSelfHostedConfig(instance_url="https://gitlab.example.com")
        assert cfg.instance_url == "https://gitlab.example.com"


class TestGitLabSelfHostedSource:
    @pytest.mark.asyncio
    async def test_normalize_instance_url(self):
        assert (
            GitLabSelfHostedSource._normalize_instance_url("gitlab.example.com/")
            == "https://gitlab.example.com"
        )
        assert (
            GitLabSelfHostedSource._normalize_instance_url("https://gitlab.example.com/")
            == "https://gitlab.example.com"
        )

    @pytest.mark.asyncio
    async def test_create_requires_token_and_instance_url(self):
        with pytest.raises(ValueError):
            await GitLabSelfHostedSource.create("", config={"instance_url": "https://x"})

        with pytest.raises(ValueError):
            await GitLabSelfHostedSource.create("pat", config={})

    @pytest.mark.asyncio
    async def test_create_sets_base_url_and_headers(self):
        with patch.object(
            GitLabSelfHostedSource, "_detect_api_version", new=AsyncMock(return_value="v4")
        ):
            src = await GitLabSelfHostedSource.create(
                "pat",
                config={
                    "instance_url": "gitlab.example.com",
                    "project_id": "123",
                    "branch": "main",
                },
            )

        assert src.instance_url == "https://gitlab.example.com"
        assert src.base_url == "https://gitlab.example.com/api/v4"

        headers = await src._get_auth_headers()
        assert headers["PRIVATE-TOKEN"] == "pat"

    @pytest.mark.asyncio
    async def test_get_auth_headers_raises_without_token(self):
        src = GitLabSelfHostedSource()
        src.personal_access_token = None
        with pytest.raises(ValueError):
            await src._get_auth_headers()

    @pytest.mark.asyncio
    async def test_detect_api_version_success_and_fallback(self):
        # Success path
        src = GitLabSelfHostedSource()
        src.personal_access_token = "pat"
        src.instance_url = "https://gitlab.example.com"

        ok_response = MagicMock(status_code=200)

        @asynccontextmanager
        async def ok_client():
            client = MagicMock()
            client.get = AsyncMock(return_value=ok_response)
            yield client

        src.http_client = ok_client  # type: ignore[assignment]

        assert await src._detect_api_version() == "v4"

        # Fallback path (exception)
        src2 = GitLabSelfHostedSource()
        src2.personal_access_token = "pat"
        src2.instance_url = "https://gitlab.example.com"

        @asynccontextmanager
        async def failing_client():
            client = MagicMock()
            client.get = AsyncMock(side_effect=RuntimeError("boom"))
            yield client

        src2.http_client = failing_client  # type: ignore[assignment]

        assert await src2._detect_api_version() == "v4"

    @pytest.mark.asyncio
    async def test_validate_true_false_and_exception_path(self):
        src = GitLabSelfHostedSource()
        src.personal_access_token = "pat"
        src.instance_url = "https://gitlab.example.com"
        src.api_version = "v4"

        ok_response = MagicMock(status_code=200)
        bad_response = MagicMock(status_code=401)

        @asynccontextmanager
        async def ok_client():
            client = MagicMock()
            client.get = AsyncMock(return_value=ok_response)
            yield client

        @asynccontextmanager
        async def bad_client():
            client = MagicMock()
            client.get = AsyncMock(return_value=bad_response)
            yield client

        @asynccontextmanager
        async def exploding_client():
            client = MagicMock()
            client.get = AsyncMock(side_effect=RuntimeError("boom"))
            yield client

        src.http_client = ok_client  # type: ignore[assignment]
        assert await src.validate() is True

        src.http_client = bad_client  # type: ignore[assignment]
        assert await src.validate() is False

        src.http_client = exploding_client  # type: ignore[assignment]
        assert await src.validate() is False

    @pytest.mark.asyncio
    async def test_get_web_url_uses_instance_domain(self):
        src = GitLabSelfHostedSource()
        src.instance_url = "https://gitlab.example.com"
        src.api_version = "v4"
        src.personal_access_token = "pat"

        url = src._get_web_url(
            project_path="acme/thing",
            branch="main",
            item_path="src/app.py",
            is_blob=True,
        )
        assert url.startswith("https://gitlab.example.com/")
        assert "/-/blob/main/src/app.py" in url


class TestGitLabCloudConnectorPaths:
    @pytest.mark.asyncio
    async def test_cloud_create_with_and_without_config(self):
        src = await GitLabSource.create("tok", config={"project_id": "1", "branch": "main"})
        assert src.project_id == "1"
        assert src.branch == "main"

        src2 = await GitLabSource.create("tok")
        assert src2.project_id is None
        assert src2.branch == ""

    @pytest.mark.asyncio
    async def test_cloud_get_access_token_via_token_manager_and_headers(self):
        src = GitLabSource()
        src._token_manager = MagicMock()
        src._token_manager.get_valid_token = AsyncMock(return_value="newtok")

        assert await src.get_access_token() == "newtok"
        headers = await src._get_auth_headers()
        assert headers["Authorization"] == "Bearer newtok"

    @pytest.mark.asyncio
    async def test_cloud_get_auth_headers_raises_without_token(self):
        src = GitLabSource()
        src.access_token = None
        src._token_manager = None
        with pytest.raises(ValueError):
            await src._get_auth_headers()
