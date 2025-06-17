#!/bin/bash

set -x  # Enable debug mode to see what's happening

# Check if .env exists, if not create it from example
if [ ! -f .env ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo ".env file created"
fi

# Generate new encryption key regardless of existing value
echo "Generating new encryption key..."
NEW_KEY=$(openssl rand -base64 32)
echo "Generated key: $NEW_KEY"

# Remove any existing ENCRYPTION_KEY line and create clean .env
grep -v "^ENCRYPTION_KEY=" .env > .env.tmp
mv .env.tmp .env

# Add the new encryption key at the end of the file
echo "ENCRYPTION_KEY=\"$NEW_KEY\"" >> .env

# Add SKIP_AZURE_STORAGE for faster local startup
if ! grep -q "^SKIP_AZURE_STORAGE=" .env; then
    echo "SKIP_AZURE_STORAGE=true" >> .env
    echo "Added SKIP_AZURE_STORAGE=true for faster startup"
fi

echo "Updated .env file. Current ENCRYPTION_KEY value:"
grep "^ENCRYPTION_KEY=" .env

# Ask for OpenAI API key
echo ""
echo "OpenAI API key is required for files and natural language search functionality."
read -p "Would you like to add your OPENAI_API_KEY now? You can also do this later by editing the .env file manually. (y/n): " ADD_OPENAI_KEY

if [ "$ADD_OPENAI_KEY" = "y" ] || [ "$ADD_OPENAI_KEY" = "Y" ]; then
    read -p "Enter your OpenAI API key: " OPENAI_KEY

    # Remove any existing OPENAI_API_KEY line
    grep -v "^OPENAI_API_KEY=" .env > .env.tmp
    mv .env.tmp .env

    # Add the new OpenAI API key
    echo "OPENAI_API_KEY=\"$OPENAI_KEY\"" >> .env
    echo "OpenAI API key added to .env file."
else
    echo "You can add your OPENAI_API_KEY later by editing the .env file manually."
    echo "Add the following line to your .env file:"
    echo "OPENAI_API_KEY=\"your-api-key-here\""
fi

# Ask for Mistral API key
echo ""
echo "Mistral API key is required for certain AI functionality."
read -p "Would you like to add your MISTRAL_API_KEY now? You can also do this later by editing the .env file manually. (y/n): " ADD_MISTRAL_KEY

if [ "$ADD_MISTRAL_KEY" = "y" ] || [ "$ADD_MISTRAL_KEY" = "Y" ]; then
    read -p "Enter your Mistral API key: " MISTRAL_KEY

    # Remove any existing MISTRAL_API_KEY line
    grep -v "^MISTRAL_API_KEY=" .env > .env.tmp
    mv .env.tmp .env

    # Add the new Mistral API key
    echo "MISTRAL_API_KEY=\"$MISTRAL_KEY\"" >> .env
    echo "Mistral API key added to .env file."
else
    echo "You can add your MISTRAL_API_KEY later by editing the .env file manually."
    echo "Add the following line to your .env file:"
    echo "MISTRAL_API_KEY=\"your-api-key-here\""
fi

# Check if "docker compose" is available (Docker Compose v2)
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
# Else, fall back to "docker-compose" (Docker Compose v1)
elif docker-compose --version >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
elif podman-compose --version > /dev/null 2>&1; then
  COMPOSE_CMD="podman-compose"
else
  echo "Neither 'docker compose', 'docker-compose', nor 'podman-compose' found. Please install Docker Compose."
  exit 1
fi

# Add this block: Check if Docker daemon is running
if docker info > /dev/null 2>&1; then
    CONTAINER_CMD="docker"
elif podman info > /dev/null 2>&1; then
    CONTAINER_CMD="podman"
else
    echo "Error: Docker daemon is not running. Please start Docker and try again."
    exit 1
fi

echo "Using commands: ${CONTAINER_CMD} and ${COMPOSE_CMD}"

# Check for existing airweave containers
EXISTING_CONTAINERS=$(${CONTAINER_CMD} ps -a --filter "name=airweave" --format "{{.Names}}" | tr '\n' ' ')

if [ -n "$EXISTING_CONTAINERS" ]; then
  echo "Found existing airweave containers: $EXISTING_CONTAINERS"
  read -p "Would you like to remove them before starting? (y/n): " REMOVE_CONTAINERS

  if [ "$REMOVE_CONTAINERS" = "y" ] || [ "$REMOVE_CONTAINERS" = "Y" ]; then
    echo "Removing existing containers..."
    ${CONTAINER_CMD} rm -f $EXISTING_CONTAINERS

    # Also remove the database volume
    echo "Removing database volume..."
    ${CONTAINER_CMD} volume rm airweave_postgres_data

    echo "Containers and volumes removed."
  else
    echo "Warning: Starting with existing containers may cause conflicts."
  fi
fi

# Now run the appropriate Docker Compose command with the new path
$COMPOSE_CMD -f docker/docker-compose.yml up -d

# Wait a moment for services to initialize
echo ""
echo "Waiting for services to initialize..."
sleep 10

# Check if backend is healthy (with retries)
echo "Checking backend health..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  if ${CONTAINER_CMD} exec airweave-backend curl -f http://localhost:8001/health >/dev/null 2>&1; then
    echo "✅ Backend is healthy!"
    break
  else
    echo "⏳ Backend is still starting... (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)"
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 5
  fi
done

# Check if frontend needs to be started manually
FRONTEND_STATUS=$(${CONTAINER_CMD} inspect airweave-frontend --format='{{.State.Status}}' 2>/dev/null)
if [ "$FRONTEND_STATUS" = "created" ] || [ "$FRONTEND_STATUS" = "exited" ]; then
  echo "Starting frontend container..."
  ${CONTAINER_CMD} start airweave-frontend
  sleep 5
fi

# Final status check
echo ""
echo "🚀 Airweave Status:"
echo "=================="

# Check each service
if ${CONTAINER_CMD} exec airweave-backend curl -f http://localhost:8001/health >/dev/null 2>&1; then
  echo "✅ Backend API:    http://localhost:8001"
else
  echo "❌ Backend API:    Not responding (check logs with: docker logs airweave-backend)"
fi

if curl -f http://localhost:8080 >/dev/null 2>&1; then
  echo "✅ Frontend UI:    http://localhost:8080"
else
  echo "❌ Frontend UI:    Not responding (check logs with: docker logs airweave-frontend)"
fi

echo ""
echo "Other services:"
echo "📊 Temporal UI:    http://localhost:8088"
echo "🗄️  PostgreSQL:    localhost:5432"
echo "🔍 Qdrant:        http://localhost:6333"
echo ""
echo "To view logs: docker logs <container-name>"
echo "To stop all services: docker compose -f docker/docker-compose.yml down"
echo ""
echo "Services started!"
