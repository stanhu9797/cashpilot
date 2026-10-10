# CashPilot specification

## Problem
Freelancers and very small businesses have the same bookkeeping obligations as larger companies but can't justify a bookkeeper. Receipts get lost, expenses get miscategorized, quarterly taxes arrive as surprises, and cash shortfalls are discovered after they happen.

## Target user
A solo operator (designer, consultant, contractor) with about 10 minutes a week for bookkeeping.

## Design principle
AI suggests, the user confirms. Anything the app isn't sure about is highlighted for review, and every number can be traced back to the transactions behind it.

## User stories
1. As a freelancer, I can photograph a receipt and have the merchant, date, and total filled in for me, with unsure fields highlighted.
2. As a freelancer, I can import my bank's CSV export without creating duplicates.
3. As a freelancer, I see a suggested category and confidence for every transaction, and I can fix one with a single tap.
4. As a freelancer, when I correct a category, the app remembers it for that merchant.
5. As a freelancer, I can ask a plain-English question about my spending or income and see the transactions behind the answer.
6. As a freelancer, I can see a 90-day balance forecast and get warned before my balance drops below a line I choose.

## Success metrics
- Receipt extraction accuracy of 90% or higher on the evaluation set (merchant, date, total)
- 85% or more of transactions categorized correctly without a user edit
- Weekly bookkeeping time under 10 minutes
- Zero answers in "Ask your books" containing numbers the backend didn't calculate

## Data model
- **User:** email, password hash, name, current balance, low-balance threshold
- **Transaction:** date, merchant, description, signed amount, category, confidence, category source, needs-review flag, source (manual, csv, receipt, demo), optional receipt link, duplicate-check key
- **Receipt:** stored file key, file type, status, extracted fields (JSON)
- **CategoryRule:** normalized merchant name to category, created when a user corrects a category
- **Correction:** history of every category change, used as examples for the AI
- **AILog:** every AI call with feature, model, output, success, and latency

## API
| Method | Path | Purpose |
|---|---|---|
| POST | /api/auth/register, /api/auth/login | Create account, sign in |
| GET | /api/auth/me | Current user |
| PUT | /api/auth/settings | Balance and low-balance line |
| GET | /api/dashboard | This month's totals, top categories, review count |
| GET, POST | /api/transactions | List with filters, add one |
| POST | /api/transactions/import | Bank CSV import with duplicate skipping |
| PATCH | /api/transactions/{id}/category | Correct a category (creates a rule) |
| POST | /api/transactions/{id}/confirm | Mark a suggestion as right |
| POST | /api/transactions/recategorize | Re-run rules and AI on items needing review |
| POST | /api/receipts | Upload and extract a receipt |
| POST | /api/ask | Ask your books |
| GET | /api/forecast | 90-day forecast |
| POST | /api/forecast/explain | Plain-English explanation of the forecast |
| GET | /health | Health check for the host |

## Where AI is and isn't used
| Task | Tool | Why |
|---|---|---|
| Reading receipts | AI (vision) | Messy, unstructured images |
| Categorizing unfamiliar merchants | AI, after rules | Cryptic bank descriptions need interpretation |
| Categorizing known vendors | Rules | Faster, free, and always consistent |
| Turning a question into a query | AI (structured plan) | Natural language to structure |
| Calculating totals | Python | Arithmetic must be exact |
| Forecasting | Statistics | LLMs shouldn't predict numbers |
| Explaining results | AI | Plain-language summaries of numbers already calculated |

## Out of scope for the MVP
Bank account linking, quarterly tax estimates, invoicing, multiple businesses per account, and shared access for an accountant.
