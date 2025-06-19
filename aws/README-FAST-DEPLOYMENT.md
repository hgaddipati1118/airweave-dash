# 🚀 Fast AWS Deployment (2-3 minutes instead of 20!)

This guide shows you how to reduce deployment times from **20 minutes to 2-3 minutes** while still using CloudFormation.

## 🧠 The Problem

The original deployment takes 20 minutes because it creates:
- **RDS PostgreSQL database** (~10-15 minutes)
- **ElastiCache Redis cluster** (~5-10 minutes)

These AWS services are inherently slow to provision, but they don't need to be recreated on every deployment.

## ✨ The Solution: Two-Stack Approach

We split the CloudFormation into two stacks:

1. **Infrastructure Stack** (slow, deploy once)
   - Database, Cache, Security Groups, Networking
   - Takes ~20 minutes, but only deployed once per environment

2. **Application Stack** (fast, deploy frequently) 
   - ECS Services, Load Balancer, Container Definitions
   - Takes ~2-3 minutes, deployed on every code change

## 🎯 Quick Start

### First Time Setup (20 minutes)

```bash
# Set required environment variables
export DB_PASSWORD="your-secure-password-12345"

# Deploy infrastructure (one-time setup)
./aws/deploy-infrastructure.sh prod us-east-1
```

### Regular Deployments (2-3 minutes)

```bash
# Set required environment variables
export ENCRYPTION_KEY="your-32-character-encryption-key"
export OPENAI_API_KEY="your-openai-key"  # optional
export MISTRAL_API_KEY="your-mistral-key"  # optional
export COMPOSIO_API_KEY="your-composio-key"  # optional

# Deploy application (fast!)
./aws/deploy-application.sh prod us-east-1
```

## 🔄 GitHub Actions Workflow

Use the new workflow: **Fast Deploy to AWS (Application Only)**

### First Time
1. Go to Actions → Fast Deploy to AWS
2. Check ☑️ "Deploy infrastructure stack" 
3. Run workflow (takes ~20 minutes)

### Regular Deployments  
1. Go to Actions → Fast Deploy to AWS
2. Leave "Deploy infrastructure stack" unchecked
3. Run workflow (takes ~2-3 minutes!)

## 📊 Deployment Time Comparison

| Approach | Infrastructure | Application | Total Time |
|----------|----------------|-------------|------------|
| **Old (airweave-simple.yaml)** | 20 min | - | **20 min** |
| **New (two stacks)** - First time | 20 min | 3 min | **23 min** |
| **New (two stacks)** - Regular | - | 3 min | **3 min** |

## 🏗️ Stack Architecture

### Infrastructure Stack (`airweave-infrastructure.yaml`)
```
📦 Infrastructure Stack (Deploy Once)
├── 🔐 Security Groups
├── 🗄️ RDS PostgreSQL Database  ← Slow (10-15 min)
├── 🚀 ElastiCache Redis         ← Slow (5-10 min)
└── 🌐 Networking Components
```

### Application Stack (`airweave-application.yaml`)
```
📦 Application Stack (Deploy Often)
├── ⚖️ Application Load Balancer  ← Fast (30 sec)
├── 🎯 Target Groups              ← Fast (10 sec)
├── 🚢 ECS Cluster               ← Fast (30 sec)
├── 📋 Task Definitions          ← Fast (10 sec)
└── 🔄 ECS Services              ← Fast (60 sec)
```

## 🔧 Advanced Usage

### Different Environments

```bash
# Deploy to staging
./aws/deploy-infrastructure.sh staging us-east-1
./aws/deploy-application.sh staging us-east-1

# Deploy to production
./aws/deploy-infrastructure.sh prod us-east-1
./aws/deploy-application.sh prod us-east-1
```

### Rollback Application

```bash
# Just redeploy application stack with older image tags
./aws/deploy-application.sh prod us-east-1
```

### Update Database/Cache

```bash
# Modify aws/cloudformation/airweave-infrastructure.yaml
# Then redeploy infrastructure (this will be slow)
./aws/deploy-infrastructure.sh prod us-east-1
```

## 🆚 Alternative Approaches Considered

### Option 1: External Database Services ❌
- **AWS RDS Serverless**: Still takes 5-10 minutes to resume from pause
- **Aurora Serverless v2**: Faster but more complex and expensive
- **External DB (Supabase/PlanetScale)**: Introduces external dependencies

### Option 2: Container-based Database ❌
- **PostgreSQL in ECS**: Data loss risk, not production-ready
- **StatefulSets**: Would require EKS, more complexity

### Option 3: Pre-provisioned Resources ✅ (Our Choice)
- **Separate stacks**: Keep slow resources separate from fast ones
- **Cross-stack references**: Use CloudFormation exports/imports
- **Best of both worlds**: Infrastructure-as-Code + Fast deployments

## 🐛 Troubleshooting

### "Infrastructure stack not found"
```bash
# Check if infrastructure stack exists
aws cloudformation describe-stacks \
  --stack-name prod-airweave-infrastructure-stack \
  --region us-east-1

# If not found, deploy it first
./aws/deploy-infrastructure.sh prod us-east-1
```

### "Unable to fetch parameters from parameter store"
```bash
# Ensure you have AWS credentials configured
aws sts get-caller-identity

# Check if you have the required environment variables
echo $ENCRYPTION_KEY
echo $DB_PASSWORD
```

### "ECS service failed to start"
```bash
# Check ECS service events
aws ecs describe-services \
  --cluster prod-airweave-cluster \
  --services prod-airweave-backend \
  --region us-east-1
```

## 💡 Benefits

✅ **85% faster deployments** (20 min → 3 min)  
✅ **Still uses CloudFormation** (Infrastructure-as-Code)  
✅ **No external dependencies** (everything in AWS)  
✅ **Same security model** (VPC, Security Groups)  
✅ **Easy rollbacks** (just redeploy application stack)  
✅ **Cost efficient** (database/cache provisioned once)  

## 🔮 Future Improvements

- **Blue/Green Deployments**: Zero-downtime deployments
- **Auto-scaling**: Scale based on load
- **Multi-AZ**: High availability setup
- **Backup automation**: Automated database backups 