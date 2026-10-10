# CashPilot testing report

## How it was tested
- **Automated backend tests:** 37 tests (`cd backend && python -m pytest -q`), including 13 security tests added in this round.
- **Abuse probe:** 22 malicious or unusual API requests (oversized passwords, SQL injection text, wildcard searches, 20,000-row CSV, fake images, tampered tokens).
- **Browser walkthrough:** 31 scripted checks in Chromium covering every screen, form, and button, keyboard-only navigation, and 375 px, 768 px, and 1280 px widths (`backend/tests/ui_walkthrough.py`). 31 of 31 pass.

## Bugs found and fixed
| # | Bug | Severity | Fix |
|---|---|---|---|
| 1 | Passwords over 72 bytes were silently cut off by bcrypt | High | Rejected with a clear message, front and back end |
| 2 | Unlimited sign-in attempts allowed password guessing | High | Rate limits per account and per network |
| 3 | Fake "images" were accepted and would be sent to the paid AI service | Medium | File type checked from its bytes |
| 4 | A 20,000-row CSV was accepted, which could trigger hundreds of AI calls | Medium | 5,000-row cap per import |
| 5 | Searching `%` or `_` matched every transaction | Medium | Wildcards escaped |
| 6 | Amounts typed as `$1,200.50` or `4,500` were rejected | Medium | Forgiving amount parser |
| 7 | A merchant of only spaces saved as blank | Low | Trimmed and required |
| 8 | Dates like 1900-01-01 were accepted | Low | Dates limited to 2000 through today |
| 9 | A question of only spaces reached the AI | Low | Trimmed and validated first |
| 10 | A crash in one screen would blank the whole app | Medium | Error boundary with a reload option |
| 11 | No way to delete a mistaken transaction | Low | Delete button with confirmation |
| 12 | Keyboard users had no skip link and lost their place after switching screens | Medium | Skip link and focus moved to each new heading |
