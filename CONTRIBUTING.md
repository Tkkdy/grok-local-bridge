# Contributing

Use Windows x64 / Python 3.13 and the lock files. Create a separate venv, install requirements.lock and the project, then run pytest and scripts/release_check.py. CI needs no account secrets and uses a fake Tunnel. Keep synthetic fixture results distinct from real-client evidence.

For issues include version, OS, transport, failing stage, expected behavior and redacted error categories. Never attach raw state/logs, credentials, personal data or hardware IDs. Follow SECURITY.md for confidential reports.

Keep changes small and prefer backend manifests/adapters over new protocol or OAuth implementations. Add meaningful auth/grant/lifecycle regression coverage when behavior changes. Preserve third-party notices. Run against isolated data and owned processes; no production Hub/hardware or network policy changes. Do not commit runtime artifacts or private Git history.
