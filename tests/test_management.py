"""Real Windows process/job tests, with an explicitly FAKE Tunnel executable."""
import asyncio
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
import httpx2
import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from conftest import ROOT,free_port,wait_port
from oauth_helpers import approve_flow
from grok_local_bridge.cli import initialize
from grok_local_bridge.io_utils import read_json,write_json
from grok_local_bridge.oauth import owner_credential
from grok_local_bridge.processes import manager_alive
from grok_local_bridge.secret_store import SecretStore


def cli(home,*args):
    result=subprocess.run([sys.executable,"-m","grok_local_bridge.cli","--home",str(home),*args],
                          cwd=ROOT,capture_output=True,text=True,timeout=45)
    assert result.returncode==0,result.stdout
    return json.loads(result.stdout)

async def until(predicate,timeout=45):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:
            value=predicate()
            if value: return value
        except (FileNotFoundError,KeyError,json.JSONDecodeError): pass
        await asyncio.sleep(.2)
    raise AssertionError("owned component condition timed out")


def test_dpapi_named_secret_and_reference_path_boundary(tmp_path):
    store=SecretStore(tmp_path/"secrets");secret="SYNTHETIC-backend-credential-for-local-test-only"
    store.save("backend-test",secret)
    assert store.load("backend-test")==secret
    assert secret.encode() not in store.slot_path("backend-test").read_bytes()
    with pytest.raises(Exception): store.load("../../not-owned")


def test_init_rejects_existing_unmanaged_state(tmp_path):
    write_json(tmp_path/"connect.json",{"private":"SYNTHETIC_EXISTING_WORK"})
    with pytest.raises(ValueError): initialize(tmp_path,None)
    assert read_json(tmp_path/"connect.json")=={"private":"SYNTHETIC_EXISTING_WORK"}


def test_cli_rejects_implicit_privilege_and_inline_secret(backends,tmp_path):
    config,_,_=backends;home=tmp_path/"home";initialize(home,sys.executable)
    spec=tmp_path/"backend.json";data=config.backends[0].model_dump()
    data.update(permissions=["read","write"])
    write_json(spec,data)
    result=subprocess.run([sys.executable,"-m","grok_local_bridge.cli","--home",str(home),"add","--spec",str(spec)],
                          cwd=ROOT,capture_output=True,text=True,timeout=20)
    assert result.returncode==1 and "explicit_permission_flag_required" in result.stdout
    assert read_json(home/"connect.json")["backends"]==[]
    data["permissions"]=["read"];data["args"]+=["--token=synthetic-never-actual"]
    write_json(spec,data)
    result=subprocess.run([sys.executable,"-m","grok_local_bridge.cli","--home",str(home),"add","--spec",str(spec)],
                          cwd=ROOT,capture_output=True,text=True,timeout=20)
    assert result.returncode==1 and "use_secret_slots" in result.stdout
    assert "synthetic-never-actual" not in result.stdout+result.stderr

@pytest.mark.parametrize("mode",["quick","named"])
async def test_managed_hot_add_recover_stop_keeps_tunnel_and_existing_token(backends,tmp_path,owned_processes,mode):
    config,http_backend,_=backends;home=tmp_path/"managed";initialize(home,sys.executable)
    # Python reads this file as its 'tunnel' script. No Cloudflare service is contacted.
    (home/"tunnel").write_text('import os,json,sys,time\nfrom pathlib import Path\nPath("fake-tunnel-evidence.json").write_text(json.dumps({"token_matches":os.environ.get("TUNNEL_TOKEN")=="SYNTHETIC_ONLY_TEST_VALUE","secret_in_args":"SYNTHETIC_ONLY_TEST_VALUE" in " ".join(sys.argv)}))\nprint("| https://synthetic-owned-fixture.trycloudflare.com |",flush=True)\ntime.sleep(300)\n',encoding="utf-8")
    port=free_port();settings=read_json(home/"settings.json");settings.update(port=port,max_minutes=5)
    if mode=="named":
        SecretStore(home/"secrets").save("new-tunnel","SYNTHETIC_ONLY_TEST_VALUE")
        settings.update(mode="named",origin="https://synthetic-owned-fixture.example.com",tunnel_secret="new-tunnel")
    write_json(home/"settings.json",settings)
    # Credentials must resolve from the manager home, not nested OAuth state.
    SecretStore(home/"secrets").save("backend-test","SYNTHETIC_ONLY_TEST_VALUE")
    config.backends[0].env_secrets={"GLB_SYNTHETIC_KEY":"backend-test"}
    write_json(home/"connect.json",config.model_dump())
    process=owned_processes([sys.executable,"-m","grok_local_bridge.supervisor","--home",str(home)])
    def ready():
        current=read_json(home/"status.json")
        assert current.get("phase")!="FAILED",current
        return current.get("phase")=="READY_LOCAL_AUTH_BOUNDARY"
    await until(ready,60)
    before=read_json(home/"status.json");assert manager_alive(home)
    tunnel_proof=read_json(home/"fake-tunnel-evidence.json")
    assert tunnel_proof=={"token_matches":mode=="named","secret_in_args":False}
    state=Path(before["state_dir"]);local=f"http://127.0.0.1:{port}"
    async with httpx2.AsyncClient(base_url=local,trust_env=False) as http:
        _,tokens=await approve_flow(http,before["mcp_url"],owner_credential(state))
    extra=config.backends[0].model_copy(deep=True);extra.name="third"
    spec=tmp_path/"third.json";write_json(spec,extra.model_dump())
    assert cli(home,"add","--spec",str(spec))["result"]=="SAVED_FOR_HOT_RELOAD"
    await until(lambda: read_json(state/"reload.status.json").get("backend_count")==3)
    async with Client(StreamableHttpTransport(local+"/mcp",auth=tokens["access_token"]),mode="legacy") as client:
        assert len(await client.list_tools())==3
        assert (await client.call_tool("third_get_hub_state")).data["provenance"]=="SYNTHETIC"
    cli(home,"recover")
    await until(lambda: read_json(home/"status.json").get("gateway_restarts")==1)
    await until(lambda: read_json(home/"status.json").get("phase")=="READY_LOCAL_AUTH_BOUNDARY")
    after=read_json(home/"status.json")
    assert after["origin"]==before["origin"] and after["tunnel_pid"]==before["tunnel_pid"]
    assert after["state_dir"]==before["state_dir"]
    assert after["gateway_pid"]!=before["gateway_pid"]
    async with Client(StreamableHttpTransport(local+"/mcp",auth=tokens["access_token"]),mode="legacy") as client:
        assert (await client.call_tool("hub_get_hub_state")).data["provenance"]=="SYNTHETIC"
    cli(home,"stop")
    await until(lambda: process.poll() is not None)
    assert not manager_alive(home)
    with socket.socket() as sock: assert sock.connect_ex(("127.0.0.1",port))!=0
    assert http_backend.poll() is None  # separately owned backend was never stopped
