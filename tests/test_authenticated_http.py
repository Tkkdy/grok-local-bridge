import sys
import pytest
import httpx2
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from conftest import free_port, wait_port
from oauth_helpers import approve_flow
from grok_local_bridge.oauth import owner_credential

async def test_real_http_oauth_two_backends_and_no_token_forward(backends,tmp_path,owned_processes):
    config, _, audit = backends
    cfg = tmp_path/"config.json"
    cfg.write_text(config.model_dump_json(),encoding="utf-8")
    state = tmp_path/"state"
    owner = owner_credential(state)
    port = free_port()
    origin = f"http://127.0.0.1:{port}"
    process = owned_processes([sys.executable,"-m","grok_local_bridge.runtime","--config",str(cfg),
                               "--state",str(state),"--origin",origin,"--port",str(port)])
    wait_port(process,port)
    async with httpx2.AsyncClient(base_url=origin,trust_env=False) as http:
        assert (await http.post("/mcp",json={"jsonrpc":"2.0","id":1,"method":"tools/list"})).status_code == 401
        assert not audit.exists()
        _, tokens = await approve_flow(http,origin+"/mcp",owner)
    transport = StreamableHttpTransport(origin+"/mcp",auth=tokens["access_token"])
    async with Client(transport,mode="legacy") as client:
        assert {t.name for t in await client.list_tools()} == {"hub_get_hub_state","probe_ping"}
        hub = (await client.call_tool("hub_get_hub_state")).data
        probe = (await client.call_tool("probe_ping")).data
        assert hub["pid"] != probe["pid"]
        assert probe["authorization_header_received"] is False
        with pytest.raises(Exception):
            await client.call_tool("probe_forbidden_delete")
        assert await client.list_resources() == []
    logs=(state/"events.jsonl").read_text()
    assert tokens["access_token"] not in logs
    assert tokens["refresh_token"] not in logs
    assert owner not in logs
