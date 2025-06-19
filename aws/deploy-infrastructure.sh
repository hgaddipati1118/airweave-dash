#!/bin/bash

# Deploy Infrastructure Stack (Database & Cache) - Run Once
# This takes ~15-20 minutes but only needs to be done once per environment

set -e

ENVIRONMENT=${1:-prod}
REGION=${2:-us-east-1}

echo "🏗️  Deploying Infrastructure Stack for $ENVIRONMENT in $REGION"
echo "⚠️  This will take 15-20 minutes due to RDS/ElastiCache provisioning"
echo "⚠️  This stack only needs to be deployed once per environment"

# Check required secrets
if [ -z "$DB_PASSWORD" ]; then
    echo "❌ Error: DB_PASSWORD environment variable is required"
    exit 1
fi

# Get default VPC and subnets
echo "🔍 Finding default VPC and subnets..."
DEFAULT_VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query 'Vpcs[0].VpcId' --output text --region $REGION)
DEFAULT_SUBNETS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$DEFAULT_VPC_ID" "Name=default-for-az,Values=true" \
  --query 'Subnets[*].SubnetId' \
  --output text --region $REGION | tr '\t' ',')

echo "📍 Using VPC: $DEFAULT_VPC_ID"
echo "📍 Using Subnets: $DEFAULT_SUBNETS"

# Deploy infrastructure stack
echo "🚀 Deploying infrastructure stack..."
aws cloudformation deploy \
  --template-file aws/cloudformation/airweave-infrastructure.yaml \
  --stack-name ${ENVIRONMENT}-airweave-infrastructure-stack \
  --parameter-overrides \
    Environment=$ENVIRONMENT \
    DatabasePassword="$DB_PASSWORD" \
    VpcId="$DEFAULT_VPC_ID" \
    SubnetIds="$DEFAULT_SUBNETS" \
  --capabilities CAPABILITY_IAM \
  --region $REGION \
  --no-fail-on-empty-changeset

echo "✅ Infrastructure deployment completed!"
echo "📋 Stack outputs:"
aws cloudformation describe-stacks \
  --stack-name ${ENVIRONMENT}-airweave-infrastructure-stack \
  --region $REGION \
  --query 'Stacks[0].Outputs' \
  --output table

echo ""
echo "🎯 Next steps:"
echo "   1. Wait for database and cache to be fully ready (~5 more minutes)"
echo "   2. Run: ./aws/deploy-application.sh $ENVIRONMENT $REGION"
echo "   3. Application deployments will now take only 2-3 minutes!" 