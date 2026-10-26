# Security boundaries

This alpha is a single-owner Windows connection, not a sandbox. Trusted stdio MCPs run with the Windows user's privileges; do not add arbitrary tools from untrusted repositories. Tool labels do not enforce file paths, business authorization or hardware safety. No general Shell/delete tool is granted by default. Every approved OAuth client shares the configured grant set; there is no per-Agent ACL.

## Authentication and network

The runtime binds 127.0.0.1. Only MCP and required OAuth/metadata paths are exposed. All MCP requests require a valid bearer issued by the local OAuth flow; duplicated/malformed Authorization headers are rejected. DCR accepts only the reviewed callback allowlist. PKCE S256, exact redirect/resource/scope binding, a local owner pairing code and one-time consent/code consumption remain enforced. The OAuth scope is named `connect` for compatibility.

Access lifetime is 600 seconds; rotating refresh families have a seven-day absolute expiry, replay detection and revocation. Pending consent/code state is memory-only. CurrentUser DPAPI protects pairing and backend secrets at rest. Tokens are hashed in the isolated SQLite store. DPAPI does not protect against malicious software already running as the same Windows user; state and token storage are sensitive.

Public HTTPS is supplied by a dedicated Cloudflare Tunnel. It is not authentication. Do not reuse production Tunnel identities or private OAuth databases. A client calling a tool can send its returned local data to a cloud model; local-first is not a promise that data never leaves the PC.

## Grants and limits

Exact tool grants apply to discovery and direct tools/call. Resources require exact URI grants; templates/prompts are disabled. Incoming Authorization is not forwarded to backends. Local HTTP uses literal loopback addresses, disables environment proxies and redirects. stdio inherits only the transport's necessary base environment plus explicitly configured DPAPI slot values.

Ingress accepts at most 64 KiB POST bodies and applies installation-wide 180 MCP/120 OAuth requests per minute. Each allowed tool defaults to 60 calls/minute, configurable by `tool_calls_per_minute` (1–600). Limits are shared by approved clients; config reload/recovery resets tool windows. These controls are not a distributed abuse-protection service or per-client fairness guarantee.

## Audit and changes

Tool events contain only configured tool identifiers, outcome, time; never arguments/results, headers, token/code/cookie values or exception text. A failing pre-call audit prevents dispatch. If the tool has already completed but its completion audit cannot be saved, the client receives an ambiguous completion error: do not blindly retry a side-effecting call. The log is not tamper-evident or a complete transaction ledger.

Config reload swaps the provider graph. New calls lose removed grants after APPLIED; in-flight calls can finish. Invalid config closes tools. Stop closes only owned jobs and the Tunnel, not independent backend services. Stop makes the remote entry unreachable while stopped; it does not revoke every stored grant permanently. Clients may use `/revoke` for their own grant. Persisted pending pages are not supported.

Never commit `.runtime`, `.env`, DPAPI, SQLite, logs, traces, private paths, conversations, Todo data, real device IDs or raw Codex sessions. Release from the reviewed tracked-file whitelist with fresh history. Preserve vendor license notices. Do not weaken OAuth, change proxy/firewall/DNS policy or install Windows tasks as a connectivity workaround.
