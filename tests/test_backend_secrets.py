import sys
from pathlib import Path
import pytest
from fastmcp import Client
from conftest import FIXTURE,free_port,wait_port
from grok_local_bridge.config import ConnectConfig
from grok_local_bridge.composition import build_server
from grok_local_bridge.secret_store import SecretStore

async def test_stdio_uses_only_explicit_encrypted_secret_refs(tmp_path,monkeypatch):
    monkeypatch.setenv("GLB_UNRELATED_SYNTHETIC_SECRET","SYNTHETIC_DO_NOT_FORWARD")
    store=SecretStore(tmp_path/"secrets");store.save("backend","SYNTHETIC_ONLY_TEST_VALUE")
    config=ConnectConfig.model_validate({"backends":[{"name":"local","transport":"stdio","command":sys.executable,
        "args":[str(FIXTURE),"--kind","probe","--audit",str(tmp_path/"events.jsonl"),"--verify-secret-fixture"],
        "env_secrets":{"GLB_SYNTHETIC_KEY":"backend"},"tools":[{"name":"ping"}]}]})
    async with Client(build_server(config,secret_store=store),mode="legacy") as client:
        result=(await client.call_tool("local_ping")).data
    assert result["configured_env_matches"] is True
    assert result["unrelated_env_present"] is False

async def test_http_uses_backend_dpapi_bearer_slot(tmp_path,owned_processes):
    store=SecretStore(tmp_path/"secrets");store.save("backend","SYNTHETIC_ONLY_TEST_VALUE")
    port=free_port();process=owned_processes([sys.executable,str(FIXTURE),"--kind","probe","--port",str(port),
        "--audit",str(tmp_path/"events.jsonl"),"--verify-secret-fixture"]);wait_port(process,port)
    config=ConnectConfig.model_validate({"backends":[{"name":"local","transport":"http","url":f"http://127.0.0.1:{port}/mcp",
        "bearer_secret":"backend","tools":[{"name":"ping"}]}]})
    async with Client(build_server(config,secret_store=store),mode="legacy") as client:
        assert (await client.call_tool("local_ping")).data["backend_auth_matches"] is True


def test_resource_read_requires_read_permission():
    with pytest.raises(ValueError):
        ConnectConfig.model_validate({"backends":[{"name":"local","transport":"stdio","command":"synthetic",
            "permissions":[],"resources":["fixture://private"]}]})
