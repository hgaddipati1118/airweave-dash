# Airweave AWS Deployment Guide

This guide walks you through deploying the complete Airweave system (Backend API + Dash API Client) to AWS using CloudFormation and ECS Fargate.

## 🏗️ Architecture Overview

The AWS deployment includes:
- **ECS Fargate**: Containerized services (Backend API + Dash Client)
- **Application Load Balancer**: Public internet access and routing
- **RDS PostgreSQL**: Managed database
- **ElastiCache Redis**: Managed caching layer
- **VPC**: Secure networking with public/private subnets
- **ECR**: Docker container registry
- **CloudWatch**: Logging and monitoring

## 📋 Prerequisites

Before deploying, ensure you have:

1. **AWS CLI installed and configured**
   ```bash
   # Install AWS CLI (if not installed)
   curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
   unzip awscliv2.zip
   sudo ./aws/install
   
   # Configure with your credentials
   aws configure
   ```

2. **Docker installed and running**
   ```bash
   # Verify Docker is running
   docker --version
   ```

3. **Required AWS permissions**:
   - ECR (create repositories, push images)
   - ECS (create clusters, services, tasks)
   - CloudFormation (create/update stacks)
   - IAM (create roles and policies)
   - EC2 (VPC, security groups, load balancers)
   - RDS (create database instances)
   - ElastiCache (create Redis clusters)
   - CloudWatch (create log groups)

## 🚀 Quick Deployment

### Option 1: Automated Script (Recommended)

1. **Navigate to project root**:
   ```bash
   cd /path/to/airweave-dash
   ```

2. **Run deployment script**:
   ```bash
   # Deploy to production (default)
   ./aws/deploy.sh

   # Or specify environment and region
   ./aws/deploy.sh prod us-west-2
   ./aws/deploy.sh staging us-east-1
   ```

3. **Provide required parameters when prompted**:
   - PostgreSQL database password (12-41 characters)
   - Encryption key (32+ characters, base64)
   - OpenAI API key (optional)
   - Mistral API key (optional)
   - Composio API key (optional)

### Option 2: Manual Deployment

1. **Create ECR repositories**:
   ```bash
   aws ecr create-repository --repository-name prod-airweave-backend --region us-east-1
   aws ecr create-repository --repository-name prod-airweave-dash-client --region us-east-1
   ```

2. **Login to ECR**:
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
   ```

3. **Build and push images**:
   ```bash
   # Backend
   cd backend
   docker build -t prod-airweave-backend .
   docker tag prod-airweave-backend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/prod-airweave-backend:latest
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/prod-airweave-backend:latest
   cd ..

   # Dash Client
   cd dash-api-client
   docker build -t prod-airweave-dash-client .
   docker tag prod-airweave-dash-client:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/prod-airweave-dash-client:latest
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/prod-airweave-dash-client:latest
   cd ..
   ```

4. **Deploy CloudFormation stack**:
   ```bash
   aws cloudformation deploy \
       --template-file aws/cloudformation/airweave-infrastructure.yaml \
       --stack-name prod-airweave-stack \
       --parameter-overrides \
           Environment=prod \
           DatabasePassword=YourSecurePassword123 \
           EncryptionKey=YourBase64EncryptionKey123456789 \
           OpenAIApiKey=sk-your-openai-key \
           ComposioApiKey=your-composio-key \
       --capabilities CAPABILITY_NAMED_IAM \
       --region us-east-1
   ```

## 🌐 Service URLs

After deployment, your services will be available at:

- **Backend API**: `http://<alb-dns-name>/`
- **Dash Client API**: `http://<alb-dns-name>/dash/`
- **Backend Health**: `http://<alb-dns-name>/health`
- **Dash Client Health**: `http://<alb-dns-name>/dash/health`

## 🔧 Management Commands

### View Logs
```bash
# Backend logs
aws logs tail /ecs/prod-airweave-backend --follow --region us-east-1

# Dash client logs
aws logs tail /ecs/prod-airweave-dash-client --follow --region us-east-1
```

### Scale Services
```bash
# Scale backend to 2 instances
aws ecs update-service \
    --cluster prod-airweave-cluster \
    --service prod-airweave-backend \
    --desired-count 2 \
    --region us-east-1

# Scale dash client to 2 instances
aws ecs update-service \
    --cluster prod-airweave-cluster \
    --service prod-airweave-dash-client \
    --desired-count 2 \
    --region us-east-1
```

### Update Services
```bash
# Rebuild and push new images, then:
aws ecs update-service \
    --cluster prod-airweave-cluster \
    --service prod-airweave-backend \
    --force-new-deployment \
    --region us-east-1
```

