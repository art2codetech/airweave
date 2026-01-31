"""Redmine entity schemas.

Defines entities for Redmine projects and issues.
"""

from datetime import datetime
from typing import Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class RedmineProjectEntity(BaseEntity):
    """Schema for a Redmine Project."""

    project_id: str = AirweaveField(
        ..., description="Unique numeric identifier for the project.", is_entity_id=True
    )
    identifier: str = AirweaveField(..., description="Project identifier (slug).", embeddable=True)
    name: str = AirweaveField(..., description="Project name.", embeddable=True, is_name=True)
    description: Optional[str] = AirweaveField(
        None, description="Project description.", embeddable=True
    )
    status: Optional[str] = AirweaveField(None, description="Project status.", embeddable=True)
    web_url_value: Optional[str] = AirweaveField(
        None, description="Link to the project in Redmine.", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """UI link for the Redmine project."""
        return self.web_url_value or ""


class RedmineIssueEntity(BaseEntity):
    """Schema for a Redmine Issue."""

    issue_id: str = AirweaveField(
        ..., description="Unique identifier for the issue.", is_entity_id=True
    )
    subject: str = AirweaveField(..., description="Issue subject.", embeddable=True, is_name=True)
    description: Optional[str] = AirweaveField(
        None, description="Issue description.", embeddable=True
    )
    status: Optional[str] = AirweaveField(None, description="Issue status.", embeddable=True)
    tracker: Optional[str] = AirweaveField(None, description="Issue tracker type.", embeddable=True)
    priority: Optional[str] = AirweaveField(None, description="Issue priority.", embeddable=True)
    author: Optional[str] = AirweaveField(None, description="Issue author.", embeddable=True)
    assignee: Optional[str] = AirweaveField(None, description="Issue assignee.", embeddable=True)
    project_id: str = AirweaveField(..., description="Project ID for the issue.", embeddable=True)
    project_identifier: Optional[str] = AirweaveField(
        None, description="Project identifier (slug).", embeddable=True
    )
    created_time: datetime = AirweaveField(
        ..., description="Timestamp when the issue was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="Timestamp when the issue was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="Link to the issue in Redmine.", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """UI link for the Redmine issue."""
        return self.web_url_value or ""
