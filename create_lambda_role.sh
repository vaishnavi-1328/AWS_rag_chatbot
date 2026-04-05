# Create the trust policy file
cat > /tmp/trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create the role
aws iam create-role \
    --role-name nhtsa-lambda-role \
    --assume-role-policy-document file:///tmp/trust-policy.json

# Attach permissions (3 separate commands)
aws iam attach-role-policy \
    --role-name nhtsa-lambda-role \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam attach-role-policy \
    --role-name nhtsa-lambda-role \
    --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess

aws iam attach-role-policy \
    --role-name nhtsa-lambda-role \
    --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess


# arn I have: "arn:aws:iam::406460435205:role/nhtsa-lambda-role"

