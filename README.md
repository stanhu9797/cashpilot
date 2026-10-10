# CashPilot

AI bookkeeping and cash flow forecasting for freelancers and very small businesses.

Snap a receipt, import your bank file, and see cash problems weeks before they happen. Anything the app isn't sure about gets highlighted in yellow for you to check.

## What it does

- **Receipt capture:** Upload a photo or PDF. AI reads the merchant, date, total, and line items, and the backend double-checks the math. Unsure fields are highlighted.
- **Smart categorization:** Known vendors are categorized by rules; only unfamiliar merchants go to AI. When you correct a category, the app remembers it for that merchant.
- **Ask your books:** Ask questions like "What did I spend on software last quarter?" AI plans the question, Python does the math, and you see every transaction behind the answer.
- **90-day forecast:** Finds your regular bills and income, projects them forward, and warns you before your balance drops below a line you choose.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite, plain CSS, mobile responsive |
| Backend | FastAPI (Python 3.12) + SQLAlchemy |
| Database | SQLite locally, PostgreSQL (Amazon RDS) in production |
| AI | Claude via the Anthropic API or Amazon Bedrock |
| File storage | Local folder locally, Amazon S3 in production |
| Hosting | AWS Amplify (frontend) + AWS Lambda (API) |

---

## Run it on your computer

### 1. Install the prerequisites (one time)

- **Python 3.11 or newer:** check with `python3 --version`
- **Node.js 18 or newer:** check with `node --version`

### 2. Set up the project (one time)

Open a terminal in the `cashpilot` folder and run:

```bash
# Settings file
cp .env.example .env

# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed                 # creates a demo account with sample data
cd ..

# Frontend
cd frontend
npm install
cd ..
```

### 3. Start the app (every time)

You need **two terminal windows**, both opened in the `cashpilot` folder.

**Terminal 1, backend:**
```bash
cd backend
source .venv/bin/activate          # Windows: .venv\Scripts\activate
uvicorn app.main:app --reload
```

**Terminal 2, frontend:**
```bash
cd frontend
npm run dev
```

Open **http://localhost:5173** and sign in with:

- Email: `demo@cashpilot.app`
- Password: `demo-password`

### 4. Turn on the AI features

Without a key, imports, rules-based categorization, and the forecast all work. Receipt reading, AI categorization, and "Ask your books" need a key.

1. Get an API key from the Anthropic Console (console.anthropic.com).
2. Open `.env` and paste it after `ANTHROPIC_API_KEY=`.
3. Stop the backend (Ctrl+C) and start it again.

The yellow "AI features are off" notice on the Overview page disappears once the key is working.

### 5. Try it out

- **Import:** Go to Transactions, click Import bank CSV, and choose `samples/sample-bank-export.csv`. Import it twice to see duplicates skipped.
- **Correct a category:** Change a highlighted transaction's category. Then add a new transaction from the same merchant and watch it get filed automatically.
- **Forecast:** The demo account is set up to show a low-balance warning in early December.
- **Ask:** Try one of the example questions (needs an AI key).

---

## Check quality

### Automated tests

```bash
cd backend
python -m pytest -q
```

37 tests cover money math, security (rate limits, injection, file checks, access control), duplicate imports, correction rules, and the AI features. AI features are tested with a fake model, so tests cost nothing to run.

### Receipt accuracy check

This measures how accurate the AI is on receipts where you already know the right answer. Re-run it after any prompt or model change.

1. Put 30–50 receipt photos or PDFs in `backend/eval/receipts/`. Include hard ones: crumpled, faded, handwritten tips, long receipts.
2. Copy `backend/eval/expected.example.json` to `backend/eval/expected.json` and fill in the correct merchant, date, and total for each file.
3. Run:
   ```bash
   cd backend
   python -m eval.run_eval
   ```

You'll see accuracy for each field against the 90% target, plus a count of **wrong answers the AI was confident about**. Those are the dangerous ones, because they won't be highlighted for the user. Each run is saved in `backend/eval/results/` so you can compare before and after.

Receipts and results are ignored by git, so they never end up on GitHub.

---

## Deploy to AWS

CashPilot runs on AWS's free tier in two pieces: the React frontend on **AWS Amplify Hosting** (connected to this repo, rebuilds on every push) and the Python API on **AWS Lambda** with a public Function URL. See `DEPLOY.md` for the step-by-step guide.

The `Dockerfile` is kept as an alternative for container hosting (it serves the frontend and API together on port 8080).

### Using Amazon Bedrock instead of an API key

Set `AI_PROVIDER=bedrock`, your `AWS_REGION`, and `BEDROCK_MODEL_ID` (copy the Claude Sonnet model or inference profile ID from the Bedrock console, and make sure model access is enabled for your account).

---

## Working with AI coding agents

`CLAUDE.md` holds the project rules for Claude Code, and `.cursor/rules/cashpilot.mdc` points Cursor to the same file, so both tools follow identical standards. `SPEC.md` describes the features, data model, and API.

Good next prompts to try:

- "Add a quarterly estimated tax set-aside card to the Overview page, clearly labeled as an estimate."
- "Add a monthly summary that shows changes in each category compared with last month."
- "Let users export their transactions as a CSV."
- "Add a dark mode that follows the system setting."

After any change to an AI prompt, ask the agent to run the receipt accuracy check and report the difference.

---

## Troubleshooting

| What you see | What to do |
|---|---|
| "Can't reach the server" | The backend isn't running. Start it in Terminal 1. |
| "AI isn't set up yet" | Add your key to `.env` and restart the backend. |
| "The AI service didn't respond" | Check that the key is correct and your Anthropic account has credits. |
| `ModuleNotFoundError` | Activate the virtual environment: `source .venv/bin/activate` |
| Port already in use | Another copy is running. Close the other terminal or restart your computer. |
| Demo login doesn't work | Run `python -m app.seed` again from the `backend` folder. |
| CSV import error | The file needs a date column, a description column, and an amount column (or debit and credit columns). |

## Project structure

```
cashpilot/
├── backend/
│   ├── app/
│   │   ├── ai/client.py          # every AI call goes through here (logged, schema-validated)
│   │   ├── routers/              # API endpoints
│   │   ├── services/             # categorizer, receipts, ask, forecast, CSV import, storage
│   │   ├── models.py             # database tables
│   │   ├── schemas.py            # input validation
│   │   ├── auth.py               # sign-in tokens
│   │   ├── seed.py               # demo account
│   │   └── main.py               # app setup
│   ├── tests/                    # automated tests
│   └── eval/                     # receipt accuracy check
├── frontend/src/
│   ├── pages/                    # Overview, Transactions, Add receipt, Ask, Forecast, Login
│   ├── components/               # layout, chart, shared UI
│   └── styles.css
├── samples/                      # sample bank CSV
├── Dockerfile, docker-compose.yml
├── SPEC.md, CLAUDE.md
└── .env.example
```

## Security and testing

See `SECURITY.md` for the full security checklist and `TESTING.md` for the testing report and bugs fixed. In production the app refuses to start without a strong `JWT_SECRET`, and without a `DATABASE_URL` unless demo mode is on.
