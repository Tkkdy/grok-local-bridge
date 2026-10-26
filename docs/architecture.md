# Architecture and component choice

Grok Local Bridge uses FastMCP 4.1.3 proxy composition over MCP SDK 2.3.0. Each backend has a namespace and explicit grants. A fresh transport/client is created per proxy request: sharing a non-persistent stdio transport previously caused concurrent discovery to close another caller's session. Aggregation uses FastMCP, not handwritten MCP JSON-RPC.

| Option | Fit for this release | Decision |
|---|---|---|
| FastMCP composition/proxy | Existing working code, namespaces, stdio and HTTP; thin permission/OAuth adapter | Selected with the tested dependency lock |
| Supergateway | Useful transport conversion; switching still requires integrating this project's Grok OAuth, aggregate policy and lifecycle | Not introduced; no universal incompatibility or benchmark claim |
| Python MCP SDK | Official protocol primitives, retained underneath FastMCP and in auth types | No new handwritten aggregation layer |

Primary references: [FastMCP composition](https://gofastmcp.com/servers/composition), [Supergateway](https://github.com/supercorp-ai/supergateway), [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk). Upstream capabilities are not evidence of this project's client acceptance.

Cloud client → dedicated HTTPS Tunnel → loopback RequestBoundary → OAuth verifier → reloadable FastMCP provider → grant/rate/audit middleware → trusted independent local MCP.

Only MCP/OAuth routes are public; no remote administration. Exact callbacks, DCR, PKCE, consent, hashed durable grants and DPAPI reuse MIT Attention Router source with explicit isolated paths. Pending codes/pages are ephemeral. Config replacement atomically swaps the graph; invalid config closes tools. In-flight calls may finish. Complete discovery errors if a granted backend is unavailable; direct calls to healthy known tools continue. Rate windows reset on replacement/recovery. Resource templates/prompts are disabled.

Windows locks and Job Objects constrain cleanup to owned workers. Separate Tunnel/Gateway jobs permit recovery without replacing the Tunnel. No AR Hub import, private path, firmware or ESP32 dependency.

Supported public transport: stateless JSON Streamable HTTP. SSE/notification streaming, persistent stdio sessions, per-Agent ACL, arbitrary callbacks and OS-boot recovery remain outside alpha acceptance. Demo data is static synthetic AR-shaped state, not a real Hub API read. Downstream MCPs enforce their own path/hardware constraints.
