# Airweave API Documentation

Complete documentation for all Airweave REST API endpoints. This includes both the **Backend API** (port 8001) and the **Dash API Client** (port 8002) endpoints.

## Table of Contents

1. [Authentication](#authentication)
2. [Backend API Endpoints (Port 8001)](#backend-api-endpoints-port-8001)
   - [Health](#health)
   - [Collections](#collections)
   - [Source Connections](#source-connections)
   - [Search](#search)
   - [Sync](#sync)
3. [Dash API Client Endpoints (Port 8002)](#dash-api-client-endpoints-port-8002)
4. [Common Schemas](#common-schemas)
5. [Error Handling](#error-handling)

---

## Authentication

Airweave uses header-based user context for multi-tenancy:

```http
X-User-ID: your_user_id
X-User-Email: user@example.com
X-User-Name: User Name
```

If no user headers are provided, default user configuration is used.

---

## Backend API Endpoints (Port 8001)

Base URL: `http://localhost:8001`

### Health

#### GET /health
**Description**: Check if the API is healthy.

**Request**:
```bash
curl -X GET "http://localhost:8001/health"
```

**Response**:
```json
{
  "status": "healthy"
}
```

---

### Collections

Collections are logical groups of data sources that provide unified search capabilities.

#### GET /collections/
**Description**: List all collections for the current user's organization.

**Parameters**:
- `skip` (query, int, optional): Number of collections to skip (default: 0)
- `limit` (query, int, optional): Maximum number of collections to return (default: 100)

**Request**:
```bash
curl -X GET "http://localhost:8001/collections/" \
  -H "X-User-ID: test_user" \
  -H "X-User-Email: test@example.com" \
  -H "Content-Type: application/json"
```

**Response**:
```json
[
  {
    "id": "acc57488-2839-4737-a1cb-e14728cb87f5",
    "readable_id": "test-collection",
    "name": "Test Collection",
    "description": null,
    "created_at": "2025-06-17T05:52:40.930991",
    "modified_at": "2025-06-17T05:52:40.930994",
    "organization_id": "88d07a82-ccfd-4445-a498-4fadfc946c23",
    "created_by_email": "admin@example.com",
    "modified_by_email": "admin@example.com",
    "status": "NEEDS SOURCE"
  }
]
```

#### POST /collections/
**Description**: Create a new collection.

**Request Body**:
```json
{
  "name": "My New Collection",
  "readable_id": "my-new-collection",
  "description": "Optional description"
}
```

**Request**:
```bash
curl -X POST "http://localhost:8001/collections/" \
  -H "X-User-ID: test_user" \
  -H "X-User-Email: test@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My New Collection",
    "readable_id": "my-new-collection",
    "description": "Optional description"
  }'
```

**Response**:
```json
{
  "id": "new-uuid-here",
  "readable_id": "my-new-collection",
  "name": "My New Collection",
  "description": "Optional description",
  "created_at": "2025-06-17T06:00:00.000000",
  "modified_at": "2025-06-17T06:00:00.000000",
  "organization_id": "org-uuid",
  "created_by_email": "test@example.com",
  "modified_by_email": "test@example.com",
  "status": "NEEDS SOURCE"
}
```

#### GET /collections/{readable_id}/
**Description**: Get a specific collection by readable ID.

**Parameters**:
- `readable_id` (path, string, required): The readable ID of the collection

**Request**:
```bash
curl -X GET "http://localhost:8001/collections/test-collection/" \
  -H "X-User-ID: test_user" \
  -H "X-User-Email: test@example.com"
```

**Response**: Same as collection object in list response.

#### PUT /collections/{readable_id}/
**Description**: Update a collection.

**Request Body**:
```json
{
  "name": "Updated Collection Name",
  "description": "Updated description"
}
```

#### DELETE /collections/{readable_id}/
**Description**: Delete a collection.

**Request**:
```bash
curl -X DELETE "http://localhost:8001/collections/test-collection/" \
  -H "X-User-ID: test_user" \
  -H "X-User-Email: test@example.com"
```

#### GET /collections/{readable_id}/search/
**Description**: Search within a collection.

**Parameters**:
- `readable_id` (path, string, required): The readable ID of the collection
- `query` (query, string, required): Search query
- `response_type` (query, enum, optional): Type of response (raw/ai_completion, default: raw)

**Request**:
```bash
curl -X GET "http://localhost:8001/collections/test-collection/search/?query=test%20query&limit=10" \
  -H "X-User-ID: test_user" \
  -H "X-User-Email: test@example.com"
```

**Response**:
```json
{
  "results": [
    {
      "id": "result-id",
      "score": 0.95,
      "metadata": {
        "source": "github",
        "file_path": "/path/to/file"
      },
      "content": "Search result content..."
    }
  ],
  "query": "test query"
}
```

#### POST /collections/{readable_id}/refresh_all/
**Description**: Start sync jobs for all source connections in the collection.

**Request**:
```bash
curl -X POST "http://localhost:8001/collections/test-collection/refresh_all/" \
  -H "X-User-ID: test_user" \
  -H "X-User-Email: test@example.com"
```

**Response**:
```json
[
  {
    "id": "job-uuid",
    "source_connection_id": "connection-uuid",
    "status": "PENDING",
    "created_at": "2025-06-17T06:00:00.000000"
  }
]
```

---

### Source Connections

Source connections are configured instances that sync data from external sources.

#### GET /source-connections/
**Description**: List all source connections for the current user.

**Parameters**:
- `collection` (query, string, optional): Filter by collection readable ID
- `skip` (query, int, optional): Number of connections to skip (default: 0)
- `limit` (query, int, optional): Maximum number of connections to return (default: 100)

**Request**:
```bash
curl -X GET "http://localhost:8001/source-connections/?collection=test-collection" \
  -H "X-User-ID: test_user" \
  -H "X-User-Email: test@example.com"
```

**Response**:
```json
[
  {
    "id": "connection-uuid",
    "name": "My GitHub Connection",
    "description": "GitHub repo connection",
    "short_name": "github",
    "status": "ACTIVE",
    "created_at": "2025-06-17T06:00:00.000000",
    "modified_at": "2025-06-17T06:00:00.000000",
    "sync_id": "sync-uuid",
    "collection": "test-collection",
    "white_label_id": null
  }
]
```

#### POST /source-connections/
**Description**: Create a new source connection.

**Request Body**:
```json
{
  "name": "My Slack Connection",
  "description": "Slack workspace connection",
  "short_name": "slack",
  "collection": "test-collection",
  "auth_fields": {
    "bot_token": "xoxb-your-bot-token"
  },
  "config_fields": {
    "channels": ["general", "development"]
  },
  "sync_immediately": true
}
```

**Request**:
```bash
curl -X POST "http://localhost:8001/source-connections/" \
  -H "X-User-ID: test_user" \
  -H "X-User-Email: test@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Slack Connection",
    "short_name": "slack",
    "collection": "test-collection",
    "auth_fields": {
      "bot_token": "xoxb-your-bot-token"
    },
    "config_fields": {
      "channels": ["general", "development"]
    },
    "sync_immediately": true
  }'
```

**Response**:
```json
{
  "id": "new-connection-uuid",
  "name": "My Slack Connection",
  "description": null,
  "short_name": "slack",
  "config_fields": {
    "channels": ["general", "development"]
  },
  "auth_fields": "****",
  "status": "IN_PROGRESS",
  "sync_id": "sync-uuid",
  "collection": "test-collection",
  "created_at": "2025-06-17T06:00:00.000000",
  "modified_at": "2025-06-17T06:00:00.000000",
  "organization_id": "org-uuid",
  "created_by_email": "test@example.com",
  "modified_by_email": "test@example.com"
}
```

#### GET /source-connections/{source_connection_id}/
**Description**: Get a specific source connection by ID.

**Parameters**:
- `source_connection_id` (path, UUID, required): The ID of the source connection

#### PUT /source-connections/{source_connection_id}/
**Description**: Update a source connection.

#### DELETE /source-connections/{source_connection_id}/
**Description**: Delete a source connection.

#### POST /source-connections/{source_connection_id}/run/
**Description**: Trigger a sync run for a source connection.

**Parameters**:
- `source_connection_id` (path, UUID, required): The ID of the source connection

**Request Body**:
```json
{
  "access_token": "optional-override-token"
}
```

**Request**:
```bash
curl -X POST "http://localhost:8001/source-connections/connection-uuid/run/" \
  -H "X-User-ID: test_user" \
  -H "X-User-Email: test@example.com" \
  -H "Content-Type: application/json"
```

**Response**:
```json
{
  "id": "job-uuid",
  "source_connection_id": "connection-uuid",
  "status": "PENDING",
  "created_at": "2025-06-17T06:00:00.000000",
  "started_at": null,
  "completed_at": null,
  "entities_inserted": 0,
  "entities_updated": 0,
  "entities_deleted": 0,
  "error": null
}
```

#### GET /source-connections/{source_connection_id}/jobs/
**Description**: List all sync jobs for a source connection.

**Request**:
```bash
curl -X GET "http://localhost:8001/source-connections/connection-uuid/jobs/" \
  -H "X-User-ID: test_user" \
  -H "X-User-Email: test@example.com"
```

**Response**:
```json
[
  {
    "id": "job-uuid",
    "source_connection_id": "connection-uuid",
    "status": "COMPLETED",
    "created_at": "2025-06-17T05:00:00.000000",
    "started_at": "2025-06-17T05:00:01.000000",
    "completed_at": "2025-06-17T05:05:00.000000",
    "entities_inserted": 150,
    "entities_updated": 25,
    "entities_deleted": 5,
    "entities_kept": 300,
    "entities_skipped": 0,
    "error": null
  }
]
```

---

### Search

#### Note: Search is accessed via collection endpoint
See [Collections Search](#get-collectionsreadable_idsearch) above.

---

### Sync

System-level sync management (usually handled via source connections).

#### GET /sync/
**Description**: List all syncs for the current user.

**Parameters**:
- `skip` (query, int, optional): Number of syncs to skip (default: 0)
- `limit` (query, int, optional): Maximum number of syncs to return (default: 100)
- `with_source_connection` (query, bool, optional): Include source connection details

#### POST /sync/
**Description**: Create a new sync configuration.

**Request Body**:
```json
{
  "name": "My Sync",
  "source_connection_id": "connection-uuid",
  "destination_connection_ids": ["dest-uuid"],
  "cron_schedule": "0 */6 * * *",
  "run_immediately": true
}
```

---

## Dash API Client Endpoints (Port 8002)

Base URL: `http://localhost:8002`

The Dash API Client provides a simplified REST interface that wraps the backend API.

### Health

#### GET /health
**Description**: Check if the Dash API Client is healthy.

**Request**:
```bash
curl -X GET "http://localhost:8002/health"
```

**Response**:
```json
{
  "status": "healthy",
  "service": "airweave-client-api"
}
```

### Collections

#### GET /collections
**Description**: List all collections.

**Request**:
```bash
curl -X GET "http://localhost:8002/collections" \
  -H "X-User-ID: test_user" \
  -H "X-User-Email: test@example.com"
```

**Response**:
```json
[
  {
    "id": "collection-uuid",
    "readable_id": "test-collection",
    "name": "Test Collection",
    "description": null,
    "created_at": "2025-06-17T05:52:40.930991"
  }
]
```

#### POST /collections
**Description**: Create a new collection.

**Request Body**:
```json
{
  "name": "My Collection",
  "description": "Collection description",
  "id": "custom-id"
}
```

**Request**:
```bash
curl -X POST "http://localhost:8002/collections" \
  -H "X-User-ID: test_user" \
  -H "X-User-Email: test@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Collection",
    "description": "Collection description"
  }'
```

#### GET /collections/{id}
**Description**: Get a specific collection.

#### DELETE /collections/{id}
**Description**: Delete a collection.

### Connections

#### POST /connections
**Description**: Create a new connection.

**Request Body**:
```json
{
  "name": "GitHub Connection",
  "source_type": "github",
  "collection_id": "test-collection",
  "config": {
    "access_token": "github-token",
    "repo": "owner/repo"
  }
}
```

**Request**:
```bash
curl -X POST "http://localhost:8002/connections" \
  -H "X-User-ID: test_user" \
  -H "X-User-Email: test@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GitHub Connection",
    "source_type": "github", 
    "collection_id": "test-collection",
    "config": {
      "access_token": "github-token",
      "repo": "owner/repo"
    }
  }'
```

**Response**:
```json
{
  "id": "connection-uuid",
  "name": "GitHub Connection",
  "source_type": "github",
  "collection_name": "Test Collection",
  "status": "in_progress",
  "created_at": "2025-06-17T06:00:00.000000"
}
```

#### GET /connections
**Description**: List connections.

**Parameters**:
- `collection_id` (query, string, optional): Filter by collection ID

### Sync

#### POST /sync
**Description**: Trigger a sync.

**Request Body**:
```json
{
  "connection_id": "connection-uuid"
}
```

**Response**:
```json
{
  "sync_id": "job-uuid",
  "connection_id": "connection-uuid", 
  "status": "pending",
  "started_at": "2025-06-17T06:00:00.000000"
}
```

#### GET /sync/latest/{connection_id}
**Description**: Get latest sync status for a connection.

### Search

#### POST /search
**Description**: Search within collections.

**Request Body**:
```json
{
  "query": "search terms",
  "collection_id": "test-collection",
  "limit": 10
}
```

**Response**:
```json
{
  "query": "search terms",
  "results": [
    {
      "id": "result-id",
      "score": 0.95,
      "content": "Result content...",
      "metadata": {
        "source": "github"
      }
    }
  ],
  "total_results": 1,
  "collection": "test-collection"
}
```

### Source Connections

#### POST /source_connections/{connection_id}/run
**Description**: Run a sync for a source connection.

**Parameters**:
- `connection_id` (path, string, required): The ID of the source connection
- `access_token` (query, string, optional): Optional access token override

---

## Common Schemas

### Source Types
Supported source types for connections:

```
github, notion, slack, google_drive, google_calendar, gmail, confluence, 
jira, linear, hubspot, asana, clickup, dropbox, elasticsearch, intercom, 
monday, mysql, onedrive, oracle, outlook_calendar, outlook_mail, 
postgresql, sql_server, sqlite, stripe, todoist, trello, zendesk
```

### Connection Status
- `ACTIVE`: Connection is working normally
- `IN_PROGRESS`: Connection is being set up or syncing
- `FAILED`: Connection has failed
- `NEEDS_AUTH`: Connection needs re-authentication

### Sync Job Status
- `PENDING`: Job is queued
- `RUNNING`: Job is currently executing
- `COMPLETED`: Job finished successfully
- `FAILED`: Job failed with error
- `CANCELLED`: Job was cancelled

---

## Error Handling

### HTTP Status Codes
- `200`: Success
- `201`: Created
- `400`: Bad Request (validation errors)
- `401`: Unauthorized
- `404`: Not Found
- `500`: Internal Server Error
- `503`: Service Unavailable (vector database offline)

### Error Response Format
```json
{
  "detail": "Error description"
}
```

### Validation Error Format
```json
{
  "detail": {
    "errors": [
      {
        "field": "name",
        "message": "Field is required"
      }
    ]
  }
}
```

---

## Examples

### Complete Workflow Example

1. **Create a Collection**:
```bash
curl -X POST "http://localhost:8001/collections/" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Data", "readable_id": "my-data"}'
```

2. **Create a Source Connection**:
```bash
curl -X POST "http://localhost:8001/source-connections/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GitHub Repo",
    "short_name": "github",
    "collection": "my-data",
    "auth_fields": {"access_token": "github-token"},
    "config_fields": {"repo": "owner/repo"},
    "sync_immediately": true
  }'
```

3. **Search the Collection**:
```bash
curl -X GET "http://localhost:8001/collections/my-data/search/?query=function" \
  -H "Content-Type: application/json"
```

### Using User Context Headers
```bash
curl -X GET "http://localhost:8001/collections/" \
  -H "X-User-ID: john_doe" \
  -H "X-User-Email: john@company.com" \
  -H "X-User-Name: John Doe" \
  -H "Content-Type: application/json"
```

---

This documentation covers all major endpoints and usage patterns for both the Airweave backend API and the Dash API Client. For the most up-to-date API specifications, visit:

- **Backend API Docs**: http://localhost:8001/docs
- **Dash API Docs**: http://localhost:8002/docs 