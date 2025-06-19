#!/bin/bash

# Deploy Application Stack (Fast) - Run for every deployment
# This takes only 2-3 minutes since it doesn't create database/cache
# MODIFIED: This script skips docker build and push

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

# Deploy application stack
echo "🚀 Deploying application stack with existing ECR images..."
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

echo "✅ Application deployment initiated!"

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