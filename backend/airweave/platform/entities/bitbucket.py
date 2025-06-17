"""Bitbucket entity schemas.

Based on the Bitbucket REST API, we define entity schemas for:
  • Workspace
  • Repository
  • Repository Contents (files and directories)

References:
  • https://developer.atlassian.com/cloud/bitbucket/rest/intro/
  • https://developer.atlassian.com/cloud/bitbucket/rest/api-group-repositories/
"""

from datetime import datetime
from typing import Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity, CodeFileEntity, ParentEntity


class BitbucketWorkspaceEntity(ParentEntity):
    """Schema for Bitbucket workspace entity."""

    slug: str = Field(..., description="Workspace slug identifier")
    name: str = Field(..., description="Workspace display name")
    uuid: str = Field(..., description="Workspace UUID")
    is_private: bool = Field(..., description="Whether the workspace is private")
    created_on: Optional[datetime] = Field(None, description="Creation timestamp")


class BitbucketRepositoryEntity(ParentEntity):
    """Schema for Bitbucket repository entity."""

    name: str = Field(..., description="Repository name")
    slug: str = Field(..., description="Repository slug")
    full_name: str = Field(..., description="Full repository name including workspace")
    description: Optional[str] = Field(None, description="Repository description")
    is_private: bool = Field(..., description="Whether the repository is private")
    fork_policy: Optional[str] = Field(None, description="Fork policy of the repository")
    language: Optional[str] = Field(None, description="Primary language of the repository")
    created_on: datetime = Field(..., description="Creation timestamp")
    updated_on: datetime = Field(..., description="Last update timestamp")
    size: Optional[int] = Field(None, description="Size of the repository in bytes")
    mainbranch: Optional[str] = Field(None, description="Main branch name")
    workspace_slug: str = Field(..., description="Slug of the parent workspace")


class BitbucketDirectoryEntity(ChunkEntity):
    """Schema for Bitbucket directory entity."""

    path: str = Field(..., description="Path of the directory within the repository")
    repo_slug: str = Field(..., description="Slug of the repository containing this directory")
    repo_full_name: str = Field(..., description="Full name of the repository")
    workspace_slug: str = Field(..., description="Slug of the workspace")


class BitbucketCodeFileEntity(CodeFileEntity):
    """Schema for Bitbucket code file entity."""

    # Bitbucket specific fields only
    commit_hash: Optional[str] = Field(None, description="Commit hash of the file version")
    path: str = Field(..., description="Path of the file within the repository")
    repo_slug: str = Field(..., description="Slug of the repository")
    repo_full_name: str = Field(..., description="Full name of the repository")
    workspace_slug: str = Field(..., description="Slug of the workspace")
