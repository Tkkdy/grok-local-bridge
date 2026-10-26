# Third-party notices

Original Grok Local Bridge code: Copyright (c) 2026 Tkkdy, MIT (LICENSE).

## Retained source

The following MIT components originate from the Attention Router public source snapshot 2cc995ce09ecf4bc8f6a07fa784293c5d6727274 and were previously adapted in Grok MCP Connect. Copyright and SPDX notices remain in each file and licenses/attention-router-MIT.txt:

- experiments/oauth_spike/oauth.py → src/grok_local_bridge/_vendor/ar_oauth.py: DCR, PKCE, exact callback consent; explicit scope and owner pairing.
- hub/durable_oauth.py → _vendor/ar_durable.py: SQLite hashed grants, refresh rotation/replay revocation; package-relative import.
- DPAPI primitives from hub/mcp_auth.py → _vendor/ar_dpapi.py: Windows CurrentUser protection, explicit caller-owned paths.

No firmware, GPL component, fonts, Hub/Todo business modules, private configuration or runtime data is included. Ask My AI source is not incorporated. The historical audit and private engineering sessions are not distributed.

## Installed dependencies

FastMCP 4.1.3: Apache-2.0; MCP SDK 2.3.0: MIT. Their license texts are retained in licenses/. They and all transitive packages are installed from PyPI, not bundled as binaries. Runtime distribution metadata is summarized in docs/dependency-licenses.json. That inventory is for the pinned environment; when redistributing dependency binaries, retain their complete license/NOTICE files, including MPL/PSF/BSD obligations where applicable.

cloudflared 2026.10.0 is Apache-2.0, downloaded from the official Cloudflare release with a pinned SHA-256 by the installer, not bundled in the source ZIP. [Cloudflare license](https://github.com/cloudflare/cloudflared/blob/2026.10.0/LICENSE). No Inspector, Node modules or external backend binaries are bundled. Supergateway (MIT) was evaluated as an alternative but is not a dependency.

The project's MIT license covers its original code and retained MIT portions; it does not relicense independent dependencies.
