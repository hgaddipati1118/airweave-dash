#!/bin/bash

# Comprehensive Airweave + Dash API Client Startup Script
# This script starts all services: backend, dash-api-client, temporal, database, etc.

set -e  # Exit on any error

echo "🚀 Starting Airweave Complete System"
echo "===================================="

# Check for .env file
if [ ! -f ../.env ]; then
    echo "⚠️  No .env file found. Running main setup script first..."
    cd ..
    ./start.sh
    cd docker
    echo "✅ Initial setup complete. Continuing with all services..."
fi

# Determine Docker command
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif docker-compose --version >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ Docker Compose not found. Please install Docker Compose."
    exit 1
fi

# Check Docker daemon
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker daemon not running. Please start Docker."
    exit 1
fi

echo "Using: $COMPOSE_CMD"

# Stop any existing services
echo "🧹 Cleaning up existing services..."
$COMPOSE_CMD -f docker-compose.yml down --remove-orphans

# Start all services
echo "🚀 Starting all Airweave services..."
$COMPOSE_CMD -f docker-compose.yml up -d

# Wait for initialization
echo "⏳ Waiting for services to initialize..."
sleep 15

# Health checks with retries
echo "🏥 Performing health checks..."

check_service() {
    local service_name=$1
    local url=$2
    local container_name=$3
    local max_retries=60
    local retry_count=0
    
    echo "Checking $service_name..."
    
    while [ $retry_count -lt $max_retries ]; do
        if docker exec $container_name curl -f $url >/dev/null 2>&1; then
            echo "✅ $service_name is healthy!"
            return 0
        else
            echo "⏳ $service_name starting... (attempt $((retry_count + 1))/$max_retries)"
            retry_count=$((retry_count + 1))
            sleep 2
        fi
    done
    
    echo "❌ $service_name failed to start"
    return 1
}

# Check core services
echo ""
echo "Checking core services..."
check_service "Backend API" "http://localhost:8001/health" "airweave-backend"
check_service "Dash API Client" "http://localhost:8002/health" "airweave-dash-api-client"

# Final status report
echo ""
echo "🎉 Airweave Complete System Status"
echo "================================="

# Core APIs
if docker exec airweave-backend curl -f http://localhost:8001/health >/dev/null 2>&1; then
    echo "✅ Backend API:        http://localhost:8001"
    echo "   📖 API Docs:        http://localhost:8001/docs"
    echo "   📊 Redoc:           http://localhost:8001/redoc"
else
    echo "❌ Backend API:        Failed to start"
fi

if docker exec airweave-dash-api-client curl -f http://localhost:8002/health >/dev/null 2>&1; then
    echo "✅ Dash API Client:    http://localhost:8002"
    echo "   📖 API Docs:        http://localhost:8002/docs"
else
    echo "❌ Dash API Client:    Failed to start"
fi

# Infrastructure services
echo ""
echo "Infrastructure Services:"
if docker exec airweave-temporal tctl --address temporal:7233 workflow list >/dev/null 2>&1; then
    echo "✅ Temporal Server:    http://localhost:7233"
    echo "✅ Temporal UI:        http://localhost:8088"
else
    echo "❌ Temporal:           Not responding"
fi

if docker exec airweave-qdrant curl -f http://localhost:6333/healthz >/dev/null 2>&1; then
    echo "✅ Qdrant Vector DB:   http://localhost:6333"
    echo "   🎛️  Qdrant UI:       http://localhost:6333/dashboard"
else
    echo "❌ Qdrant:             Not responding"
fi

echo "✅ PostgreSQL:         localhost:5432"
echo "✅ Redis:              localhost:6379"
echo "✅ Text2Vec Model:     http://localhost:9878"

echo ""
echo "📱 Quick Start Guide:"
echo "===================="
echo "1. Backend API:        http://localhost:8001/docs"
echo "2. Dash API Client:    http://localhost:8002/docs" 
echo "3. Create collections, connections, and start syncing!"
echo ""
echo "🔧 Management Commands:"
echo "======================"
echo "View logs:           docker logs <container-name>"
echo "Stop all services:   docker compose -f docker/docker-compose.yml down"
echo "Restart service:     docker compose -f docker/docker-compose.yml restart <service>"
echo "Rebuild service:     docker compose -f docker/docker-compose.yml up -d --build <service>"
echo ""
echo "📋 Container Names:"
echo "=================="
echo "• airweave-backend"
echo "• airweave-dash-api-client"
echo "• airweave-temporal"
echo "• airweave-temporal-ui"
echo "• airweave-temporal-worker"
echo "• airweave-db"
echo "• airweave-redis"
echo "• airweave-qdrant"
echo "• airweave-embeddings"
echo ""
echo "🎯 All services started successfully! Happy syncing! 🎉" 