# Security Policy

## Supported versions

Security-relevant fixes are applied to the latest commit on `main` only.

## Reporting a vulnerability

Do NOT open a public issue. Report in private to the repository owner via GitHub
(https://github.com/Tradeplusmore) or by raising a private vulnerability report from
the repository's "Security" tab.

Please include:
- A minimal description of the issue
- Affected endpoints/modules (e.g. `api_server.py`, `features/odds_aggregator.py`)
- Steps to reproduce if possible

You will receive an acknowledgement within 5 business days. Do not disclose the issue
publicly before a fix is released.

## Secrets handling

- All live API keys live only in local, gitignored files (`.env` / `local.env`).
- Never commit `local.env`, `.env`, `.env.local` or any other file containing keys.
- CI runs `scripts/security/check_no_secrets.py` and fails the build on any match.
- The historical `ODDS_API_KEY` value `9b49...f83` posted publicly is considered compromised —
  rotate it on the-odds-api.com if still in use anywhere.