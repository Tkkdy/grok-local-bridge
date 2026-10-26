import asyncio
import json
import sys
import time
import httpx2
import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from conftest import free_port, wait_port
from oauth_helpers import approve_flow
from grok_local_bridge.config import Backend, ToolGrant
from grok_local_bridge.registry import build_reloadable_server
from grok_local_bridge.oauth import owner_credential
from grok_local_bridge.io_utils import write_json

async def test_add_remove_and_invalid_config_deny_old_tools(backends):
    config,_,_=backends
    server,registry=build_reloadable_server(config)
    async with Client(server,mode="legacy") as client:
        assert {t.name for t in await client.list_tools()}=={"hub_get_hub_state","probe_ping"}
        expanded=config.model_copy(deep=True)
        extra=config.backends[0].model_copy(deep=True);extra.name="extra";extra.tools=[ToolGrant(name="ping")]
        extra=Backend.model_validate(extra.model_dump())
        expanded.backends.append(extra)
        registry.replace(expanded)
        assert {t.name for t in await client.list_tools()}=={"hub_get_hub_state","probe_ping","extra_ping"}
        assert (await client.call_tool("extra_ping")).data["reply"]=="pong"
        reduced=config.model_copy(deep=True);reduced.backends=reduced.backends[1:]
        registry.replace(reduced)
        with pytest.raises(Exception): await client.call_tool("hub_get_hub_state")
        assert (await client.call_tool("probe_ping")).data["reply"]=="pong"
        registry.block()
        with pytest.raises(Exception): await client.call_tool("probe_ping")
        with pytest.raises(Exception): await client.list_tools()
        registry.replace(config)
        assert len(await client.list_tools())==2

async def test_real_http_hot_add_keeps_process_origin_and_existing_oauth(backends,tmp_path,owned_processes):
    config,_,_=backends
    cfg=tmp_path/"connect.json";write_json(cfg,config.model_dump())
    state=tmp_path/"state";owner=owner_credential(state)
    port=free_port();origin=f"http://127.0.0.1:{port}"
    process=owned_processes([sys.executable,"-m","grok_local_bridge.runtime","--config",str(cfg),
                             "--state",str(state),"--origin",origin,"--port",str(port)])
    wait_port(process,port)
    async with httpx2.AsyncClient(base_url=origin,trust_env=False) as http:
        _,tokens=await approve_flow(http,origin+"/mcp",owner)
    async with Client(StreamableHttpTransport(origin+"/mcp",auth=tokens["access_token"]),mode="legacy") as client:
        assert len(await client.list_tools())==2
        before=json.loads((state/"reload.status.json").read_text())
        expanded=config.model_copy(deep=True)
        extra=config.backends[0].model_copy(deep=True);extra.name="third"
        expanded.backends.append(extra)
        write_json(cfg,expanded.model_dump())
        for _ in range(80):
            after=json.loads((state/"reload.status.json").read_text())
            if after["generation"]>before["generation"]: break
            await asyncio.sleep(.1)
        assert after["result"]=="APPLIED" and after["generation"]>before["generation"]
        assert (after["pid"],after["started_at"])==(before["pid"],before["started_at"])
        assert process.poll() is None
        assert {t.name for t in await client.list_tools()}=={"hub_get_hub_state","probe_ping","third_get_hub_state"}
        assert (await client.call_tool("third_get_hub_state")).data["provenance"]=="SYNTHETIC"
        # Revocation is enforced over the existing authenticated connection.
        write_json(cfg,config.model_dump())
        for _ in range(80):
            removed=json.loads((state/"reload.status.json").read_text())
            if removed.get("backend_count")==2 and removed["generation"]>after["generation"]: break
            await asyncio.sleep(.1)
        assert removed["result"]=="APPLIED"
        assert {t.name for t in await client.list_tools()}=={"hub_get_hub_state","probe_ping"}
        with pytest.raises(Exception): await client.call_tool("third_get_hub_state")
        assert (await client.call_tool("probe_ping")).data["reply"]=="pong"
        cfg.write_text('{"invalid":true}',encoding="utf-8")
        for _ in range(50):
            if json.loads((state/"reload.status.json").read_text())["result"]!="APPLIED": break
            await asyncio.sleep(.1)
        with pytest.raises(Exception): await client.call_tool("hub_get_hub_state")
        write_json(cfg,config.model_dump())
        for _ in range(50):
            if json.loads((state/"reload.status.json").read_text())["result"]=="APPLIED": break
            await asyncio.sleep(.1)
        assert len(await client.list_tools())==2
