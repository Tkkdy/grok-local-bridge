# v0.1.0-alpha validation

Experimental first independent release. Recorded on 2026-10-26 UTC on an existing Windows x64 development computer, Python 3.13.7, PowerShell 5.1, FastMCP 4.1.3 and MCP SDK 2.3.0. Package version: `0.1.0a0`. This is not a clean Windows VM or long-term service certification.

## Current release results

| Area | Result | Evidence / practical limit |
| --- | --- | --- |
| Separate installation | PASS | CheckOnly, install into a new path containing spaces, locked runtime installation, `pip check`, doctor, demo and direct installed-module verify. A second source-ZIP installation (SkipCloudflared, no public start) passed doctor/demo/verify. Existing installations were preserved. |
| Automated local suite | PASS | 34 tests, zero failures/errors, JUnit duration 162.943 seconds. Run `python -m pytest -q`. Tests and assertions are included; raw machine paths/logs are excluded. |
| Two independent MCPs | PASS, SYNTHETIC | `test_composition.py` and installed verify call Hub-shaped read-only state and Ping; distinct process IDs; no private Hub or real business data. |
| Transport boundary | PASS locally | Real loopback Streamable HTTP and stdio; `test_http_composition.py`, `test_backend_secrets.py`. Arbitrary network targets, redirects and ungranted tools are rejected. SSE and arbitrary third-party MCP compatibility are not accepted. |
| OAuth / credentials | PASS locally and over HTTPS | `test_oauth.py`, `test_authenticated_http.py`; DCR, owner consent, exact callbacks, PKCE, refresh persistence/replay revocation, no incoming Authorization forwarding. DPAPI tests run on Windows. |
| Add/remove and same connection | PASS locally and over HTTPS | `test_registry.py`, `test_management.py`, `test_release_features.py`; add third synthetic backend, wait APPLIED, discover/call, remove, deny removed call, retain healthy tools using the same access token. |
| Rate / sanitized audit | PASS locally | Per-tool limit and independent tool buckets; forbidden call denied; failing pre-call audit prevents backend dispatch. This is not an independent penetration test or tamper-evident business ledger. |
| Recovery | PASS locally and over HTTPS | Owned Gateway recovery preserves origin/Tunnel and usable grant. Local management tests use fake Tunnels; the separate HTTPS run used a real Quick Tunnel. OS reboot/autostart and crash loops over long periods are NOT TESTED. |
| Public HTTPS MCP | PASS, automated client only | New isolated 15-minute Quick Tunnel; real public discovery and both tool calls, unauthenticated/invalid token 401, unknown tool rejection, add/remove, Gateway recovery, explicit grant revocation. Test business data stayed SYNTHETIC. This client was not Inspector or GrokBot. |
| Public shutdown | PASS | A new valid grant could call Ping before stop. After owned stop: manager lock released, loopback port closed, public authenticated request returned HTTP 530. No other services were stopped. |
| Fresh MCP Inspector | NOT RUN | Predecessor Inspector evidence is historical only. |
| Fresh GrokBot | NOT VERIFIED | An optional user check was requested; no result was received before the test entry was stopped. No current-release GrokBot success is claimed. |
| Production writes / hardware | NOT RUN | No real `upsert_todo`, `set_current_item`, filesystem write adapter or hardware operation was exercised. |
| WorkBuddy import | FAILED historically, cause UNKNOWN | User still saw missing SKILL.md. Archive parsing alone did not locate the host/cloud failure stage. This alpha does not claim WorkBuddy import or cloud-to-Windows execution. |

## Source, security and license gates

- Whitelist source export from the exact V0.1.1 RC1 candidate, whose SHA-256 is in [provenance](provenance.md), followed by reviewed Bridge changes. Fresh Git history; no old repository or raw conversation/log export.
- Project source checker: tracked source whitelist, forbidden runtime/credential artifacts, private paths, real Quick Tunnel URLs, credential patterns, Python syntax and local Markdown links. Stage reviewed changes before running `python scripts/release_check.py`.
- Gitleaks 8.30.1 source scan with full redaction: zero findings. Official scanner archive verified against its release checksum. Scan the initial Git history as a separate publication gate.
- Dependency inventory: 70 locked runtime distributions; license metadata/files identified, notices retained. See [inventory](dependency-licenses.json) and [third-party notices](../THIRD_PARTY_NOTICES.md). Dependency executables are not bundled. No GPL/private firmware or Attention Router business module was exported.
- OSV public advisory API: queried all 70 runtime PyPI name/version pairs on 2026-10-26 UTC; no advisory IDs returned. This is a point-in-time database lookup, not proof of zero vulnerabilities. Source/security gates are not a penetration test or a complete vulnerability audit. CI repeats synthetic tests without public connections or account secrets.

## Reproduction and remaining acceptance

Follow [English README](../README_EN.md) or [Chinese README](../README.md) in a separate installation directory. Local `verify` executes the two packaged synthetic MCPs; it does not validate OAuth/Grok. For HTTPS acceptance, explicitly start this installation, finish owner authorization, list the full namespace, invoke both tools, then stop it and confirm remote closure. Never publish raw runtime state.

Historical predecessor Grok MCP Connect acceptance included real GrokBot discovery and calls to two synthetic MCPs. That evidence motivated reuse; it is not acceptance of the renamed release. Real Attention Router integration, durable stdio sessions, per-Agent authorization, external Named Tunnel, a Python-free clean Windows setup, OS reboot recovery and long-running reliability remain outside current acceptance. Quick Tunnel origins can change; reconnection/reauthorization can be necessary.
