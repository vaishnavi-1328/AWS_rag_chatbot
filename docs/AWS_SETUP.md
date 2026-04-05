# AWS Setup Guide (Beginner-Friendly)
 
Complete step-by-step guide to deploy the NHTSA Recall Analyzer on AWS. This guide includes troubleshooting for common issues encountered during setup.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Create AWS Account](#step-1-create-aws-free-tier-account)
3. [Set Up Billing Alerts](#step-2-set-up-billing-alert)
4. [Install AWS CLI](#step-3-install-and-configure-aws-cli)
5. [Create S3 Bucket](#step-4-create-s3-bucket)
6. [Enable Bedrock](#step-5-enable-bedrock-model-access)
7. [Create Lambda Function](#step-6-create-lambda-function)
8. [Create API Gateway](#step-7-create-api-gateway)
9. [Launch EC2](#step-8-launch-ec2-for-streamlit)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, make sure you have:
- [ ] AWS Account (we'll create a free tier account if you don't have one)
- [ ] A computer with Python 3.11+ installed
- [ ] Terminal/Command Prompt access

---

## Step 1: Create AWS Free Tier Account (Skip if you have one)

1. Go to [https://aws.amazon.com/free](https://aws.amazon.com/free)
2. Click **"Create a Free Account"**
3. Enter your email and create a password
4. Choose **"Personal"** account type
5. Enter your payment info (you won't be charged if staying within free tier)
6. Complete phone verification
7. Select **"Basic Support - Free"**
8. Sign in to the AWS Console

**Important:** Set up a billing alert immediately (see Step 2).

---

## Step 2: Set Up Billing Alert (Prevent Unexpected Charges)

This is CRITICAL to avoid surprise bills.

1. Go to AWS Console: [https://console.aws.amazon.com](https://console.aws.amazon.com)
2. In the search bar at top, type **"Billing"** and click **"Billing and Cost Management"**
3. In the left sidebar, click **"Budgets"**
4. Click **"Create budget"**
5. Choose **"Use a template"** → Select **"Zero spend budget"**
6. Budget name: `my-zero-spend-alert`
7. Email: Enter your email
8. Click **"Create budget"**

Now you'll get an email if ANY charges occur.

**Create another budget for $10:**
1. Click **"Create budget"** again
2. Choose **"Use a template"** → Select **"Monthly cost budget"**
3. Budget name: `my-10-dollar-limit`
4. Budgeted amount: `10`
5. Email: Your email
6. Click **"Create budget"**

---

## Step 3: Install and Configure AWS CLI

The AWS CLI lets you run AWS commands from your terminal.

### On Mac:
```bash
# Install using Homebrew
brew install awscli

# Verify installation
aws --version
```

### On Windows:
1. Download installer from: https://aws.amazon.com/cli/
2. Run the MSI installer
3. Open Command Prompt and verify:
```bash
aws --version
```

### Configure AWS CLI with Your Credentials:

1. Go to AWS Console
2. Click your account name (top right) → **"Security credentials"**
3. Scroll down to **"Access keys"**
4. Click **"Create access key"**
5. Select **"Command Line Interface (CLI)"**
6. Check the acknowledgment box
7. Click **"Create access key"**
8. **IMPORTANT:** Download the CSV file or copy both keys NOW (you can't see the secret key again!)

9. In your terminal, run:
```bash
aws configure
```

10. Enter when prompted:
```
AWS Access Key ID: [paste your access key]
AWS Secret Access Key: [paste your secret key]
Default region name: us-east-1
Default output format: json
```

11. Verify it works:
```bash
aws sts get-caller-identity
```

You should see your account ID. If you get an error, re-run `aws configure` and check your keys.

---

## Step 4: Create S3 Bucket

### IMPORTANT: Bucket Types

AWS S3 has TWO types of buckets:
- **General Purpose** - Standard S3 bucket (THIS IS WHAT WE NEED)
- **Directory Bucket** - For high-performance workloads (NOT what we need)

**If you accidentally created a Directory Bucket, delete it first.**

### Create the Correct Bucket:

1. Go to S3 Console: [https://s3.console.aws.amazon.com/s3/buckets](https://s3.console.aws.amazon.com/s3/buckets)
2. Click the orange **"Create bucket"** button
3. **Bucket type:** Select **"General purpose"** ← IMPORTANT!
4. **Bucket name:** `nhtsa-analyzer-YOURNAME-2024` (must be globally unique)
5. **AWS Region:** `US East (N. Virginia) us-east-1`
6. **Object Ownership:** Keep default "ACLs disabled"
7. **Block Public Access:** Keep all boxes CHECKED (we want it private)
8. **Bucket Versioning:** Disable
9. Click **"Create bucket"**

**Write down your bucket name!** You'll need it later.

### Verify bucket was created:
```bash
aws s3 ls
```

---

## Step 5: Enable Bedrock Model Access

Bedrock models must be explicitly enabled before use.

1. Go to Bedrock Console: [https://console.aws.amazon.com/bedrock](https://console.aws.amazon.com/bedrock)
2. **IMPORTANT:** Make sure you're in **US East (N. Virginia)** region (check top-right dropdown)
3. In the left sidebar, click **"Model access"** (under "Bedrock configurations")
4. Click **"Modify model access"** (orange button)
5. Find and CHECK these models:
   - **Anthropic** → **Claude 3 Haiku**
6. Click **"Next"** at bottom
7. Click **"Submit"**

**Wait 1-2 minutes** for access to be granted. The status should change to "Access granted".

---

## Step 6: Create Lambda Function

### 6.1 Create the Lambda Function (Console)

1. Go to Lambda Console: [https://console.aws.amazon.com/lambda](https://console.aws.amazon.com/lambda)
2. Make sure you're in **us-east-1** region
3. Click **"Create function"**
4. Choose **"Author from scratch"**
5. Fill in:
   - Function name: `nhtsa-recall-analyzer`
   - Runtime: **Python 3.11**
   - Architecture: **x86_64**
6. Click **"Create function"**

### 6.2 Upload Lambda Code

**IMPORTANT: Lambda Size Limits**
- Direct upload: **50 MB** (zipped)
- Unzipped size: **250 MB**
- If your package is larger, see [Troubleshooting - Lambda Package Too Large](#lambda-package-too-large)

**For this project, we use a simplified handler that only requires boto3 (pre-installed in Lambda):**

1. On your local machine, create the zip:
```bash
cd /path/to/AWS_project
zip -j lambda_simple.zip lambda/handler_simple.py
```

2. In Lambda Console:
   - Click **"Upload from"** → **".zip file"**
   - Upload `lambda_simple.zip`
   - Click **"Save"**

3. Update the **Handler** setting:
   - Scroll to **Runtime settings** → Click **Edit**
   - Change Handler to: `handler_simple.lambda_handler`
   - Click **Save**

### 6.3 Configure Lambda

**General Configuration:**
1. Click **Configuration** tab → **General configuration** → **Edit**
2. Set:
   - Memory: `512` MB
   - Timeout: `1` min `0` sec
3. Click **Save**

**Environment Variables:**
1. Click **Environment variables** → **Edit**
2. Add:
   - `S3_BUCKET_NAME` = `your-bucket-name`
   - `AWS_REGION` = `us-east-1`
3. Click **Save**

**Permissions (Add Bedrock Access):**
1. Click **Configuration** → **Permissions**
2. Click the **Role name** link (opens IAM)
3. Click **Add permissions** → **Attach policies**
4. Search and add: **AmazonBedrockFullAccess**
5. Click **Add permissions**

### 6.4 Test Lambda

1. Click **Test** tab
2. Create test event with this JSON:
```json
{
  "body": "{\"query\": \"Are there any recalls for 2019 Ford F-150?\"}",
  "httpMethod": "POST"
}
```
3. Click **Test**

**Expected Response:**
```json
{
  "statusCode": 200,
  "headers": {...},
  "body": "{\"response\": \"Here's what I found...\"}"
}
```

---

## Step 7: Create API Gateway

### 7.1 Create the API

1. Go to API Gateway Console: [https://console.aws.amazon.com/apigateway](https://console.aws.amazon.com/apigateway)
2. Click **"Create API"**
3. Under **REST API** (not private), click **"Build"**
4. Choose **"New API"**
5. API name: `nhtsa-api`
6. Click **"Create API"**

### 7.2 Create Resource and Method

1. Click **"Create resource"**
2. Resource name: `query`
3. Check **"CORS"** ← IMPORTANT for frontend
4. Click **"Create resource"**

5. Click on `/query`
6. Click **"Create method"**
7. Fill in:
   - Method type: **POST**
   - Integration type: **Lambda function**
   - **Enable Lambda proxy integration** ← CRITICAL!
   - Lambda function: `nhtsa-recall-analyzer`
8. Click **"Create method"**

### 7.3 Deploy the API

1. Click **"Deploy API"** (top right)
2. Stage: **New stage**
3. Stage name: `prod`
4. Click **"Deploy"**

**Copy your Invoke URL!** It looks like:
```
https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod
```

### 7.4 Test the API

```bash
curl -X POST https://YOUR_API_URL/prod/query \
  -H "Content-Type: application/json" \
  -d '{"query": "2019 Ford F-150 recalls"}'
```

**Expected:** JSON response with recall information

**If you get `{"message":"Missing Authentication Token"}`:**
- You're accessing the wrong URL (don't add `/query` twice)
- Make sure you're using POST, not GET

---

## Step 8: Launch EC2 for Streamlit

### 8.1 Create EC2 Instance

1. Go to EC2 Console: [https://console.aws.amazon.com/ec2](https://console.aws.amazon.com/ec2)
2. Click **"Launch instance"**
3. Configure:
   - Name: `nhtsa-frontend`
   - AMI: **Amazon Linux 2023**
   - Instance type: `t2.micro` (Free tier)
   - Key pair: Create new → Name: `nhtsa-key` → Download .pem file
   - Network: Check **Allow HTTP traffic**
4. Click **"Launch instance"**

### 8.2 Configure Security Group

**IMPORTANT:** You must allow HTTP (port 80) traffic.

1. Go to EC2 → Instances → Click your instance
2. Click **Security** tab → Click the Security Group link
3. Click **Edit inbound rules**
4. Add rule:
   - Type: **HTTP**
   - Source: **Anywhere-IPv4** (0.0.0.0/0)
5. Click **Save rules**

### 8.3 Copy Files to EC2

**IMPORTANT: Run these from your LOCAL machine, not from EC2!**

Your terminal prompt tells you where you are:
- `yourname@MacBook ~ %` = Local Mac ✓
- `[ec2-user@ip-xxx]$` = EC2 server ✗

**Step 1: Create directory on EC2**
```bash
ssh -i ~/Downloads/nhtsa-key.pem ec2-user@YOUR_EC2_IP "sudo mkdir -p /opt/nhtsa-app && sudo chown ec2-user:ec2-user /opt/nhtsa-app"
```

**Step 2: Copy only essential files (NOT venv or node_modules)**
```bash
scp -i ~/Downloads/nhtsa-key.pem -r \
  /path/to/AWS_project/src \
  /path/to/AWS_project/scripts \
  /path/to/AWS_project/frontend \
  /path/to/AWS_project/docs \
  /path/to/AWS_project/data \
  /path/to/AWS_project/requirements.txt \
  ec2-user@YOUR_EC2_IP:/opt/nhtsa-app/
```

**Why selective copy?**
- `venv/` folder is 300+ MB (Python packages for YOUR machine)
- `lambda/build/` can be 100+ MB
- We only need the source code (~1 MB)

### 8.4 Set Up EC2

**Connect to EC2:**
```bash
ssh -i ~/Downloads/nhtsa-key.pem ec2-user@YOUR_EC2_IP
```

**Run the setup script:**
```bash
bash /opt/nhtsa-app/scripts/ec2_full_setup.sh
```

**Or run manually:**
```bash
# Install packages
sudo yum update -y
sudo yum install -y python3.11 python3.11-pip nginx

# Install Python dependencies
pip3.11 install --user streamlit boto3 requests

# Create systemd service
sudo tee /etc/systemd/system/streamlit.service > /dev/null << 'EOF'
[Unit]
Description=Streamlit NHTSA App
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/opt/nhtsa-app/frontend
Environment="PATH=/home/ec2-user/.local/bin:/usr/bin"
Environment="API_GATEWAY_URL=https://YOUR_API_GATEWAY_URL/prod"
ExecStart=/home/ec2-user/.local/bin/streamlit run app.py --server.port 8501 --server.headless true
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# IMPORTANT: Update the API URL
sudo nano /etc/systemd/system/streamlit.service
# Change YOUR_API_GATEWAY_URL to your actual URL
# Save: Ctrl+O, Enter, Ctrl+X

# Configure Nginx
sudo tee /etc/nginx/conf.d/streamlit.conf > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
EOF

# Start services
sudo systemctl daemon-reload
sudo systemctl enable streamlit nginx
sudo systemctl start streamlit nginx
```

### 8.5 Access Your App

Open browser: `http://YOUR_EC2_PUBLIC_IP`

---

## Troubleshooting

### Lambda Package Too Large

**Problem:** "Unzipped size must be smaller than 262144000 bytes"

**Why:** LangGraph + FAISS + LangChain exceed Lambda's 250MB limit.

**Solutions (in order of preference):**

1. **Use Simplified Handler (Recommended for demos)**
   - Use `handler_simple.py` which only needs `boto3` (pre-installed)
   - Limited functionality but works within limits
   ```bash
   zip -j lambda_simple.zip lambda/handler_simple.py
   ```

2. **Use Docker Container**
   - Allows up to 10GB
   - Requires Docker Desktop
   - See `scripts/deploy_lambda_docker.sh`

3. **Use Lambda Layers**
   - Split dependencies into layers
   - Each layer max 250MB unzipped
   - Complex to manage

### API Gateway Returns Full Lambda Response

**Problem:** Response shows `{"statusCode": 200, "headers": {...}, "body": "..."}`

**Solution:** Enable Lambda Proxy Integration
1. API Gateway → Resources → POST method
2. Integration Request → Check **"Use Lambda Proxy integration"**
3. Deploy API again

### "Missing query parameter" Error

**Problem:** Lambda returns `{"error": "Missing query parameter"}`

**Cause:** The request body isn't being passed correctly.

**Debug Steps:**
1. Add logging to Lambda:
   ```python
   print(f"Received event: {json.dumps(event)}")
   ```
2. Check CloudWatch logs to see what Lambda receives
3. Ensure API Gateway has Lambda Proxy integration enabled
4. Ensure you're sending POST with JSON body

### EC2 Website Not Loading

**Problem:** Browser can't connect to EC2 IP

**Check Security Group:**
1. EC2 → Instances → Your instance → Security tab
2. Security group must have:
   - HTTP (port 80) from 0.0.0.0/0
   - (Optional) HTTPS (port 443)
   - (Optional) Custom TCP 8501 for direct Streamlit access

**Check Services on EC2:**
```bash
sudo systemctl status streamlit
sudo systemctl status nginx

# View logs
sudo journalctl -u streamlit -f
```

### "No response received" on Website

**Problem:** Website loads but queries return no response

**Check API Gateway URL:**
```bash
# On EC2, check what URL is configured
cat /etc/systemd/system/streamlit.service | grep API_GATEWAY
```

**Test API directly:**
```bash
curl -X POST https://YOUR_API_URL/prod/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
```

**Update API URL if wrong:**
```bash
sudo nano /etc/systemd/system/streamlit.service
# Edit the API_GATEWAY_URL line
sudo systemctl daemon-reload
sudo systemctl restart streamlit
```

### SCP/SSH Issues

**Problem:** "Permission denied" or "Identity file not accessible"

**Check where you are:**
- Local Mac: `yourname@MacBook ~ %`
- EC2: `[ec2-user@ip-xxx]$`

**SCP must run from LOCAL machine**, not EC2.

**Fix permissions:**
```bash
chmod 400 ~/Downloads/nhtsa-key.pem
```

### Bedrock Access Denied

**Problem:** "AccessDeniedException" when calling Bedrock

**Solutions:**
1. Ensure models are enabled in Bedrock console
2. Check Lambda role has `AmazonBedrockFullAccess` policy
3. Verify you're in `us-east-1` region

---

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser   │────▶│    EC2      │────▶│ API Gateway │
│   (User)    │     │  Streamlit  │     │             │
└─────────────┘     │  + Nginx    │     └──────┬──────┘
                    └─────────────┘            │
                                               ▼
                                        ┌─────────────┐
                                        │   Lambda    │
                                        │  (Python)   │
                                        └──────┬──────┘
                                               │
                          ┌────────────────────┼────────────────────┐
                          ▼                    ▼                    ▼
                   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
                   │   Bedrock   │      │     S3      │      │ CloudWatch  │
                   │   Claude    │      │   (Data)    │      │   (Logs)    │
                   └─────────────┘      └─────────────┘      └─────────────┘
```

**Data Flow:**
1. User enters query in Streamlit UI (EC2)
2. Streamlit sends POST request to API Gateway
3. API Gateway triggers Lambda function
4. Lambda calls Bedrock Claude for AI response
5. Response flows back through the chain to user

---

## Cost Summary

| Service | Free Tier Limit | Our Usage | Monthly Cost |
|---------|-----------------|-----------|--------------|
| Lambda | 1M requests/month | ~500 | $0 |
| EC2 t2.micro | 750 hours/month | 720 | $0 |
| S3 | 5 GB | ~50 MB | $0 |
| API Gateway | 1M calls/month | ~500 | $0 |
| **Bedrock** | **No free tier** | ~500 calls | **~$1-2** |

**Total: ~$1-2/month** (only Bedrock charges)

---

## Cleanup (To Avoid Charges)

```bash
# Stop EC2 (keeps data, can restart)
aws ec2 stop-instances --instance-ids YOUR_INSTANCE_ID

# Or terminate EC2 (deletes everything)
aws ec2 terminate-instances --instance-ids YOUR_INSTANCE_ID

# Delete Lambda
aws lambda delete-function --function-name nhtsa-recall-analyzer

# Delete API Gateway (easier via console)
# Go to API Gateway → Select API → Actions → Delete

# Empty and delete S3 bucket
aws s3 rm s3://your-bucket-name --recursive
aws s3 rb s3://your-bucket-name
```

---

## Quick Reference

| Resource | Value |
|----------|-------|
| Region | `us-east-1` |
| Lambda Function | `nhtsa-recall-analyzer` |
| Lambda Handler | `handler_simple.lambda_handler` |
| API Gateway Stage | `prod` |
| EC2 AMI | Amazon Linux 2023 |
| EC2 Type | t2.micro |
