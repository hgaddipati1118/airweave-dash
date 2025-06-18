#!/bin/bash

# Airweave AWS Deployment Script
# This script deploys the complete Airweave system to AWS using CloudFormation

set -e  # Exit on any error

# Configuration
ENVIRONMENT=${1:-prod}
REGION=${2:-us-east-1}
STACK_NAME="${ENVIRONMENT}-airweave-stack"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Airweave AWS Deployment${NC}"
echo "Environment: ${ENVIRONMENT}"
echo "Region: ${REGION}"
echo "Stack Name: ${STACK_NAME}"
echo "========================================"

# Check prerequisites
echo -e "${BLUE}📋 Checking prerequisites...${NC}"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found. Please install AWS CLI.${NC}"
    exit 1
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker.${NC}"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS credentials not configured. Please run 'aws configure'.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "AWS Account ID: ${AWS_ACCOUNT_ID}"

# Get default VPC ID
DEFAULT_VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query 'Vpcs[0].VpcId' --output text)
if [ "$DEFAULT_VPC_ID" = "None" ] || [ -z "$DEFAULT_VPC_ID" ]; then
    echo -e "${RED}❌ No default VPC found. Please create a default VPC first.${NC}"
    exit 1
fi
echo "Default VPC ID: ${DEFAULT_VPC_ID}"

# Get default subnets in different AZs for ALB
echo "Getting default subnets for ALB..."
DEFAULT_SUBNETS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=${DEFAULT_VPC_ID}" "Name=default-for-az,Values=true" \
    --query 'Subnets[*].SubnetId' \
    --output text)

if [ -z "$DEFAULT_SUBNETS" ]; then
    echo -e "${RED}❌ No default subnets found in default VPC.${NC}"
    exit 1
fi

# Convert to comma-separated list for CloudFormation
DEFAULT_SUBNET_LIST=$(echo $DEFAULT_SUBNETS | tr ' ' ',')
echo "Default Subnets: ${DEFAULT_SUBNET_LIST}"

# Verify we have at least 2 subnets for ALB
SUBNET_COUNT=$(echo $DEFAULT_SUBNETS | wc -w)
if [ $SUBNET_COUNT -lt 2 ]; then
    echo -e "${RED}❌ Need at least 2 subnets in different AZs for ALB. Found: $SUBNET_COUNT${NC}"
    exit 1
fi
echo "✅ Found $SUBNET_COUNT subnets for ALB"

# Collect required parameters
echo -e "${BLUE}📝 Collecting deployment parameters...${NC}"

