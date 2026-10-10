# CashPilot security checklist

Status as of the October 2026 audit. Each item is enforced in code and, where noted, covered by an automated test in `backend/tests/test_security.py`.

## Secrets and configuration
- [x] API keys, database URL, and JWT secret come only from environment variables (`.env` locally, Secrets Manager in AWS)
- [x] `.env`, receipts, local database, and eval data are in `.gitignore` and `.dockerignore`
- [x] No keys in frontend code; the browser never talks to the AI provider directly
- [x] Production refuses to start with the default or a short (<32 character) JWT secret
- [x] Production refuses to start without `DATABASE_URL`
- [x] Interactive API docs (`/docs`, `/openapi.json`) are disabled in production

## Authentication and access
- [x] Passwords hashed with bcrypt; 8–72 character limit (bcrypt ignores bytes past 72) *(tested)*
- [x] Signed JWT sessions with expiry; tampered tokens rejected *(tested)*
- [x] Sign-in rate limited: 5 attempts per account and 20 per network per 15 minutes *(tested)*
- [x] Account creation limited to 5 per network per hour
- [x] Same response and similar timing whether or not an email exists at sign-in
- [x] Every query filtered by the signed-in user; other users' records return 404 *(tested)*

## Injection and input handling
- [x] All database access through SQLAlchemy parameters; no string-built SQL *(tested with `'; DROP TABLE` input)*
- [x] Search escapes `%` and `_` so they can't act as wildcards *(tested)*
- [x] The AI never writes SQL; it returns a schema-checked plan with an allow-listed set of fields and categories
- [x] All AI output passes a JSON schema and a Pydantic model before use
- [x] Server-side validation on every input: lengths, number ranges, dates (2000 to today), categories, blank text *(tested)*
- [x] React escapes all displayed text, so stored `<script>` text renders harmlessly
- [x] Content Security Policy blocks inline and third-party scripts

## Files
- [x] Receipt type verified from the file's bytes, not the browser's label *(tested)*
- [x] 10 MB upload limit; only JPG, PNG, WEBP, GIF, PDF accepted
- [x] Files stored under random names; served only to their owner
- [x] S3 uploads use server-side encryption
- [x] CSV imports capped at 5,000 rows *(tested)*

## Abuse and cost controls
- [x] Per-user hourly limits on receipts (30), questions (30), forecast explanations (20), imports (20), and re-runs (10)

## Transport and browser
- [x] Security headers on every response: CSP, `X-Frame-Options: DENY`, `nosniff`, Referrer-Policy, Permissions-Policy *(tested)*
- [x] HSTS in production
- [x] `Cache-Control: no-store` on all API responses *(tested)*
- [x] CORS limited to configured origins

## Errors and logging
- [x] Unexpected errors return a generic message; details stay in server logs *(tested)*
- [x] Every AI call logged with feature, success, and latency (no receipts or passwords in logs)

## Known limitations
- Rate limits are in memory, so they reset on restart and aren't shared across multiple servers. Use Redis or AWS WAF rate rules when scaling out.
- Session tokens are kept in browser storage. The CSP reduces XSS risk; moving to HttpOnly cookies would remove it.
- No email verification or password reset yet.
- Dependencies should be scanned regularly (`pip-audit`, `npm audit`).
