"""Single authenticated public surface; unknown routes and oversized bodies close."""
import re
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit
from starlette.responses import JSONResponse
from .composition import build_server
from .oauth import ConnectAuthorizationServer, ConnectVerifier, owner_credential
from .safe_events import SafeObservations

PUBLIC_PATHS = frozenset({
    "/mcp", "/authorize", "/consent", "/register", "/token", "/revoke",
    "/.well-known/oauth-protected-resource/mcp", "/.well-known/oauth-protected-resource",
    "/.well-known/oauth-authorization-server", "/.well-known/openid-configuration",
})

class RequestBoundary:
    def __init__(self, app, authorization, port):
        self.app, self.authorization = app, authorization
        self.hosts = {urlsplit(authorization.origin).netloc, f"127.0.0.1:{port}", f"localhost:{port}"}
        self.windows = defaultdict(deque)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)
        if scope["type"] != "http":
            return await send({"type": "websocket.close", "code": 1008})
        async def reject(error, status, headers=None):
            await JSONResponse({"error": error}, status_code=status,
                               headers={"Cache-Control": "no-store", **(headers or {})})(scope, receive, send)
        headers = scope.get("headers", [])
        hosts = [v.decode("latin-1") for k,v in headers if k.lower() == b"host"]
        if len(hosts) != 1 or hosts[0] not in self.hosts:
            return await reject("invalid_host", 400)
        path = scope["path"]
        if path not in PUBLIC_PATHS:
            return await reject("not_found", 404)
        # Global caps avoid trusting spoofable forwarding headers for security.
        category = "mcp" if path == "/mcp" else "oauth"
        window = self.windows[category]
        now = time.monotonic()
        while window and window[0] <= now - 60:
            window.popleft()
        if len(window) >= (180 if category == "mcp" else 120):
            return await reject("rate_limited", 429, {"Retry-After": "60"})
        window.append(now)
        if path == "/mcp":
            values = [v for k,v in headers if k.lower() == b"authorization"]
            supplied = bool(values)
            token = None
            if len(values) == 1:
                match = re.fullmatch(rb"(?i:Bearer) ([A-Za-z0-9_-]{43})", values[0])
                if match:
                    token = match.group(1).decode("ascii")
            valid = await self.authorization.verify_token(token) if token else None
            if not valid:
                challenge = f'Bearer resource_metadata="{self.authorization.origin}/.well-known/oauth-protected-resource/mcp", scope="connect"'
                if supplied:
                    challenge += ', error="invalid_token"'
                return await reject("invalid_token" if supplied else "authentication_required", 401,
                                    {"WWW-Authenticate": challenge})
        body = bytearray()
        if scope["method"] == "POST":
            while True:
                part = await receive()
                if part["type"] == "http.disconnect":
                    return
                body.extend(part.get("body", b""))
                if len(body) > 65536:
                    return await reject("request_too_large", 413)
                if not part.get("more_body", False):
                    break
        delivered = False
        async def replay():
            nonlocal delivered
            if not delivered and scope["method"] == "POST":
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()
        await self.app(scope, replay, send)

def create_application(config, *, origin, port, state_dir, owner_code=None, observations=None, dynamic=False, secrets_dir=None):
    from pathlib import Path
    state_dir = Path(state_dir)
    observations = observations or SafeObservations(state_dir / "events.jsonl")
    owner_code = owner_code if owner_code is not None else owner_credential(state_dir)
    authorization = ConnectAuthorizationServer(origin, observations, owner_code=owner_code,
                                                path=state_dir / "oauth.sqlite3")
    from .secret_store import SecretStore
    secrets = SecretStore(Path(secrets_dir) if secrets_dir else state_dir.parent / "secrets")
    registry = None
    if dynamic:
        from .registry import build_reloadable_server
        server, registry = build_reloadable_server(config, auth=ConnectVerifier(authorization), secret_store=secrets, observations=observations)
    else:
        server = build_server(config, auth=ConnectVerifier(authorization), secret_store=secrets, observations=observations)
    hosts = [urlsplit(origin).netloc, f"127.0.0.1:{port}", f"localhost:{port}"]
    mcp_app = server.http_app(path="/mcp", json_response=True, stateless_http=True,
                              allowed_hosts=hosts, allowed_origins=[origin])
    boundary = RequestBoundary(mcp_app, authorization, port)
    boundary.registry = registry
    return boundary, authorization, server
