"""Adapt the verified Attention Router OAuth implementation to FastMCP."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from fastmcp.server.auth import TokenVerifier, AccessToken
from starlette.routing import Route
from ._vendor.ar_durable import DurableAuthorizationServer
from ._vendor.ar_dpapi import provision_credential, load_credential
from .safe_events import SafeObservations

DEFAULT_CALLBACKS = frozenset({
    "https://www.cursor.com/agents/mcp/oauth/callback",
    "https://cursor.com/agents/mcp/oauth/callback",
    "http://localhost:8787/callback",
    "cursor://anysphere.cursor-mcp/oauth/callback",
    "http://localhost:6274/oauth/callback",
    "http://127.0.0.1:6274/oauth/callback",
})

def validate_origin(origin):
    u = urlsplit(origin)
    if u.username or u.password or u.path or u.query or u.fragment or not u.hostname:
        raise ValueError("origin must be a bare public HTTPS origin or test loopback origin")
    if u.scheme != "https" and not (u.scheme == "http" and u.hostname in ("127.0.0.1", "::1")):
        raise ValueError("public origin requires HTTPS")
    return origin

class ConnectAuthorizationServer(DurableAuthorizationServer):
    def __init__(self, origin, observations, *, owner_code, path,
                 callbacks=DEFAULT_CALLBACKS, clock=None, access_ttl=600,
                 refresh_ttl=7 * 86400):
        self.callbacks = frozenset(callbacks)
        kwargs = {"clock": clock} if clock else {}
        super().__init__(validate_origin(origin), observations, scope="connect",
                         owner_code=owner_code, path=path, access_ttl=access_ttl,
                         refresh_ttl=refresh_ttl, **kwargs)

    async def register(self, request):
        try:
            data = await request.json()
            uris = data.get("redirect_uris") if isinstance(data, dict) else None
            if not isinstance(uris, list) or not uris or any(u not in self.callbacks for u in uris):
                self.observations.record("registration_rejected", reason="invalid_request")
                return self.error("invalid_redirect_uri")
        except (ValueError, TypeError):
            return self.error("invalid_client_metadata")
        return await super().register(request)

def owner_credential(state_dir):
    path = Path(state_dir) / "owner.dpapi"
    provision_credential(path)
    return load_credential(path)

class ConnectVerifier(TokenVerifier):
    def __init__(self, authorization):
        super().__init__(base_url=authorization.origin, required_scopes=["connect"])
        self.authorization = authorization

    async def verify_token(self, token):
        value = await self.authorization.verify_token(token)
        if value is None:
            return None
        fields = value.model_dump()
        fields["claims"] = fields.get("claims") or {}
        return AccessToken(**fields)

    def get_routes(self, mcp_path=None):
        a = self.authorization
        return [
            Route("/.well-known/oauth-protected-resource/mcp", a.resource_metadata),
            Route("/.well-known/oauth-protected-resource", a.resource_metadata),
            Route("/.well-known/oauth-authorization-server", a.metadata),
            Route("/.well-known/openid-configuration", a.metadata),
            Route("/register", a.register, methods=["POST"]),
            Route("/authorize", a.authorize, methods=["GET"]),
            Route("/consent", a.consent, methods=["POST"]),
            Route("/token", a.token, methods=["POST"]),
            Route("/revoke", a.revoke, methods=["POST"]),
        ]
