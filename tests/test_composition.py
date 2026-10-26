import json
import os
import pytest
from fastmcp import Client
from grok_local_bridge.composition import build_server
from grok_local_bridge.config import Backend

async def test_two_independent_transports_and_closed_grants(backends):
    config, http_process, audit = backends
    server = build_server(config)
    async with Client(server, mode="legacy") as client:
        names = {t.name for t in await client.list_tools()}
        assert names == {"hub_get_hub_state", "probe_ping"}
        hub = (await client.call_tool("hub_get_hub_state")).data
        probe = (await client.call_tool("probe_ping")).data
        assert hub["provenance"] == probe["provenance"] == "SYNTHETIC"
        assert probe["reply"] == "pong"
        assert hub["pid"] != probe["pid"]  # Windows venv redirector has a separate launcher PID
        assert hub["pid"] != os.getpid()
        assert probe["pid"] != os.getpid()
        assert not probe["authorization_header_received"]
        for name in ("hub_forbidden_delete", "probe_forbidden_delete", "ping"):
            with pytest.raises(Exception):
                await client.call_tool(name)
        assert await client.list_resources() == []
        assert await client.list_resource_templates() == []
        assert await client.list_prompts() == []
        with pytest.raises(Exception):
            await client.read_resource("fixture://probe/private")
        with pytest.raises(Exception):
            await client.get_prompt("probe_private_prompt")
    events = [json.loads(x) for x in audit.read_text().splitlines()]
    assert {x["tool"] for x in events} == {"get_hub_state", "ping"}

async def test_backend_failure_does_not_block_other_backend(backends):
    config, process, audit = backends
    server = build_server(config)
    async with Client(server, mode="legacy") as client:
        assert (await client.call_tool("probe_ping")).data["reply"] == "pong"
        process.terminate()
        process.wait(timeout=10)
        with pytest.raises(Exception):
            await client.call_tool("probe_ping")
        with pytest.raises(Exception):
            await client.list_tools()
        assert (await client.call_tool("hub_get_hub_state")).data["provenance"] == "SYNTHETIC"

@pytest.mark.parametrize("url", ["http://localhost:80/mcp", "http://192.168.1.2/mcp",
                                "https://127.0.0.1/mcp", "http://u:p@127.0.0.1/mcp",
                                "http://127.0.0.1/mcp?token=not-a-real-token"])
def test_reject_unsafe_backend_targets(url):
    with pytest.raises(ValueError):
        Backend(name="local", transport="http", url=url)

def test_privileged_tool_requires_corresponding_permission():
    with pytest.raises(ValueError):
        Backend(name="local", transport="stdio", command="synthetic",
                tools=[{"name": "delete", "permission": "delete"}])


async def test_explicit_resource_grant_stays_with_its_backend(backends):
    config, _, audit = backends
    config = config.model_copy(deep=True)
    config.backends[1].resources = ["fixture://private"]
    async with Client(build_server(config), mode="legacy") as client:
        resources = await client.list_resources()
        assert {str(r.uri) for r in resources} == {"fixture://probe/private"}
        content = await client.read_resource("fixture://probe/private")
        assert any(c.text == "SYNTHETIC_PRIVATE_RESOURCE" for c in content)
        for uri in ("fixture://hub/private", "fixture://private"):
            with pytest.raises(Exception):
                await client.read_resource(uri)
    events = [json.loads(x) for x in audit.read_text().splitlines()]
    assert [(e["backend"], e["tool"]) for e in events] == [("probe", "private_resource")]


async def test_concurrent_initial_catalogs_include_every_granted_backend(backends):
    import asyncio
    config, _, _ = backends
    server = build_server(config)
    async def initial_catalog():
        async with Client(server, mode="legacy") as client:
            return {tool.name for tool in await client.list_tools()}
    catalogs = await asyncio.gather(*(initial_catalog() for _ in range(3)))
    assert all(names == {"hub_get_hub_state", "probe_ping"} for names in catalogs)


async def test_concurrent_backend_calls_preserve_both_audit_records(backends):
    import asyncio
    import json
    from fastmcp import Client
    from grok_local_bridge.composition import build_server
    config,_,audit=backends
    async with Client(build_server(config),mode="legacy") as client:
        left,right=await asyncio.gather(client.call_tool("hub_get_hub_state"),client.call_tool("probe_ping"))
    records=[json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    assert {(r["tool"],r["pid"]) for r in records}=={
        ("get_hub_state",left.data["pid"]),("ping",right.data["pid"])}
