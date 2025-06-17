"""
Test source sync operations using the new public API.

This test validates that various sources can successfully sync data through the new
source connections API. It creates integration credentials directly in the database (since we
have the raw tokens) and then uses the public API to create and run source connections.

How this test works:
1. For each source in @pytest.mark.parametrize:
   - Retrieve credentials from environment variables (as JSON strings)
   - Create IntegrationCredential directly in database with encrypted credentials
   - Use POST /source-connections/ to create a source connection with the credential_id
   - Use POST /source-connections/{id}/run to trigger a sync
   - Poll the job status until completion
   - Assert the sync completed successfully
   - Clean up test resources (source connection and collection)

To add a new source:
1. Add the source's short_name to @pytest.mark.parametrize
2. Add credentials to environment as JSON matching the source's auth config class
3. Ensure the source is properly configured in the backend

Example credential formats:
- Stripe: {"api_key": "sk_test_..."}
- Dropbox: {"refresh_token": "...", "access_token": "", "client_id": "...", "client_secret": "..."}
- PostgreSQL: {"host": "localhost", "port": 5432, "database": "mydb", "user": "postgres", "password": "secret", "schema": "public", "tables": "*"}
- GitHub: {"personal_access_token": "ghp_...", "repo_name": "owner/repo"}
- Notion: {"access_token": "secret_..."}
"""

import os
import json
import uuid
import time
import pytest
import requests
import asyncio
from typing import Dict, Any, Optional

from airweave import crud, schemas
from airweave.core import credentials
from airweave.core.config import settings
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.integration_credential import IntegrationType

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture
def creds() -> Dict[str, Optional[str]]:
    """Fixture providing credentials for all test connectors.

    Credentials should be JSON strings that match the source's auth config class.

    Set environment variables like:
    - STRIPE_CREDS='{"api_key": "sk_test_..."}'
    - DROPBOX_CREDS='{"refresh_token": "...", "access_token": "", "client_id": "...", "client_secret": "..."}'
    - POSTGRESQL_CREDS='{"host": "localhost", "port": 5432, "database": "mydb", "user": "postgres", "password": "secret"}'
    """
    return {
        "dropbox": os.getenv("DROPBOX_CREDS"),
        "google_drive": os.getenv("GDRIVE_CREDS"),
        "asana": os.getenv("ASANA_CREDS"),
        "notion": os.getenv("NOTION_CREDS"),
        "linear": os.getenv("LINEAR_CREDS"),
        "github": os.getenv("GITHUB_CREDS"),
        "stripe": os.getenv("STRIPE_CREDS"),
        "postgresql": os.getenv("POSTGRESQL_CREDS"),
    }


