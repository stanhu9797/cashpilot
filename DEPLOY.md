# Deploying CashPilot to AWS (Amplify + Lambda, free tier)

CashPilot has two parts, so it deploys in two pieces:

| Part | Where | Cost |
|---|---|---|
| React frontend (the screens) | AWS Amplify Hosting, connected to GitHub, rebuilds on every push | Free tier: 1,000 build minutes, 15 GB served per month |
| Python API (data, AI, forecast) | AWS Lambda with a public Function URL | Lambda always-free tier |

## Step 1: Deploy the API (about 5 minutes)

From the `cashpilot` folder in Terminal:
```bash
bash deploy/backend-lambda.sh
```
It prints a URL like `https://abc123.lambda-url.us-east-1.on.aws`. Copy it.
(Optional: run `export ANTHROPIC_API_KEY=your-key` first to turn on AI features.)

## Step 2: Push the code to a new GitHub repository

In Cursor: Source Control panel -> Publish to GitHub -> name it `cashpilot`. Check that `.env` is not in the file list.

## Step 3: Create the Amplify app (same flow as Relist)

1. Amplify console -> **Create new app** -> **GitHub** -> pick the `cashpilot` repo and the `main` branch.
2. Check **"My app is a monorepo"** and enter `frontend` as the root directory.
3. Build settings are detected from `amplify.yml` automatically.
4. Open **Advanced settings** -> add environment variable `VITE_API_BASE` = the Lambda URL from step 1.
5. **Save and deploy.** In 2 to 4 minutes you get `https://main.xxxx.amplifyapp.com`.

## Step 4 (recommended): Lock the API to your site

```bash
bash deploy/backend-lambda.sh https://main.xxxx.amplifyapp.com
```
This lets only your Amplify site call the API from a browser.

## After that

- Frontend changes: `git push` and Amplify rebuilds automatically.
- Backend changes: re-run `bash deploy/backend-lambda.sh https://main.xxxx.amplifyapp.com`.
- GitHub also runs the test suite on every push (the "Tests" workflow).

## Demo mode

The live API runs with `DEMO_MODE=true` and keeps data in Lambda's temporary storage. It re-creates the demo account (demo@cashpilot.app / demo-password) whenever Lambda starts fresh, so changes reset after idle periods. For real users, connect a database with `DATABASE_URL`.

## Checking status and cost

```bash
aws amplify list-apps --query 'apps[].[name,defaultDomain]' --output table
aws lambda get-function-url-config --function-name cashpilot-api --query FunctionUrl --output text
aws ce get-cost-and-usage --time-period Start=$(date +%Y-%m-01),End=$(date -v+1d +%Y-%m-%d) --granularity MONTHLY --metrics UnblendedCost
```
