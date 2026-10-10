#!/usr/bin/env bash
# Deploys the CashPilot API to AWS Lambda with a public Function URL (Lambda's always-free tier).
# Run from the cashpilot folder:   bash deploy/backend-lambda.sh
# Re-run any time to push backend code changes. Optional: export ANTHROPIC_API_KEY=... first to enable AI.
# Optional: bash deploy/backend-lambda.sh https://main.xxxx.amplifyapp.com   (locks CORS to your Amplify site)
set -euo pipefail
cd "$(dirname "$0")/.."
FN=cashpilot-api
REGION="${AWS_REGION:-$(aws configure get region || echo us-east-1)}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ORIGIN="${1:-*}"
echo "AWS account $ACCOUNT_ID, region $REGION"

echo "1/4 Packaging the API for Lambda (Linux, Python 3.12)..."
rm -rf build/lambda build/cashpilot-api.zip && mkdir -p build/lambda
python3 -m pip install --quiet --upgrade --target build/lambda \
  --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all: \
  -r backend/requirements-lambda.txt
cp -r backend/app backend/lambda_handler.py build/lambda/
find build/lambda -name "__pycache__" -type d -prune -exec rm -rf {} +
(cd build/lambda && zip -qr ../cashpilot-api.zip .)
echo "    package size: $(du -h build/cashpilot-api.zip | cut -f1)"

echo "2/4 Making sure the Lambda role exists..."
ROLE=cashpilot-lambda-role
if ! aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE" --assume-role-policy-document \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  aws iam attach-role-policy --role-name "$ROLE" --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  echo "    created role; waiting 15 seconds for AWS to register it"
  sleep 15
fi
ROLE_ARN="arn:aws:iam::$ACCOUNT_ID:role/$ROLE"

# Keep the same signing secret across redeploys so people stay signed in
EXISTING_SECRET=$(aws lambda get-function-configuration --function-name "$FN" --region "$REGION" \
  --query 'Environment.Variables.JWT_SECRET' --output text 2>/dev/null || true)
if [ -z "$EXISTING_SECRET" ] || [ "$EXISTING_SECRET" = "None" ]; then
  JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
else
  JWT_SECRET="$EXISTING_SECRET"
fi
AI_KEY="${ANTHROPIC_API_KEY:-$(aws lambda get-function-configuration --function-name "$FN" --region "$REGION" --query 'Environment.Variables.ANTHROPIC_API_KEY' --output text 2>/dev/null || true)}"
[ "$AI_KEY" = "None" ] && AI_KEY=""
ENV_JSON=$(python3 - "$JWT_SECRET" "$ORIGIN" "$AI_KEY" <<'PY'
import json, sys
secret, origin, key = sys.argv[1:4]
env = {"APP_ENV": "production", "DEMO_MODE": "true", "JWT_SECRET": secret, "CORS_ORIGINS": origin,
       "DATABASE_URL": "sqlite:////tmp/cashpilot.db", "UPLOAD_DIR": "/tmp/uploads"}
if key:
    env["ANTHROPIC_API_KEY"] = key
print(json.dumps({"Variables": env}))
PY
)

echo "3/4 Creating or updating the function..."
if aws lambda get-function --function-name "$FN" --region "$REGION" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$FN" --region "$REGION" --zip-file fileb://build/cashpilot-api.zip >/dev/null
  aws lambda wait function-updated --function-name "$FN" --region "$REGION"
  aws lambda update-function-configuration --function-name "$FN" --region "$REGION" --environment "$ENV_JSON" >/dev/null
else
  aws lambda create-function --function-name "$FN" --region "$REGION" --runtime python3.12 \
    --handler lambda_handler.handler --role "$ROLE_ARN" --zip-file fileb://build/cashpilot-api.zip \
    --memory-size 512 --timeout 60 --architectures x86_64 --environment "$ENV_JSON" >/dev/null
fi
aws lambda wait function-updated --function-name "$FN" --region "$REGION" 2>/dev/null || aws lambda wait function-active --function-name "$FN" --region "$REGION"

echo "4/4 Making sure the public URL exists..."
if ! aws lambda get-function-url-config --function-name "$FN" --region "$REGION" >/dev/null 2>&1; then
  aws lambda create-function-url-config --function-name "$FN" --region "$REGION" --auth-type NONE >/dev/null
  aws lambda add-permission --function-name "$FN" --region "$REGION" --statement-id public-url \
    --action lambda:InvokeFunctionUrl --principal "*" --function-url-auth-type NONE >/dev/null
fi
URL=$(aws lambda get-function-url-config --function-name "$FN" --region "$REGION" --query FunctionUrl --output text)
URL="${URL%/}"

echo
echo "API is live: $URL"
echo "Health check: $(curl -s "$URL/health" || echo 'not responding yet, try again in a minute')"
echo
echo "In Amplify, set the environment variable  VITE_API_BASE = $URL"
