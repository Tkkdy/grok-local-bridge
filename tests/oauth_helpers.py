"""Synthetic OAuth client. All credentials stay in memory, never printed."""
import base64
import hashlib
import re
import secrets
from urllib.parse import parse_qs, urlsplit
CALLBACK = "http://localhost:6274/oauth/callback"

async def begin_flow(client, resource, *, callback=CALLBACK):
    response = await client.post("/register", json={
        "redirect_uris": [callback], "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"], "scope": "connect"})
    assert response.status_code == 201
    client_id = response.json()["client_id"]
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    params = {"client_id": client_id, "redirect_uri": callback, "response_type": "code",
              "code_challenge": challenge, "code_challenge_method": "S256",
              "scope": "connect", "resource": resource, "state": secrets.token_hex(12)}
    response = await client.get("/authorize", params=params)
    assert response.status_code == 200
    ticket = re.search(r'name="ticket" value="([^"]+)"', response.text).group(1)
    return client_id, verifier, params, ticket

async def approve_flow(client, resource, owner, *, callback=CALLBACK):
    client_id, verifier, params, ticket = await begin_flow(client, resource, callback=callback)
    response = await client.post("/consent", data={
        "ticket": ticket, "decision": "allow", "owner_code": owner})
    assert response.status_code == 303
    code = parse_qs(urlsplit(response.headers["location"]).query)["code"][0]
    response = await client.post("/token", data={
        "grant_type": "authorization_code", "client_id": client_id, "code": code,
        "redirect_uri": callback, "code_verifier": verifier, "resource": resource})
    assert response.status_code == 200
    return client_id, response.json()