@pytest.mark.parametrize("service_name", ["stripe"])  # Add more: "dropbox", "asana", "google_drive", "github", "postgresql", etc.
def test_sources(
    e2e_environment, e2e_api_url: str, creds: Dict[str, str], service_name: str
):
    """Test end-to-end sync for any source using the new public API.

    This test is source-agnostic - it works with any source as long as the
    credentials match the source's auth config class.

    Args:
        e2e_environment: The E2E test environment fixture
        e2e_api_url: The API URL for testing
        creds: Dictionary of credentials from environment
        service_name: The source to test
    """
    # Get credentials for this source
    credential_json = creds.get(service_name)
    if not credential_json or credential_json == "None":
        pytest.skip(f"No credentials available for {service_name}. Please set {service_name.upper()}_CREDS environment variable.")

    print(f"\n🔄 Testing {service_name} sync via new public API")
    print(f"  Credential JSON: {credential_json[:100]}..." if len(credential_json) > 100 else f"  Credential JSON: {credential_json}")

    # 1. Create integration credential directly in database
    credential_id = asyncio.run(
        create_integration_credential(service_name, credential_json)
    )
    print(f"✓ Created integration credential: {credential_id}")

    # Debug: Ensure credential_id is not None
    if credential_id is None:
        raise ValueError(f"Failed to create integration credential for {service_name}")

    # 2. Create source connection via public API
    source_conn_data = {
        "name": f"Test {service_name.capitalize()} Connection",
        "description": f"E2E test connection for {service_name}",
        "short_name": service_name,
        "credential_id": str(credential_id),
        "sync_immediately": False,  # We'll trigger manually for better control
        # Collection will be auto-created
    }

    response = requests.post(
        f"{e2e_api_url}/source-connections/",
        json=source_conn_data
    )

    if response.status_code != 200:
        # Parse credentials to show what fields were provided (without sensitive values)
        try:
            cred_dict = json.loads(credential_json)
            provided_fields = list(cred_dict.keys())
            print(f"\n❌ Failed to create source connection")
            print(f"   Source: {service_name}")
            print(f"   Provided credential fields: {provided_fields}")
            print(f"   Response: {response.status_code} - {response.text}")
        except:
            pass

    assert response.status_code == 200, f"Failed to create source connection: {response.text}"

    source_conn = response.json()
    source_conn_id = source_conn["id"]
    collection_id = source_conn["collection"]

    print(f"✓ Created source connection: {source_conn_id}")
    print(f"  - Name: {source_conn['name']}")
    print(f"  - Collection: {collection_id}")
    print(f"  - Status: {source_conn['status']}")

    # 3. Trigger sync run
    print(f"\n📤 Triggering sync for {service_name}...")
    response = requests.post(f"{e2e_api_url}/source-connections/{source_conn_id}/run")
    assert response.status_code == 200, f"Failed to run sync: {response.text}"

    sync_job = response.json()
    job_id = sync_job["id"]

    print(f"✓ Sync job started: {job_id}")
    print(f"  - Status: {sync_job['status']}")

    # 4. Wait for sync completion
    print(f"\n⏳ Waiting for sync to complete...")
    job_status = wait_for_sync_completion(
        e2e_api_url, source_conn_id, job_id, timeout=300
    )

    # 5. Verify sync completed successfully
    assert job_status["status"].upper() == "COMPLETED", (
        f"Sync job failed or timed out. Status: {job_status.get('status')}. "
        f"Error: {job_status.get('error', 'No error message')}"
    )

    print(f"\n✅ Successfully completed sync test for {service_name}")
    print(f"  - Entities processed: {job_status.get('entities_encountered', 0)}")
    print(f"  - Items inserted: {job_status.get('inserted', 0)}")
    print(f"  - Items updated: {job_status.get('updated', 0)}")

    # 6. Cleanup
    cleanup_source_connection(e2e_api_url, source_conn_id, collection_id)


