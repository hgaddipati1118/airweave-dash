# Airweave Complete System Setup

This guide shows how to run the complete Airweave system including the backend API and the Dash API client using Docker Compose.

## 🚀 Quick Start

### Option 1: Use the Complete Startup Script (Recommended)

```bash
# Run the complete system startup script
cd docker
./start-all.sh
```

This script will:
- Set up environment variables if needed
- Start all services (backend, dash-api-client, temporal, databases)
- Perform health checks
- Display service status and URLs

### Option 2: Manual Docker Compose

```bash
# Make sure you have a .env file (run ../start.sh first if needed)
docker compose -f docker-compose.yml up -d
```

## 📊 Services & Ports

After startup, the following services will be available:

### Core APIs
- **Backend API**: http://localhost:8001
  - API Documentation: http://localhost:8001/docs
  - ReDoc: http://localhost:8001/redoc
- **Dash API Client**: http://localhost:8002
  - API Documentation: http://localhost:8002/docs

### Infrastructure Services
- **Temporal UI**: http://localhost:8088 (workflow management)
- **Qdrant UI**: http://localhost:6333/dashboard (vector database)
- **PostgreSQL**: localhost:5432 (main database)
- **Redis**: localhost:6379 (caching)
- **Text2Vec Model**: http://localhost:9878 (embeddings)

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐
│  Dash API       │    │  Airweave       │
│  Client         │────│  Backend API    │
│  :8002          │    │  :8001          │
└─────────────────┘    └─────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼──────┐    ┌─────────▼──────┐    ┌─────────▼──────┐
│  PostgreSQL  │    │     Redis      │    │    Qdrant     │
│    :5432     │    │     :6379      │    │    :6333      │
└──────────────┘    └────────────────┘    └────────────────┘
                              │
                    ┌─────────▼──────┐
                    │   Temporal     │
                    │   :7233/8088   │
                    └────────────────┘
```

## 🛠️ Management Commands

### View Logs
```bash
# View all services
docker compose -f docker/docker-compose.yml logs

# View specific service
docker logs airweave-backend
docker logs airweave-dash-api-client
```

### Restart Services
```bash
# Restart all services
docker compose -f docker/docker-compose.yml restart

# Restart specific service
docker compose -f docker/docker-compose.yml restart dash-api-client
```

### Stop Services
```bash
# Stop all services
docker compose -f docker/docker-compose.yml down

# Stop and remove volumes (clean slate)
docker compose -f docker/docker-compose.yml down -v
```

### Rebuild Services
```bash
# Rebuild and restart specific service
docker compose -f docker/docker-compose.yml up -d --build dash-api-client

# Rebuild all services
docker compose -f docker/docker-compose.yml up -d --build
```

## 🔧 Configuration

### Environment Variables

The system uses environment variables from the `.env` file. Key configurations:

```bash
# Core API settings
AIRWEAVE_API_URL=http://backend:8001  # Internal container networking

# Dash API Client user settings
DASH_USER_ID=dash_team
DASH_USER_EMAIL=founders@usedash.ai
DASH_USER_NAME=Dash Team

# Optional: Composio integration for Gmail
COMPOSIO_API_KEY=your-composio-api-key
```

### Dash API Client Configuration

The Dash API Client is pre-configured to:
- Connect to the backend API at `http://backend:8001` (internal Docker network)
- Use a default user for API calls
- Provide REST endpoints for all Airweave functionality

## 📱 Usage Examples

### Using the Dash API Client

```bash
# Check health
curl http://localhost:8002/health

# List collections (using default user)
curl http://localhost:8002/collections

# Create a new collection
curl -X POST http://localhost:8002/collections \
  -H "Content-Type: application/json" \
  -d '{"name": "My Collection", "description": "Test collection"}'
```

### Using the Backend API Directly

```bash
# Check health
curl http://localhost:8001/health

# Access API documentation
open http://localhost:8001/docs
```

## 🐳 Container Overview

| Container Name | Purpose | Port | Health Check |
|---|---|---|---|
| `airweave-backend` | Main API server | 8001 | `/health` |
| `airweave-dash-api-client` | Dash client API | 8002 | `/health` |
| `airweave-db` | PostgreSQL database | 5432 | `pg_isready` |
| `airweave-redis` | Redis cache | 6379 | `redis-cli ping` |
| `airweave-qdrant` | Vector database | 6333 | `/healthz` |
| `airweave-temporal` | Workflow engine | 7233 | `tctl workflow list` |
| `airweave-temporal-ui` | Temporal dashboard | 8088 | Web UI |
| `airweave-temporal-worker` | Background worker | - | - |
| `airweave-embeddings` | Text2Vec model | 9878 | `/health` |

## 🎯 Next Steps

1. **Access the APIs**: Visit http://localhost:8001/docs and http://localhost:8002/docs
2. **Create Collections**: Use either API to create data collections
3. **Set up Connections**: Configure data source connections
4. **Start Syncing**: Begin syncing data from your sources
5. **Search & Retrieve**: Use the search endpoints to query your data

## 🔍 Troubleshooting

### Service Won't Start
```bash
# Check service logs
docker logs airweave-dash-api-client

# Check if port is already in use
lsof -i :8002
```

### API Connection Issues
```bash
# Verify backend is healthy
curl http://localhost:8001/health

# Check container networking
docker exec airweave-dash-api-client curl http://backend:8001/health
```

### Complete Reset
```bash
# Stop everything and start fresh
docker compose -f docker/docker-compose.yml down -v
./start-all.sh
```

## 📚 Additional Resources

- [Airweave Documentation](https://docs.airweave.ai)
- [Temporal Documentation](https://docs.temporal.io)
- [Qdrant Documentation](https://qdrant.tech/documentation)

Happy syncing! 🎉 