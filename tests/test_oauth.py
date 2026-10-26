import html
import json
import secrets
import re
import pytest
import httpx2
from urllib.parse import parse_qs, urlsplit
from grok_local_bridge.app import create_application
from grok_local_bridge.config import ConnectConfig
from grok_local_bridge.oauth import ConnectAuthorizationServer
from grok_local_bridge.safe_events import SafeObservations
from oauth_helpers import begin_flow, approve_flow, CALLBACK

ORIGIN = "http://127.0.0.1:43180"

@pytest.fixture
def oauth_app(tmp_path):
    owner = secrets.token_urlsafe(32)
    events = SafeObservations()
    app, authorization, _ = create_application(ConnectConfig(), origin=ORIGIN, port=43180,
                                              state_dir=tmp_path, owner_code=owner, observations=events)
    return app, authorization, owner, events

async def test_no_auth_cannot_reach_any_mcp_method(oauth_app):
    app, _, _, _ = oauth_app
    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app), base_url=ORIGIN) as client:
        for method in ("initialize", "tools/list", "tools/call", "resources/list", "resources/read", "prompts/list"):
            response = await client.post("/mcp", json={"jsonrpc":"2.0","id":1,"method":method})
            assert response.status_code == 401
            assert 'resource_metadata="' in response.headers["www-authenticate"]
            assert "invalid_token" not in response.headers["www-authenticate"]
        assert (await client.get("/mcp")).status_code == 401
        response = await client.post("/mcp", headers={"Authorization": "Bearer invalid"})
        assert response.status_code == 401
        assert "invalid_token" in response.headers["www-authenticate"]
        response = await client.post("/mcp", headers=[("Authorization","Bearer invalid"),("Authorization","Bearer invalid")])
        assert response.status_code == 401
        assert (await client.get("/admin")).status_code == 404
        assert (await client.get("/.well-known/oauth-protected-resource/mcp")).json()["resource"] == ORIGIN+"/mcp"

async def test_dcr_exact_callbacks_and_owner_required(oauth_app):
    app, auth, owner, events = oauth_app
    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app), base_url=ORIGIN) as client:
        response = await client.post("/register", json={"redirect_uris":["https://attacker.invalid/callback"]})
        assert response.status_code == 400
        client_id, verifier, params, ticket = await begin_flow(client, ORIGIN+"/mcp")
        response = await client.post("/consent", data={"ticket":ticket,"decision":"allow"})
        assert response.status_code == 403
        assert not auth.codes
        response = await client.get("/authorize", params={**params,"resource":"https://other.invalid/mcp"})
        assert response.status_code == 400
        response = await client.get("/authorize", params={**params,"scope":"write"})
        assert response.status_code == 400
        response = await client.post("/consent", headers={"Origin":"https://attacker.invalid"},
                                     data={"ticket":ticket,"decision":"allow","owner_code":owner})
        assert response.status_code == 400
        assert not auth.codes

async def test_pkce_binding_single_use_and_safe_events(oauth_app):
    app, auth, owner, events = oauth_app
    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app), base_url=ORIGIN) as client:
        client_id, verifier, params, ticket = await begin_flow(client, ORIGIN+"/mcp")
        response = await client.post("/consent", data={"ticket":ticket,"decision":"allow","owner_code":owner})
        assert response.status_code == 303
        code = parse_qs(urlsplit(response.headers["location"]).query)["code"][0]
        body = {"grant_type":"authorization_code","client_id":client_id,"code":code,
                "redirect_uri":CALLBACK,"code_verifier":verifier,"resource":ORIGIN+"/mcp"}
        assert (await client.post("/token",data={**body,"code_verifier":"wrong"*16})).status_code == 400
        assert (await client.post("/token",data={**body,"resource":"https://other.invalid/mcp"})).status_code == 400
        response = await client.post("/token", data=body)
        assert response.status_code == 200
        token = response.json()["access_token"]
        assert await auth.verify_token(token)
        assert (await client.post("/token",data=body)).status_code == 400
        assert (await client.post("/consent",data={"ticket":ticket,"decision":"allow","owner_code":owner})).status_code == 400
        text = json.dumps(events.events)
        assert all(value not in text for value in (token, owner, code, verifier, ticket))

async def test_refresh_persists_then_replay_revokes_family(oauth_app, tmp_path):
    app, auth, owner, events = oauth_app
    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app), base_url=ORIGIN) as client:
        client_id, pair = await approve_flow(client, ORIGIN+"/mcp", owner)
    restarted = ConnectAuthorizationServer(ORIGIN, SafeObservations(), owner_code=owner,
                                            path=tmp_path/"oauth.sqlite3")
    assert await restarted.verify_token(pair["access_token"])
    app2, auth2, _ = create_application(ConnectConfig(), origin=ORIGIN, port=43180,
                                       state_dir=tmp_path, owner_code=owner)
    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app2), base_url=ORIGIN) as client:
        body = {"grant_type":"refresh_token","client_id":client_id,
                "refresh_token":pair["refresh_token"],"resource":ORIGIN+"/mcp"}
        response = await client.post("/token", data=body)
        assert response.status_code == 200
        rotated = response.json()
        assert await auth2.verify_token(rotated["access_token"])
        assert (await client.post("/token",data=body)).status_code == 400
        assert await auth2.verify_token(rotated["access_token"]) is None

async def test_manual_callback_and_expired_consent(oauth_app):
    app, auth, owner, events = oauth_app
    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app), base_url=ORIGIN) as client:
        callback = "https://www.cursor.com/agents/mcp/oauth/callback"
        _, _, _, ticket = await begin_flow(client, ORIGIN+"/mcp", callback=callback)
        response = await client.post("/consent",data={"ticket":ticket,"decision":"allow","owner_code":owner})
        assert response.status_code == 200
        assert "Continue to GrokBot" in response.text
        assert response.headers["referrer-policy"] == "no-referrer"
        target = html.unescape(re.search(r'href="([^"]+)"',response.text).group(1))
        assert target.startswith(callback+"?")
        assert "code" in parse_qs(urlsplit(target).query)
        _, _, _, ticket = await begin_flow(client, ORIGIN+"/mcp")
        auth.pending[ticket]["expires"] = 0
        response = await client.post("/consent",data={"ticket":ticket,"decision":"allow","owner_code":owner})
        assert response.status_code == 303
        assert parse_qs(urlsplit(response.headers["location"]).query).get("error") == ["access_denied"]

def test_event_sink_drops_untrusted_values():
    events = SafeObservations()
    events.record("synthetic", reason={"secret":"never write this"}, token="never write this",
                  accepted=True, mode="attacker-controlled")
    assert events.events[0] == {"time":events.events[0]["time"],"event":"synthetic","accepted":True}


async def test_unauthenticated_requests_are_rate_limited(tmp_path):
    import httpx2
    from grok_local_bridge.app import create_application
    from grok_local_bridge.config import ConnectConfig
    app, _, _ = create_application(ConnectConfig(), origin="http://127.0.0.1:9911", port=9911,
                                   state_dir=tmp_path, owner_code="synthetic-owner-rate-limit-credential-only")
    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="http://127.0.0.1:9911") as http:
        for _ in range(180):
            assert (await http.get("/mcp")).status_code==401
        assert (await http.get("/mcp")).status_code==429
