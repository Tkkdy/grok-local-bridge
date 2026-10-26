# Source and evidence provenance

The historical audit on 2026-10-24 proposed a two-backend FastMCP P0; that audit alone did not prove it existed. Subsequent Grok MCP Connect code implemented composition, transport isolation, a reloadable registry, OAuth/DPAPI adapters and owned Windows management. Predecessor synthetic real-Grok results were later recorded. A separate V0.1.1 RC1 public-source candidate passed 30 fresh local Windows tests on 2026-10-25.

This independent source export starts from that RC1 candidate, SHA-256 `6bc2fad496926d768e94460cc7adef9fa0389b8607101ebc9dafdc6d70eec1c3`. No private Git history, raw audit document, conversation, runtime database or original log was copied. This repository uses fresh history. Modifications for the first Bridge alpha are listed in CHANGELOG.md and tested in its own environment.

MIT vendor source and copyright provenance are listed in THIRD_PARTY_NOTICES.md. The Bridge does not import the Attention Router Hub, TodoCore or hardware runtime. The demo is a static isolated AR-shaped example, not proof of real Hub access. Current tests and client results belong in validation.md, with each execution client identified separately.
