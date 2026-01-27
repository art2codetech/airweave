"""Unit tests for GitLab self-hosted connector.

These tests are intentionally lightweight and heavily mocked so we can
exercise the code paths added in the self-hosted connector without
needing a real GitLab instance.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.configs.config import GitLabSelfHostedConfig
from airweave.platform.sources.gitlab import GitLabSelfHostedSource


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
                config={"instance_url": "gitlab.example.com", "project_id": "123", "branch": "main"},
            )

        assert src.instance_url == "https://gitlab.example.com"
        assert src.base_url == "https://gitlab.example.com/api/v4"

        headers = await src._get_auth_headers()
        assert headers["PRIVATE-TOKEN"] == "pat"

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
    async def test_validate_true_false(self):
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

        src.http_client = ok_client  # type: ignore[assignment]
        assert await src.validate() is True

        src.http_client = bad_client  # type: ignore[assignment]
        assert await src.validate() is False
