"""Configuration management for the Airweave Client API."""

import os
from typing import List


class AppConfig:
    """Application configuration."""
    
    def __init__(self):
        self.airweave_api_url = os.getenv("AIRWEAVE_API_URL", "http://localhost:8001")
        self.log_level = os.getenv("AIRWEAVE_LOG_LEVEL", "INFO")
        self.cors_origins = ["*"]
        
        # Default user configuration
        self.default_user_id = os.getenv("AIRWEAVE_DEFAULT_USER_ID", "dash_team")
        self.default_user_email = os.getenv("AIRWEAVE_DEFAULT_USER_EMAIL", "founders@usedash.ai")
        self.default_user_name = os.getenv("AIRWEAVE_DEFAULT_USER_NAME", "Dash Team")


def get_config() -> AppConfig:
    """Get application configuration."""
    return AppConfig() 