"""Redmine entity schemas.

Entity schemas for Redmine Projects, Issues, Wiki Pages, Journals (comments),
and Attachments for integration with Airweave platform.

Supports Redmine 4.2.x and newer.
"""

from typing import Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class RedmineProjectEntity(BaseEntity):
    """Schema for a Redmine Project.

    Reference:
        https://www.redmine.org/projects/redmine/wiki/Rest_Projects
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (project-{id})
    # - breadcrumbs (empty - projects are top-level)
    # - name (from project name)
    # - created_at (from created_on timestamp)
    # - updated_at (from updated_on timestamp)

    # API fields
    project_id: int = AirweaveField(
        ..., description="Numeric ID of the project.", embeddable=True, is_entity_id=True
    )
    identifier: str = AirweaveField(
        ...,
        description="Unique identifier of the project (e.g., 'my-project').",
        embeddable=True,
        is_name=True,
    )
    description: Optional[str] = AirweaveField(
        None, description="Description of the project.", embeddable=True
    )
    homepage: Optional[str] = AirweaveField(
        None, description="Project homepage URL.", embeddable=True
    )
    is_public: Optional[bool] = AirweaveField(
        None, description="Whether the project is public.", embeddable=True
    )
    parent_id: Optional[int] = AirweaveField(
        None, description="Parent project ID if this is a subproject.", embeddable=True
    )
    status: Optional[int] = AirweaveField(
        None, description="Project status (1=active, 5=closed, 9=archived).", embeddable=True
    )


class RedmineIssueEntity(BaseEntity):
    """Schema for a Redmine Issue.

    Reference:
        https://www.redmine.org/projects/redmine/wiki/Rest_Issues
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (issue-{id})
    # - breadcrumbs (project breadcrumb)
    # - name (from subject)
    # - created_at (from created_on timestamp)
    # - updated_at (from updated_on timestamp)

    # API fields
    issue_id: int = AirweaveField(
        ..., description="Numeric ID of the issue.", embeddable=True, is_entity_id=True
    )
    subject: str = AirweaveField(
        ..., description="Subject/title of the issue.", embeddable=True, is_name=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Detailed description of the issue.", embeddable=True
    )
    project_id: int = AirweaveField(
        ..., description="ID of the project this issue belongs to.", embeddable=True
    )
    project_name: Optional[str] = AirweaveField(
        None, description="Name of the project this issue belongs to.", embeddable=True
    )
    tracker_name: Optional[str] = AirweaveField(
        None, description="Type of the issue (Bug, Feature, Support, etc.).", embeddable=True
    )
    status_name: Optional[str] = AirweaveField(
        None,
        description="Current status of the issue (New, In Progress, Closed, etc.).",
        embeddable=True,
    )
    priority_name: Optional[str] = AirweaveField(
        None, description="Priority level of the issue (Low, Normal, High, etc.).", embeddable=True
    )
    assigned_to: Optional[str] = AirweaveField(
        None, description="Name of the user assigned to this issue.", embeddable=True
    )
    author: Optional[str] = AirweaveField(
        None, description="Name of the user who created this issue.", embeddable=True
    )
    start_date: Optional[str] = AirweaveField(
        None, description="Start date of the issue (YYYY-MM-DD).", embeddable=True
    )
    due_date: Optional[str] = AirweaveField(
        None, description="Due date of the issue (YYYY-MM-DD).", embeddable=True
    )
    done_ratio: Optional[int] = AirweaveField(
        None, description="Percentage of completion (0-100).", embeddable=True
    )
    estimated_hours: Optional[float] = AirweaveField(
        None, description="Estimated time in hours.", embeddable=True
    )
    spent_hours: Optional[float] = AirweaveField(
        None, description="Time spent on the issue in hours.", embeddable=True
    )
    closed_on: Optional[str] = AirweaveField(
        None, description="Timestamp when the issue was closed.", embeddable=True
    )


class RedmineWikiPageEntity(BaseEntity):
    """Schema for a Redmine Wiki Page.

    Reference:
        https://www.redmine.org/projects/redmine/wiki/Rest_WikiPages
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (wiki-{project_id}-{title})
    # - breadcrumbs (project breadcrumb)
    # - name (from title)
    # - created_at (from created_on timestamp)
    # - updated_at (from updated_on timestamp)

    # API fields
    title: str = AirweaveField(
        ...,
        description="Title of the wiki page.",
        embeddable=True,
        is_entity_id=True,
        is_name=True,
    )
    text: str = AirweaveField(
        ...,
        description="Content of the wiki page (in Textile or Markdown format).",
        embeddable=True,
    )
    version: Optional[int] = AirweaveField(
        None, description="Version number of the wiki page.", embeddable=True
    )
    author: Optional[str] = AirweaveField(
        None, description="Name of the user who last updated this page.", embeddable=True
    )
    comments: Optional[str] = AirweaveField(
        None, description="Comments about the last update.", embeddable=True
    )
    project_id: int = AirweaveField(
        ..., description="ID of the project this wiki page belongs to.", embeddable=True
    )
    project_name: Optional[str] = AirweaveField(
        None, description="Name of the project this wiki page belongs to.", embeddable=True
    )


class RedmineJournalEntity(BaseEntity):
    """Schema for a Redmine Journal (comment/change history).

    Journals track both comments and field changes on issues.

    Reference:
        https://www.redmine.org/projects/redmine/wiki/Rest_Issues
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (journal-{id})
    # - breadcrumbs (project + issue breadcrumbs)
    # - name (preview of notes or "Change log entry")
    # - created_at (from created_on timestamp)
    # - updated_at (None - journals don't update)

    # API fields
    journal_id: int = AirweaveField(
        ..., description="Numeric ID of the journal entry.", embeddable=True, is_entity_id=True
    )
    notes: Optional[str] = AirweaveField(
        None, description="Comment text of the journal entry.", embeddable=True, is_name=True
    )
    issue_id: int = AirweaveField(
        ..., description="ID of the issue this journal belongs to.", embeddable=True
    )
    author: Optional[str] = AirweaveField(
        None, description="Name of the user who created this journal entry.", embeddable=True
    )


class RedmineAttachmentEntity(BaseEntity):
    """Schema for a Redmine Attachment.

    Attachments can be associated with issues, wiki pages, and other entities.

    Reference:
        https://www.redmine.org/projects/redmine/wiki/Rest_api
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (attachment-{id})
    # - breadcrumbs (project + parent entity breadcrumbs)
    # - name (from filename)
    # - created_at (from created_on timestamp)
    # - updated_at (None - attachments don't update)

    # API fields
    attachment_id: int = AirweaveField(
        ..., description="Numeric ID of the attachment.", embeddable=True, is_entity_id=True
    )
    filename: str = AirweaveField(
        ..., description="Name of the attached file.", embeddable=True, is_name=True
    )
    filesize: Optional[int] = AirweaveField(
        None, description="Size of the file in bytes.", embeddable=True
    )
    content_type: Optional[str] = AirweaveField(
        None, description="MIME type of the file.", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Description of the attachment.", embeddable=True
    )
    content_url: Optional[str] = AirweaveField(
        None, description="URL to download the attachment content.", embeddable=True
    )
    author: Optional[str] = AirweaveField(
        None, description="Name of the user who uploaded this attachment.", embeddable=True
    )
    issue_id: Optional[int] = AirweaveField(
        None,
        description="ID of the issue this attachment belongs to (if applicable).",
        embeddable=True,
    )
