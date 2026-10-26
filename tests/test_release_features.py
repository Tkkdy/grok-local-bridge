import json
import subprocess
import sys
import pytest
from fastmcp import Client
from grok_local_bridge.composition import build_server
from grok_local_bridge.safe_events import SafeObservations
from grok_local_bridge.cli import initialize
from grok_local_bridge.io_utils import write_json, read_json

async def test_per_tool_rate_limit_and_safe_audit(backends, tmp_path):
    config, _, backend_audit = backends
    config.tool_calls_per_minute = 1
    observations = SafeObservations(tmp_path / "safe-events.jsonl")
    async with Client(build_server(config,observations=observations),mode="legacy") as client:
        assert (await client.call_tool("hub_get_hub_state")).data["provenance"] == "SYNTHETIC"
        with pytest.raises(Exception): await client.call_tool("hub_get_hub_state")
        assert (await client.call_tool("probe_ping")).data["reply"] == "pong"
        with pytest.raises(Exception): await client.call_tool("hub_forbidden_delete")
    events = observations.events
    assert any(e.get("outcome")=="rate_limited" for e in events)
    assert any(e.get("outcome")=="denied" for e in events)
    assert all(set(e) <= {"time","event","tool","outcome"} for e in events)
    assert {e["tool"] for e in events if "tool" in e} == {"hub_get_hub_state","probe_ping"}
    assert len(backend_audit.read_text().splitlines()) == 2

async def test_failed_pre_call_audit_prevents_backend_dispatch(backends, monkeypatch):
    config, _, backend_audit = backends
    observations = SafeObservations()
    def unavailable(*args, **kwargs): raise OSError("SYNTHETIC audit disk unavailable")
    monkeypatch.setattr(observations,"record",unavailable)
    async with Client(build_server(config,observations=observations),mode="legacy") as client:
        with pytest.raises(Exception): await client.call_tool("hub_get_hub_state")
    assert not backend_audit.exists()

def test_remove_cli_preserves_other_backends_and_rejects_unknown(backends,tmp_path):
    config,_,_=backends
    home=tmp_path/"owned";initialize(home,None);write_json(home/"connect.json",config.model_dump())
    command=[sys.executable,"-m","grok_local_bridge.cli","--home",str(home),"remove","--name","hub"]
    result=subprocess.run(command,capture_output=True,text=True,timeout=20)
    assert result.returncode==0 and json.loads(result.stdout)["removed_backend"]=="hub"
    assert [b["name"] for b in read_json(home/"connect.json")["backends"]]==["probe"]
    again=subprocess.run(command,capture_output=True,text=True,timeout=20)
    assert again.returncode!=0
    assert [b["name"] for b in read_json(home/"connect.json")["backends"]]==["probe"]


def test_release_scanner_reports_only_categories_for_private_artifacts(tmp_path):
    import importlib.util
    from pathlib import Path
    scanner_path=Path(__file__).resolve().parents[1]/"scripts/release_check.py"
    spec=importlib.util.spec_from_file_location("release_check",scanner_path)
    scanner=importlib.util.module_from_spec(spec);spec.loader.exec_module(scanner)
    synthetic_credential="gh"+"p_"+"z"*36
    (tmp_path/"note.md").write_text(synthetic_credential,encoding="utf-8")
    (tmp_path/".env").write_text("SYNTHETIC_ONLY",encoding="utf-8")
    findings=scanner.scan(tmp_path,[Path("note.md"),Path(".env")])
    assert {f["kind"] for f in findings}=={"github_credential","forbidden_artifact"}
    assert synthetic_credential not in json.dumps(findings)


async def test_backend_error_result_is_audited_as_error(monkeypatch):
    from fastmcp import FastMCP
    from fastmcp.tools import ToolResult
    from fastmcp.server.providers.proxy import ProxyClient
    from grok_local_bridge.config import ConnectConfig
    import grok_local_bridge.composition as composition

    backend = FastMCP("SYNTHETIC backend refusal")

    @backend.tool
    def read_guarded() -> ToolResult:
        return ToolResult(content="SYNTHETIC backend refused this read", is_error=True)

    config = ConnectConfig.model_validate({"backends": [{
        "name": "guard", "transport": "stdio", "command": sys.executable,
        "tools": [{"name": "read_guarded"}]
    }]})
    monkeypatch.setattr(composition, "backend_client", lambda *args: ProxyClient(backend))
    observations = SafeObservations()
    async with Client(composition.build_server(config, observations=observations), mode="legacy") as client:
        result = await client.call_tool("guard_read_guarded", raise_on_error=False)
        assert result.is_error
    outcomes = [e["outcome"] for e in observations.events if e.get("tool") == "guard_read_guarded"]
    assert outcomes == ["allowed", "error"]
    assert "SYNTHETIC backend refused this read" not in json.dumps(observations.events)
