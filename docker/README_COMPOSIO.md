# Composio Integration in Docker

This guide explains how to set up and use Composio integration with Airweave when running in Docker containers.

## 🔧 **Quick Setup**

### 1. **Automatic Setup (Recommended)**
When you run `./start.sh`, you'll be prompted to configure Composio:

```bash
./start.sh
```

The script will ask:
```
Composio integration enables advanced Gmail token management.
This is optional but recommended if you plan to use Gmail with automatic token refresh.
Would you like to configure Composio integration now? (y/n):
```

Choose `y` and provide:
- **Composio API Key**: Get from [https://app.composio.dev](https://app.composio.dev)

Note: Entity IDs are provided per Gmail connection, not globally.

### 2. **Manual Setup**
If you skipped the automatic setup, add these to your `.env` file:

```bash
# Add to .env file in project root
COMPOSIO_API_KEY="your_composio_api_key_here"
# Note: Entity IDs are provided when creating individual Gmail connections
```

Then restart the containers:
```bash
docker compose -f docker/docker-compose.yml down
docker compose -f docker/docker-compose.yml up -d
```

## 📋 **Prerequisites**

### 1. **Composio Account Setup**
1. Create account at [https://app.composio.dev](https://app.composio.dev)
2. Get your API key from the dashboard
3. Create or note your entity ID

### 2. **Gmail Connection in Composio**
1. In Composio dashboard, connect your Gmail account
2. Ensure the connection is active and has proper permissions
3. Note the entity ID associated with the Gmail connection

## 🚀 **Using Gmail with Composio**

### **Create Gmail Connection via API**
```python
import asyncio
from dash_api_client.airweave_client import AirweaveClient, ConnectionConfig, SourceType, AirweaveConfig

async def create_gmail_connection():
    config = AirweaveConfig(base_url="http://localhost:8001")
    
    async with AirweaveClient(config) as client:
        connection_config = ConnectionConfig(
            name="Gmail with Composio",
            source_type=SourceType.GMAIL,
            collection_id="my-gmail-collection",
            auth_fields={
                "access_token": "your_initial_gmail_token",
                "composio_api_key": "your_composio_api_key",  # Or use shared from env
                "entity_id": "your_unique_entity_id"  # User-specific entity ID
            }
        )
        
        connection = await client.create_connection(connection_config)
        print(f"✅ Created connection: {connection.id}")

asyncio.run(create_gmail_connection())
```

### **Benefits with Composio**
- ✅ **Automatic token refresh** when Gmail tokens expire
- ✅ **No manual OAuth management** required
- ✅ **Centralized token management** through Composio
- ✅ **Real-time token updates** from Composio

## 🔍 **Verify Setup**

### 1. **Check Environment Variables**
```bash
docker exec airweave-backend env | grep COMPOSIO
```

Should show:
```
COMPOSIO_API_KEY=your_api_key
# Note: Entity IDs are not set globally - they come from individual connections
```

### 2. **Test Container Access**
```bash
# Check if Composio package is installed
docker exec airweave-backend python -c "import composio; print('✅ Composio available')"

# Check logs for Composio initialization
docker logs airweave-backend | grep -i composio
```

### 3. **Monitor Gmail Sync with Token Refresh**
```bash
# Watch logs during Gmail sync
docker logs -f airweave-backend

# Look for messages like:
# "401 Unauthorized - attempting to refresh token from Composio"
# "Successfully refreshed access token from Composio"
```

## 🛠 **Troubleshooting**

### **Common Issues**

#### 1. **Composio Package Not Found**
```
WARNING: Composio not available. Install with: pip install composio-core
```

**Solution:** Rebuild the backend container:
```bash
docker compose -f docker/docker-compose.yml build backend
docker compose -f docker/docker-compose.yml up -d
```

#### 2. **Environment Variables Not Set**
```
ERROR: Composio client or entity_id not available for token refresh
```

**Solution:** Check your `.env` file:
```bash
# Verify .env file contains Composio config
grep COMPOSIO .env

# If missing, add it:
echo 'COMPOSIO_API_KEY="your_key"' >> .env
# Note: Entity IDs are provided per connection, not globally

# Restart containers
docker compose -f docker/docker-compose.yml restart
```

#### 3. **Token Refresh Failures**
```
ERROR: Failed to refresh token from Composio
```

**Solutions:**
- Verify Composio API key is correct
- Check entity has access to Gmail connection
- Ensure Gmail connection is active in Composio dashboard

#### 4. **Authentication Errors**
```
ERROR: No Gmail connection found in Composio for entity
```

**Solutions:**
- Verify entity ID is correct
- Check Gmail is connected in Composio for this entity
- Ensure proper scopes are configured in Composio

### **Debug Commands**

```bash
# Check container environment
docker exec airweave-backend printenv | grep -E "(COMPOSIO|GMAIL)"

# Test Composio connection (using a specific entity ID)
docker exec airweave-backend python -c "
from composio import Composio
import os
try:
    client = Composio(api_key=os.getenv('COMPOSIO_API_KEY'))
    # Note: Replace 'your_entity_id' with an actual entity ID from your connections
    entity = client.get_entity(id='your_entity_id')
    connections = entity.get_connections()
    print(f'✅ Found {len(connections)} connections')
    for conn in connections:
        print(f'  - {conn.appName}')
except Exception as e:
    print(f'❌ Error: {e}')
"

# View full backend logs
docker logs airweave-backend --tail 100
```

## 📚 **Configuration Reference**

### **Environment Variables**
| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `COMPOSIO_API_KEY` | Your Composio API key | Yes* | `comp_abc123...` |

*Required only if using Gmail with Composio integration

**Note:** Entity IDs are provided per Gmail connection, not as global environment variables.

### **Docker Compose Override**
If you need to override the default configuration, create a `docker-compose.override.yml`:

```yaml
# docker-compose.override.yml
services:
  backend:
    environment:
      - COMPOSIO_API_KEY=your_override_key
      - COMPOSIO_ENTITY_ID=your_override_entity
  
  temporal-worker:
    environment:
      - COMPOSIO_API_KEY=your_override_key
      - COMPOSIO_ENTITY_ID=your_override_entity
```

## 🔄 **Migration from Legacy Gmail**

If you have existing Gmail connections without Composio:

### 1. **Update Existing Connection**
```python
# Update connection to include Composio credentials
auth_fields = {
    "access_token": "existing_token",
    "composio_api_key": "your_composio_key",  # Add this
    "entity_id": "your_entity_id"              # Add this
}
```

### 2. **Test Token Refresh**
Trigger a sync and monitor logs for automatic token refresh behavior.

## 🚀 **Next Steps**

1. **Set up Composio** following this guide
2. **Create Gmail connections** with Composio credentials
3. **Monitor automatic token refresh** in action
4. **Scale to multiple users** with different entity IDs

---

For more information about Composio integration, see the main [GMAIL_COMPOSIO_INTEGRATION.md](../GMAIL_COMPOSIO_INTEGRATION.md) documentation. 