import json
import sys
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from conftest import free_port, wait_port

async def test_one_real_http_entry_and_no_credential_forwarding(backends, tmp_path, owned_processes):
    config, _, audit = backends
    path = tmp_path / "config.json"
    path.write_text(config.model_dump_json(), encoding="utf-8")
    port = free_port()
    code = ("import sys;from pathlib import Path;"
            "from grok_local_bridge.config import ConnectConfig;"
            "from grok_local_bridge.composition import build_server;"
            "import uvicorn;"
            "c=ConnectConfig.model_validate_json(Path(sys.argv[1]).read_text());"
            "s=build_server(c);"
            "uvicorn.run(s.http_app(path='/mcp',stateless_http=True,json_response=True),"
            "host='127.0.0.1',port=int(sys.argv[2]),access_log=False,log_level='critical')")
    process = owned_processes([sys.executable, "-c", code, str(path), str(port)])
    wait_port(process, port)
    transport = StreamableHttpTransport(f"http://127.0.0.1:{port}/mcp",
                                        headers={"Authorization": "Bearer synthetic-front-test-only"})
    async with Client(transport, mode="legacy") as client:
        assert {t.name for t in await client.list_tools()} == {"hub_get_hub_state", "probe_ping"}
        hub = (await client.call_tool("hub_get_hub_state")).data
        probe = (await client.call_tool("probe_ping")).data
        assert hub["pid"] != probe["pid"]
        assert probe["reply"] == "pong"
        assert probe["authorization_header_received"] is False
