# CashPilot — rules for AI coding agents (Claude Code, Cursor)

Read SPEC.md first. Build one feature at a time and run the tests before saying it's done.

## Stack
- Frontend: React 18 + Vite, plain CSS in `frontend/src/styles.css` (no Tailwind, no UI libraries)
- Backend: FastAPI + SQLAlchemy 2, Python 3.12, in `backend/app/`
- Database: SQLite locally, PostgreSQL in production (`DATABASE_URL`)
- AI: Anthropic SDK through `backend/app/ai/client.py` ONLY. Never call the model from anywhere else.

## Non-negotiable rules
1. Money is `Decimal` in Python and `Numeric(12,2)` in the database. Never use float for stored amounts.
2. Amounts are signed: negative = money out, positive = money in.
3. Every AI output goes through a forced tool call with a JSON schema, then a Pydantic model. No regex parsing of model text.
4. The AI never writes SQL and never does arithmetic we show to users. It plans; Python calculates.
5. Every query filters by `user_id`. Add a test whenever you add a query.
6. Rules before AI in categorization. User rules beat built-in rules.
7. Anything below `REVIEW_THRESHOLD` confidence is flagged `needs_review`.
8. Errors shown to users say what happened and how to fix it. No stack traces, no "Oops".
9. Secrets come from environment variables. Never hardcode keys. Never commit `.env`.
10. After changing an AI prompt, run `python -m eval.run_eval` and report the accuracy change.

## Commands
- Backend tests: `cd backend && python -m pytest -q`
- Run backend: `cd backend && uvicorn app.main:app --reload`
- Run frontend: `cd frontend && npm run dev`