### Database Access
```bash
# Get database endpoint
aws cloudformation describe-stacks \
    --stack-name prod-airweave-stack \
    --query 'Stacks[0].Outputs[?OutputKey==`DatabaseEndpoint`].OutputValue' \
    --output text

# Connect via psql (requires VPN/bastion host)
psql -h <db-endpoint> -U airweave -d airweave
```

## 🔒 CORS Configuration

✅ **CORS is already configured** to allow requests from anywhere:

```python
# In dash-api-client/config.py
self.cors_origins = ["*"]
```

This allows your frontend applications to make requests to the Dash API Client from any domain.

## 🧪 Testing Deployment

### Health Checks
```bash
# Backend health
curl http://<alb-dns-name>/health

# Dash client health  
curl http://<alb-dns-name>/dash/health

# Backend API docs
curl http://<alb-dns-name>/docs

# Dash client API docs
curl http://<alb-dns-name>/dash/docs
```

### API Testing
```bash
# Test backend API
curl -X GET "http://<alb-dns-name>/api/v1/health"

# Test dash client API
curl -X GET "http://<alb-dns-name>/dash/collections"
```

## 💰 Cost Estimation

Approximate monthly costs for production environment:

- **ECS Fargate**: ~$30-50/month (2 tasks, 0.5 vCPU, 1GB RAM each)
- **RDS PostgreSQL (db.t3.micro)**: ~$15-20/month
- **ElastiCache Redis (cache.t3.micro)**: ~$15-20/month
- **Application Load Balancer**: ~$20-25/month
- **NAT Gateway**: ~$45/month
- **CloudWatch Logs**: ~$5-10/month
- **ECR Storage**: ~$1-5/month

**Total**: ~$130-175/month

## 🔐 Security Best Practices

1. **Use AWS Secrets Manager** for sensitive data (recommended for production):
   ```bash
   # Create secret
   aws secretsmanager create-secret \
       --name prod-airweave-secrets \
       --description "Airweave application secrets" \
       --secret-string '{"database_password":"your-password","encryption_key":"your-key"}'
   ```

2. **Enable VPC Flow Logs** for network monitoring

3. **Set up AWS WAF** for application firewall protection

4. **Use HTTPS** with ACM certificates:
   - Request SSL certificate in ACM
   - Update ALB listener to use HTTPS (port 443)
   - Redirect HTTP to HTTPS

## 🚨 Troubleshooting

### Common Issues

1. **Service fails to start**:
   ```bash
   # Check service events
   aws ecs describe-services \
       --cluster prod-airweave-cluster \
       --services prod-airweave-backend \
       --region us-east-1
   
   # Check task logs
   aws logs tail /ecs/prod-airweave-backend --region us-east-1
   ```

2. **Database connection issues**:
   - Verify security group rules
   - Check database endpoint and credentials
   - Ensure tasks are in correct subnets

3. **Load balancer health checks failing**:
   - Verify health check paths (/health)
   - Check application startup time
   - Review security group configurations

### Useful Commands

```bash
# List running tasks
aws ecs list-tasks \
    --cluster prod-airweave-cluster \
    --service-name prod-airweave-backend \
    --region us-east-1

# Describe task
aws ecs describe-tasks \
    --cluster prod-airweave-cluster \
    --tasks <task-arn> \
    --region us-east-1

# View stack events
aws cloudformation describe-stack-events \
    --stack-name prod-airweave-stack \
    --region us-east-1
```

## 🧹 Cleanup

To delete the entire deployment:

```bash
# Delete CloudFormation stack
aws cloudformation delete-stack \
    --stack-name prod-airweave-stack \
    --region us-east-1

# Delete ECR repositories (optional)
aws ecr delete-repository \
    --repository-name prod-airweave-backend \
    --force \
    --region us-east-1

aws ecr delete-repository \
    --repository-name prod-airweave-dash-client \
    --force \
    --region us-east-1
```

## 📞 Support

For issues:
1. Check CloudWatch logs first
2. Review CloudFormation events
3. Verify all prerequisites are met
4. Check AWS service limits in your account

## 🔄 CI/CD Integration

For automated deployments, integrate with:
- **GitHub Actions**: Use AWS credentials as secrets
- **AWS CodePipeline**: Native AWS CI/CD
- **Jenkins**: With AWS CLI and Docker plugins

Example GitHub Actions workflow:
```yaml
name: Deploy to AWS
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy to AWS
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          ./aws/deploy.sh prod us-east-1
``` 