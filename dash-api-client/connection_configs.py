"""
Connection Configuration Specifications

This file defines the required configuration fields for each supported connection type.
Each connection type specifies:
1. Required auth fields
2. Optional auth fields
3. Required config fields
4. Optional config fields
"""

from typing import Dict, List, TypedDict, Optional
from enum import Enum


class AuthConfig(TypedDict):
    """Authentication configuration specification."""
    required_fields: List[str]
    optional_fields: List[str]
    docs_url: str


class ConfigSpec(TypedDict):
    """Complete configuration specification for a connection type."""
    auth_config: AuthConfig
    required_config_fields: List[str]
    optional_config_fields: List[str]
    example: Dict


# Configuration specifications for each connection type
CONNECTION_CONFIGS: Dict[str, ConfigSpec] = {
    "google_calendar": {
        "auth_config": {
            "required_fields": [
                "access_token",
                "refresh_token",
                "client_id",
                "client_secret"
            ],
            "optional_fields": [],
            "docs_url": "https://docs.airweave.ai/docs/connectors/google_calendar#authentication"
        },
        "required_config_fields": [],
        "optional_config_fields": [
            "calendar_id",  # Specific calendar to sync, defaults to primary
            "start_time",   # Start of sync window
            "end_time"      # End of sync window
        ],
        "example": {
            "name": "My Google Calendar",
            "source_type": "google_calendar",
            "collection_id": "my_collection",
            "config": {
                "access_token": "ya29.a0...",
                "refresh_token": "1//...",
                "client_id": "your-client-id.apps.googleusercontent.com",
                "client_secret": "your-client-secret",
                "calendar_id": "primary"
            }
        }
    },
    
    "linear": {
        "auth_config": {
            "required_fields": [
                "access_token"
            ],
            "optional_fields": [],
            "docs_url": "https://docs.airweave.ai/docs/connectors/linear#authentication"
        },
        "required_config_fields": [],
        "optional_config_fields": [
            "team_id",      # Specific team to sync
            "project_id",   # Specific project to sync
            "exclude_path"  # Paths to exclude
        ],
        "example": {
            "name": "My Linear",
            "source_type": "linear",
            "collection_id": "my_collection",
            "config": {
                "access_token": "lin_oauth_...",
                "team_id": "optional_team_id"
            }
        }
    },
    
    "hubspot": {
        "auth_config": {
            "required_fields": [
                "access_token",
                "refresh_token"
            ],
            "optional_fields": [],
            "docs_url": "https://docs.airweave.ai/docs/connectors/hubspot#authentication"
        },
        "required_config_fields": [],
        "optional_config_fields": [
            "portal_id",    # HubSpot portal ID
            "object_types", # List of object types to sync
            "start_time",   # Start time for sync
            "end_time"      # End time for sync
        ],
        "example": {
            "name": "My HubSpot",
            "source_type": "hubspot",
            "collection_id": "my_collection",
            "config": {
                "access_token": "pat-...",
                "refresh_token": "refresh_token_value",
                "object_types": ["contacts", "companies", "deals"]
            }
        }
    },
    
    "slack": {
        "auth_config": {
            "required_fields": [
                "access_token"
            ],
            "optional_fields": [],
            "docs_url": "https://docs.airweave.ai/docs/connectors/slack#authentication"
        },
        "required_config_fields": [],
        "optional_config_fields": [
            "channels",     # List of channels to sync
            "exclude_channels", # List of channels to exclude
            "start_time"    # Start time for message history
        ],
        "example": {
            "name": "My Slack",
            "source_type": "slack",
            "collection_id": "my_collection",
            "config": {
                "access_token": "xoxb-...",
                "channels": ["general", "random"]
            }
        }
    },
    
    "notion": {
        "auth_config": {
            "required_fields": [
                "access_token"
            ],
            "optional_fields": [],
            "docs_url": "https://docs.airweave.ai/docs/connectors/notion#authentication"
        },
        "required_config_fields": [],
        "optional_config_fields": [
            "workspace_id",  # Specific workspace to sync
            "database_ids", # List of specific databases to sync
            "page_ids"      # List of specific pages to sync
        ],
        "example": {
            "name": "My Notion",
            "source_type": "notion",
            "collection_id": "my_collection",
            "config": {
                "access_token": "secret_...",
                "database_ids": ["database_id1", "database_id2"]
            }
        }
    },
    
    "gmail": {
        "auth_config": {
            "required_fields": [
                "access_token"
            ],
            "optional_fields": [
                "composio_api_key",
                "entity_id",
                "refresh_token",
                "client_id",
                "client_secret"
            ],
            "docs_url": "https://docs.airweave.ai/docs/connectors/gmail#authentication"
        },
        "required_config_fields": [],
        "optional_config_fields": [
            "labels",       # List of labels to sync
            "query",        # Gmail search query
            "start_time",   # Start time for email sync
            "max_results"   # Maximum number of emails to sync
        ],
        "example": {
            "name": "My Gmail with Composio",
            "source_type": "gmail",
            "collection_id": "my_collection",
            "config": {
                "access_token": "ya29.a0...",
                "composio_api_key": "your-composio-api-key",
                "entity_id": "your-entity-id",
                "labels": ["INBOX", "SENT"]
            }
        }
    }
}


def get_connection_config(source_type: str) -> Optional[ConfigSpec]:
    """Get the configuration specification for a connection type."""
    return CONNECTION_CONFIGS.get(source_type.lower())


def validate_connection_config(source_type: str, config: Dict) -> List[str]:
    """
    Validate a connection configuration against its specification.
    Returns a list of error messages, empty if valid.
    """
    errors = []
    spec = get_connection_config(source_type)
    
    if not spec:
        return [f"Unsupported connection type: {source_type}"]
    
    # Check required auth fields
    for field in spec["auth_config"]["required_fields"]:
        if field not in config:
            errors.append(f"Missing required auth field: {field}")
    
    # Check required config fields
    for field in spec["required_config_fields"]:
        if field not in config:
            errors.append(f"Missing required config field: {field}")
    
    return errors 