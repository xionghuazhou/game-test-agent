# Contributing to Game Test Agent

Thanks for your interest! Issues and PRs are welcome.

## Development setup

Follow the [Quick Start](README.md#-quick-start) in the README (Python 3.11+, `pip install -r requirements.txt`, copy `backend/.env.example` to `backend/.env`).

## Running checks

```bash
# Syntax check (same as CI)
python -m compileall -q backend

# End-to-end smoke run: start the server, create a task in the dashboard,
# and verify the demo-mode agents complete a 12-step test and report the planted bugs.
```

## Guidelines

- **Open an issue first** for major changes so we can discuss the approach.
- Keep PRs focused — one feature or fix per PR.
- Match the existing code style (type hints, Chinese docstrings are fine).
- If you add a bug pattern to `demo_game.py`, document it in the README feature list.
- Never commit `.env`, databases, or runtime screenshots — `.gitignore` covers them.

## Good first issues

Look for issues labeled `good first issue` — e.g. new planted bug patterns, bug-report export formats, dashboard polish.