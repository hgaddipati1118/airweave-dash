"""
Airweave Client API

A FastAPI service that provides REST endpoints for interacting with Airweave.
This service wraps the airweave_client library and provides a REST API interface
for other applications to use.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from airweave_client import AirweaveClient, AirweaveConfig, AppUser
from config import get_config
from dependencies import set_global_client, set_default_user
from utils import setup_logging
from routers import (
    router as collections_router,
    connections_router,
    sync_router,
    search_router,
    source_connections_router
)

# Load environment variables
load_dotenv()

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup the Airweave client."""
    config = get_config()
    
    # Initialize client and user
    client = AirweaveClient(AirweaveConfig(base_url=config.airweave_api_url))
    user = AppUser(
        user_id=config.default_user_id,
        email=config.default_user_email,
        name=config.default_user_name
    )
    
    # Set global dependencies
    set_global_client(client)
    set_default_user(user)
    
    logger.info("Airweave Client API started")
    yield
    logger.info("Airweave Client API stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Airweave Client API",
        description="REST API for interacting with Airweave backend",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    config = get_config()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Health check
    @app.get("/health")
    def health_check():
        return {"status": "healthy", "service": "airweave-client-api"}
    
    # Include routers
    app.include_router(collections_router, prefix="/collections", tags=["Collections"])
    app.include_router(connections_router, prefix="/connections", tags=["Connections"])
    app.include_router(sync_router, prefix="/sync", tags=["Sync"])
    app.include_router(search_router, prefix="/search", tags=["Search"])
    app.include_router(source_connections_router, prefix="/source_connections", tags=["Source Connections"])
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002) 