read -s -p "Enter PostgreSQL database password (12-41 characters): " DB_PASSWORD
echo
if [ ${#DB_PASSWORD} -lt 12 ] || [ ${#DB_PASSWORD} -gt 41 ]; then
    echo -e "${RED}❌ Database password must be 12-41 characters${NC}"
    exit 1
fi

read -s -p "Enter encryption key (base64, 32+ characters): " ENCRYPTION_KEY
echo
if [ ${#ENCRYPTION_KEY} -lt 32 ]; then
    echo -e "${RED}❌ Encryption key must be at least 32 characters${NC}"
    exit 1
fi

read -s -p "Enter OpenAI API key (optional, press Enter to skip): " OPENAI_API_KEY
echo

read -s -p "Enter Mistral API key (optional, press Enter to skip): " MISTRAL_API_KEY
echo

read -s -p "Enter Composio API key (optional, press Enter to skip): " COMPOSIO_API_KEY
echo

echo -e "${GREEN}✅ Parameters collected${NC}"

# Create ECR repositories if they don't exist
echo -e "${BLUE}🐳 Setting up ECR repositories...${NC}"

create_ecr_repo() {
    local repo_name=$1
    echo "Creating ECR repository: ${repo_name}"
    
    if ! aws ecr describe-repositories --repository-names "${repo_name}" --region "${REGION}" &> /dev/null; then
        aws ecr create-repository \
            --repository-name "${repo_name}" \
            --region "${REGION}" \
            --image-scanning-configuration scanOnPush=true \
            --encryption-configuration encryptionType=AES256
        echo -e "${GREEN}✅ Created ECR repository: ${repo_name}${NC}"
    else
        echo -e "${YELLOW}⚠️  ECR repository already exists: ${repo_name}${NC}"
    fi
}

create_ecr_repo "${ENVIRONMENT}-airweave-backend"
create_ecr_repo "${ENVIRONMENT}-airweave-dash-client"

# Login to ECR
echo -e "${BLUE}🔐 Logging into ECR...${NC}"
aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# Build and push backend image
echo -e "${BLUE}🏗️  Building and pushing backend image...${NC}"
cd backend
docker build -t "${ENVIRONMENT}-airweave-backend" .
docker tag "${ENVIRONMENT}-airweave-backend:latest" "${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ENVIRONMENT}-airweave-backend:latest"
docker push "${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ENVIRONMENT}-airweave-backend:latest"
cd ..

# Build and push dash-api-client image
echo -e "${BLUE}🏗️  Building and pushing dash-api-client image...${NC}"
cd dash-api-client
docker build -t "${ENVIRONMENT}-airweave-dash-client" .
docker tag "${ENVIRONMENT}-airweave-dash-client:latest" "${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ENVIRONMENT}-airweave-dash-client:latest"
docker push "${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ENVIRONMENT}-airweave-dash-client:latest"
cd ..

echo -e "${GREEN}✅ Docker images built and pushed${NC}"

# Deploy CloudFormation stack
echo -e "${BLUE}☁️  Deploying CloudFormation stack...${NC}"

aws cloudformation deploy \
    --template-file aws/cloudformation/airweave-infrastructure.yaml \
    --stack-name "${STACK_NAME}" \
    --parameter-overrides \
        Environment="${ENVIRONMENT}" \
        DefaultVPC="${DEFAULT_VPC_ID}" \
        DefaultSubnets="${DEFAULT_SUBNET_LIST}" \
        DatabasePassword="${DB_PASSWORD}" \
        EncryptionKey="${ENCRYPTION_KEY}" \
        OpenAIApiKey="${OPENAI_API_KEY}" \
        MistralApiKey="${MISTRAL_API_KEY}" \
        ComposioApiKey="${COMPOSIO_API_KEY}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "${REGION}" \
    --no-fail-on-empty-changeset

echo -e "${GREEN}✅ CloudFormation stack deployed${NC}"

# Get stack outputs
echo -e "${BLUE}📊 Getting deployment information...${NC}"

ALB_URL=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerURL`].OutputValue' \
    --output text)

BACKEND_URL=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --query 'Stacks[0].Outputs[?OutputKey==`BackendAPIURL`].OutputValue' \
    --output text)

DASH_CLIENT_URL=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --query 'Stacks[0].Outputs[?OutputKey==`DashClientAPIURL`].OutputValue' \
    --output text)

echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo ""
echo "========================================"
echo -e "${BLUE}📋 Deployment Information${NC}"
echo "========================================"
echo "Environment: ${ENVIRONMENT}"
echo "Region: ${REGION}"
echo "Stack Name: ${STACK_NAME}"
echo ""
echo -e "${BLUE}🌐 Service URLs:${NC}"
echo "Load Balancer: ${ALB_URL}"
echo "Backend API: ${BACKEND_URL}"
echo "Dash Client API: ${DASH_CLIENT_URL}"
echo ""
echo -e "${BLUE}🔧 Management Commands:${NC}"
echo "View logs: aws logs tail /ecs/${ENVIRONMENT}-airweave-backend --follow --region ${REGION}"
echo "View dash logs: aws logs tail /ecs/${ENVIRONMENT}-airweave-dash-client --follow --region ${REGION}"
echo "Scale backend: aws ecs update-service --cluster ${ENVIRONMENT}-airweave-cluster --service ${ENVIRONMENT}-airweave-backend --desired-count 2 --region ${REGION}"
echo "Delete stack: aws cloudformation delete-stack --stack-name ${STACK_NAME} --region ${REGION}"
echo ""
echo -e "${BLUE}🧪 Health Checks:${NC}"
echo "Backend health: curl ${BACKEND_URL}/health"
echo "Dash client health: curl ${DASH_CLIENT_URL}/health"
echo ""
echo -e "${YELLOW}⏰ Note: Services may take 5-10 minutes to become fully available${NC}"
echo "========================================" 