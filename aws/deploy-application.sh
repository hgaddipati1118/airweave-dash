#!/bin/bash

# Deploy Application Stack (Fast) - Run for every deployment
# This takes only 2-3 minutes since it doesn't create database/cache

set -e

ENVIRONMENT=${1:-prod}
REGION=${2:-us-east-1}

echo "🚀 Deploying Application Stack for $ENVIRONMENT in $REGION"
echo "⚡ This should take only 2-3 minutes!"

# Check required secrets
if [ -z "$ENCRYPTION_KEY" ]; then
    echo "❌ Error: ENCRYPTION_KEY environment variable is required"
    exit 1
fi

# Check if infrastructure stack exists
echo "🔍 Checking infrastructure stack..."
if ! aws cloudformation describe-stacks \
    --stack-name ${ENVIRONMENT}-airweave-infrastructure-stack \
    --region $REGION \
    --query 'Stacks[0].StackStatus' \
    --output text >/dev/null 2>&1; then
    echo "❌ Error: Infrastructure stack not found!"
    echo "   Please run: ./aws/deploy-infrastructure.sh $ENVIRONMENT $REGION first"
    exit 1
fi

# Get AWS Account ID
echo "🔍 Getting AWS Account ID..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "📍 AWS Account ID: $ACCOUNT_ID"

# Create ECR repositories if they don't exist
echo "🏗️  Creating ECR repositories..."
aws ecr create-repository \
  --repository-name ${ENVIRONMENT}-airweave-backend \
  --region $REGION \
  --image-scanning-configuration scanOnPush=true \
  --encryption-configuration encryptionType=AES256 || echo "Backend repository already exists"

aws ecr create-repository \
  --repository-name ${ENVIRONMENT}-airweave-dash-client \
  --region $REGION \
  --image-scanning-configuration scanOnPush=true \
  --encryption-configuration encryptionType=AES256 || echo "Dash client repository already exists"

# Login to ECR
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

# Build and push backend image
echo "🔨 Building and pushing backend image..."
cd backend
docker build -t ${ENVIRONMENT}-airweave-backend .
docker tag ${ENVIRONMENT}-airweave-backend:latest \
  $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/${ENVIRONMENT}-airweave-backend:latest
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/${ENVIRONMENT}-airweave-backend:latest
cd ..

# Build and push dash client image
echo "🔨 Building and pushing dash client image..."
cd dash-api-client
docker build -t ${ENVIRONMENT}-airweave-dash-client .
docker tag ${ENVIRONMENT}-airweave-dash-client:latest \
  $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/${ENVIRONMENT}-airweave-dash-client:latest
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/${ENVIRONMENT}-airweave-dash-client:latest
cd ..

# Deploy application stack
echo "🚀 Deploying application stack..."
aws cloudformation deploy \
  --template-file aws/cloudformation/airweave-application.yaml \
  --stack-name ${ENVIRONMENT}-airweave-application-stack \
  --parameter-overrides \
    Environment=$ENVIRONMENT \
    EncryptionKey="$ENCRYPTION_KEY" \
    OpenAIApiKey="${OPENAI_API_KEY:-}" \
    MistralApiKey="${MISTRAL_API_KEY:-}" \
    ComposioApiKey="${COMPOSIO_API_KEY:-}" \
  --capabilities CAPABILITY_IAM \
  --region $REGION \
  --no-fail-on-empty-changeset

echo "✅ Application deployment completed!"

# Get deployment outputs
echo "🌐 Getting service URLs..."
ALB_URL=$(aws cloudformation describe-stacks \
  --stack-name ${ENVIRONMENT}-airweave-application-stack \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerURL`].OutputValue' \
  --output text)

BACKEND_URL=$(aws cloudformation describe-stacks \
  --stack-name ${ENVIRONMENT}-airweave-application-stack \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`BackendAPIURL`].OutputValue' \
  --output text)

DASH_CLIENT_URL=$(aws cloudformation describe-stacks \
  --stack-name ${ENVIRONMENT}-airweave-application-stack \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`DashClientAPIURL`].OutputValue' \
  --output text)

echo ""
echo "🎉 Deployment completed successfully!"
echo "========================================"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "========================================"
echo "🌐 Service URLs:"
echo "Load Balancer: $ALB_URL"
echo "Backend API: $BACKEND_URL"
echo "Dash Client API: $DASH_CLIENT_URL"
echo "========================================"
echo "🧪 Health Check URLs:"
echo "Backend health: $BACKEND_URL/health"
echo "Dash client health: $DASH_CLIENT_URL/health"
echo "========================================"

# Wait a moment for services to start
echo "⏰ Waiting 30 seconds for services to initialize..."
sleep 30

# Test backend health (allow failure since services might still be starting)
echo "Testing backend health..."
curl -f "$BACKEND_URL/health" || echo "Backend still starting..."

# Test dash client health (allow failure since services might still be starting)
echo "Testing dash client health..."
curl -f "$DASH_CLIENT_URL/health" || echo "Dash client still starting..."

echo ""
echo "🎯 Next deployments will take only 2-3 minutes!"
echo "   Just run: ./aws/deploy-application.sh $ENVIRONMENT $REGION" 