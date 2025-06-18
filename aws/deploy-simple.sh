#!/bin/bash

# Airweave AWS Deployment Script - Simple Version (Uses Default VPC)
# This script deploys the complete Airweave system to AWS using the default VPC

set -e  # Exit on any error

# Configuration
ENVIRONMENT=${1:-prod}
REGION=${2:-us-east-1}
STACK_NAME="${ENVIRONMENT}-airweave-simple-stack"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Airweave AWS Deployment (Simple Version)${NC}"
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
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo -e "${RED}❌ AWS credentials not configured. Please run 'aws configure'.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "AWS Account ID: ${AWS_ACCOUNT_ID}"

# First, let's clean up the failed stack
echo -e "${BLUE}🧹 Cleaning up failed stack...${NC}"
aws cloudformation delete-stack --stack-name prod-airweave-stack --region "${REGION}" || true

# Wait for stack deletion
echo "Waiting for stack deletion to complete..."
aws cloudformation wait stack-delete-complete --stack-name prod-airweave-stack --region "${REGION}" || true

# Collect required parameters
echo -e "${BLUE}📝 Collecting deployment parameters...${NC}"

read -s -p "Enter PostgreSQL database password (12-41 characters): " DB_PASSWORD
echo
if [ ${#DB_PASSWORD} -lt 12 ] || [ ${#DB_PASSWORD} -gt 41 ]; then
    echo -e "${RED}❌ Database password must be 12-41 characters${NC}"
    exit 1
fi

read -s -p "Enter encryption key (use: iZTSModxRIfO2Ihf01fTcmMl1e+10oBqi7ed9c/dT+o=): " ENCRYPTION_KEY
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

# Create simple CloudFormation template
cat > /tmp/airweave-simple.yaml << 'EOF'
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Airweave Complete System - Using Default VPC'

Parameters:
  Environment:
    Type: String
    Default: 'prod'
  DatabasePassword:
    Type: String
    NoEcho: true
  EncryptionKey:
    Type: String
    NoEcho: true
  OpenAIApiKey:
    Type: String
    NoEcho: true
    Default: ''
  MistralApiKey:
    Type: String
    NoEcho: true
    Default: ''
  ComposioApiKey:
    Type: String
    NoEcho: true
    Default: ''

Resources:
  ECSCluster:
    Type: AWS::ECS::Cluster
    Properties:
      ClusterName: !Sub '${Environment}-airweave-simple-cluster'

  ECSTaskExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: ecs-tasks.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

  BackendLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub '/ecs/${Environment}-airweave-backend-simple'
      RetentionInDays: 7

  DashClientLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub '/ecs/${Environment}-airweave-dash-client-simple'
      RetentionInDays: 7

  BackendTaskDefinition:
    Type: AWS::ECS::TaskDefinition
    Properties:
      Family: !Sub '${Environment}-airweave-backend-simple'
      NetworkMode: awsvpc
      RequiresCompatibilities:
        - FARGATE
      Cpu: '512'
      Memory: '1024'
      ExecutionRoleArn: !Ref ECSTaskExecutionRole
      ContainerDefinitions:
        - Name: backend
          Image: !Sub '${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/${Environment}-airweave-backend:latest'
          PortMappings:
            - ContainerPort: 8001
              Protocol: tcp
          Environment:
            - Name: ENVIRONMENT
              Value: !Ref Environment
            - Name: ENCRYPTION_KEY
              Value: !Ref EncryptionKey
            - Name: OPENAI_API_KEY
              Value: !Ref OpenAIApiKey
            - Name: MISTRAL_API_KEY
              Value: !Ref MistralApiKey
            - Name: COMPOSIO_API_KEY
              Value: !Ref ComposioApiKey
            - Name: SKIP_AZURE_STORAGE
              Value: 'true'
            - Name: LOCAL_DEVELOPMENT
              Value: 'false'
          LogConfiguration:
            LogDriver: awslogs
            Options:
              awslogs-group: !Ref BackendLogGroup
              awslogs-region: !Ref AWS::Region
              awslogs-stream-prefix: ecs

  DashClientTaskDefinition:
    Type: AWS::ECS::TaskDefinition
    Properties:
      Family: !Sub '${Environment}-airweave-dash-client-simple'
      NetworkMode: awsvpc
      RequiresCompatibilities:
        - FARGATE
      Cpu: '256'
      Memory: '512'
      ExecutionRoleArn: !Ref ECSTaskExecutionRole
      ContainerDefinitions:
        - Name: dash-client
          Image: !Sub '${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/${Environment}-airweave-dash-client:latest'
          PortMappings:
            - ContainerPort: 8002
              Protocol: tcp
          Environment:
            - Name: AIRWEAVE_API_URL
              Value: 'http://localhost:8001'
            - Name: AIRWEAVE_DEFAULT_USER_ID
              Value: 'dash_team'
          LogConfiguration:
            LogDriver: awslogs
            Options:
              awslogs-group: !Ref DashClientLogGroup
              awslogs-region: !Ref AWS::Region
              awslogs-stream-prefix: ecs

Outputs:
  ECSClusterName:
    Description: 'ECS Cluster Name'
    Value: !Ref ECSCluster
EOF

# Deploy CloudFormation stack
echo -e "${BLUE}☁️  Deploying CloudFormation stack...${NC}"

aws cloudformation deploy \
    --template-file /tmp/airweave-simple.yaml \
    --stack-name "${STACK_NAME}" \
    --parameter-overrides \
        Environment="${ENVIRONMENT}" \
        DatabasePassword="${DB_PASSWORD}" \
        EncryptionKey="${ENCRYPTION_KEY}" \
        OpenAIApiKey="${OPENAI_API_KEY}" \
        MistralApiKey="${MISTRAL_API_KEY}" \
        ComposioApiKey="${COMPOSIO_API_KEY}" \
    --capabilities CAPABILITY_IAM \
    --region "${REGION}" \
    --no-fail-on-empty-changeset

echo -e "${GREEN}✅ CloudFormation stack deployed${NC}"

# Get stack outputs
echo -e "${BLUE}📊 Getting deployment information...${NC}"

CLUSTER_NAME=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${REGION}" \
    --query 'Stacks[0].Outputs[?OutputKey==`ECSClusterName`].OutputValue' \
    --output text)

echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo ""
echo "========================================"
echo -e "${BLUE}📋 Deployment Information${NC}"
echo "========================================"
echo "Environment: ${ENVIRONMENT}"
echo "Region: ${REGION}"
echo "Stack Name: ${STACK_NAME}"
echo "ECS Cluster: ${CLUSTER_NAME}"
echo ""
echo -e "${BLUE}🔧 Next Steps:${NC}"
echo "1. This is a simplified deployment without load balancer or database"
echo "2. Your containers are running but not accessible from internet"
echo "3. To test locally, you can run tasks manually:"
echo ""
echo "aws ecs run-task \\"
echo "    --cluster ${CLUSTER_NAME} \\"
echo "    --task-definition ${ENVIRONMENT}-airweave-backend-simple \\"
echo "    --launch-type FARGATE \\"
echo "    --network-configuration 'awsvpcConfiguration={subnets=[subnet-xxx],assignPublicIp=ENABLED}' \\"
echo "    --region ${REGION}"
echo ""
echo -e "${BLUE}🔧 Management Commands:${NC}"
echo "View backend logs: aws logs tail /ecs/${ENVIRONMENT}-airweave-backend-simple --follow --region ${REGION}"
echo "View dash logs: aws logs tail /ecs/${ENVIRONMENT}-airweave-dash-client-simple --follow --region ${REGION}"
echo "Delete stack: aws cloudformation delete-stack --stack-name ${STACK_NAME} --region ${REGION}"
echo "========================================"

# Clean up temp file
rm /tmp/airweave-simple.yaml 