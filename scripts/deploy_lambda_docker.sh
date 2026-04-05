#!/bin/bash
# Deploy Lambda as Docker container
# Run this from your LOCAL Mac

set -e

# Configuration - UPDATE THESE
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO_NAME="nhtsa-lambda"
LAMBDA_FUNCTION_NAME="nhtsa-recall-analyzer"

PROJECT_DIR="/Users/vaishnavis/Desktop/AWS_project"

echo "=========================================="
echo "Deploying Lambda as Docker Container"
echo "=========================================="
echo "AWS Account: $AWS_ACCOUNT_ID"
echo "Region: $AWS_REGION"
echo ""

# Step 1: Create ECR repository (if it doesn't exist)
echo "[1/5] Creating ECR repository..."
aws ecr create-repository --repository-name $ECR_REPO_NAME --region $AWS_REGION 2>/dev/null || echo "Repository already exists"

# Step 2: Login to ECR
echo "[2/5] Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Step 3: Build Docker image
echo "[3/5] Building Docker image..."
cd $PROJECT_DIR

# Copy src to lambda directory for Docker build
cp -r src lambda/src

docker build -t $ECR_REPO_NAME -f lambda/Dockerfile lambda/

# Clean up
rm -rf lambda/src

# Step 4: Tag and push to ECR
echo "[4/5] Pushing to ECR..."
docker tag $ECR_REPO_NAME:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest

# Step 5: Update Lambda function
echo "[5/5] Updating Lambda function..."
aws lambda update-function-code \
    --function-name $LAMBDA_FUNCTION_NAME \
    --image-uri $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest \
    --region $AWS_REGION

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo ""
echo "Image URI: $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest"
echo ""
echo "If you get errors, make sure:"
echo "1. Docker Desktop is running"
echo "2. Lambda function '$LAMBDA_FUNCTION_NAME' exists"
echo "3. You have the necessary IAM permissions"