async def create_integration_credential(
    service_name: str, credential_json: str
) -> uuid.UUID:
    """Create integration credential directly in database.

    This is necessary because we have raw credentials that need to be
    properly encrypted and stored before they can be used by source connections.

    Args:
        service_name: The short name of the source
        credential_json: JSON string containing credentials matching the source's auth config

    Returns:
        The UUID of the created integration credential
    """
    # Setup test database connection
    original_uri = settings.SQLALCHEMY_ASYNC_DATABASE_URI
    settings.SQLALCHEMY_ASYNC_DATABASE_URI = (
        "postgresql+asyncpg://airweave:airweave1234!@localhost:9432/airweave"
    )

    print(f"\n  Creating credential for {service_name}...")
    print(f"  Database URI: {settings.SQLALCHEMY_ASYNC_DATABASE_URI}")

    async_engine = create_async_engine(
        str(settings.SQLALCHEMY_ASYNC_DATABASE_URI),
        pool_size=10,
        max_overflow=5,
        pool_pre_ping=True,
        isolation_level="READ COMMITTED",
    )

    AsyncSessionLocal = async_sessionmaker(
        autocommit=False, autoflush=False, bind=async_engine
    )

    async with AsyncSessionLocal() as db:
        try:
            # Get source definition
            source = await crud.source.get_by_short_name(db, service_name)
            if not source:
                raise ValueError(f"Source {service_name} not found in database")

            print(f"  Found source: {source.name} (auth_type: {source.auth_type})")

            # Get test user
            user_db = await crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)
            if not user_db:
                raise ValueError(f"Test user {settings.FIRST_SUPERUSER} not found")
            user = schemas.User.model_validate(user_db)

            print(f"  Found user: {user.email}")

            # Parse credentials - they should be a JSON string
            try:
                cred_dict = json.loads(credential_json)
                print(f"  Parsed credentials with fields: {list(cred_dict.keys())}")
            except (json.JSONDecodeError, TypeError) as e:
                # If it's not valid JSON, assume it's already a dict
                raise ValueError(
                    f"Credentials for {service_name} must be a valid JSON string. "
                    f"Error: {e}. Got: {credential_json[:50]}..."
                )

            # Encrypt credentials
            settings.ENCRYPTION_KEY = "SpgLrrEEgJ/7QdhSMSvagL1juEY5eoyCG0tZN7OSQV0="
            encrypted_credentials = credentials.encrypt(cred_dict)

            print(f"  Encrypted credentials successfully")

            # Create integration credential
            async with UnitOfWork(db) as uow:
                credential_in = schemas.IntegrationCredentialCreateEncrypted(
                    name=f"E2E Test - {source.name}",
                    description=f"Auto-created for E2E testing of {source.name}",
                    integration_short_name=source.short_name,
                    integration_type=IntegrationType.SOURCE,
                    auth_type=source.auth_type,
                    encrypted_credentials=encrypted_credentials,
                    auth_config_class=source.auth_config_class,
                )

                credential = await crud.integration_credential.create(
                    uow.session, obj_in=credential_in, current_user=user, uow=uow
                )

                await uow.session.flush()

                credential_id = credential.id
                print(f"  Created credential with ID: {credential_id}")

                await uow.commit()
                print(f"  Transaction committed successfully")

            return credential_id

        except Exception as e:
            print(f"  ❌ Error creating credential: {type(e).__name__}: {e}")
            raise
        finally:
            await db.close()
            # Restore original URI
            settings.SQLALCHEMY_ASYNC_DATABASE_URI = original_uri


def wait_for_sync_completion(
    api_url: str,
    source_conn_id: str,
    job_id: str,
    timeout: int = 300,
    poll_interval: int = 5
) -> Dict[str, Any]:
    """Wait for a sync job to complete and return final status.

    Args:
        api_url: The API base URL
        source_conn_id: The source connection ID
        job_id: The sync job ID
        timeout: Maximum seconds to wait
        poll_interval: Seconds between status checks

    Returns:
        The final job status dictionary

    Raises:
        AssertionError: If job times out
    """
    elapsed = 0

    while elapsed < timeout:
        response = requests.get(
            f"{api_url}/source-connections/{source_conn_id}/jobs/{job_id}"
        )
        assert response.status_code == 200, f"Failed to get job status: {response.text}"

        job_status = response.json()
        current_status = job_status["status"].upper()

        if current_status == "COMPLETED":
            return job_status
        elif current_status == "FAILED":
            return job_status

        # Show progress
        entities = job_status.get("entities_encountered", 0)
        print(f"  Status: {current_status} | Entities: {entities} | Elapsed: {elapsed}s", end="\r")

        time.sleep(poll_interval)
        elapsed += poll_interval

    raise AssertionError(f"Sync job timed out after {timeout} seconds")


def cleanup_source_connection(
    api_url: str, source_conn_id: str, collection_id: str
) -> None:
    """Clean up test resources.

    Args:
        api_url: The API base URL
        source_conn_id: The source connection to delete
        collection_id: The collection to delete
    """
    print("\n🧹 Cleaning up test resources...")

    # Delete source connection (will cascade delete sync, etc.)
    response = requests.delete(
        f"{api_url}/source-connections/{source_conn_id}?delete_data=true"
    )
    if response.status_code == 200:
        print(f"✓ Deleted source connection: {source_conn_id}")
    else:
        print(f"⚠️  Failed to delete source connection: {response.status_code}")

    # Delete collection
    response = requests.delete(
        f"{api_url}/collections/{collection_id}?delete_data=true"
    )
    if response.status_code == 200:
        print(f"✓ Deleted collection: {collection_id}")
    else:
        print(f"⚠️  Failed to delete collection: {response.status_code}")
