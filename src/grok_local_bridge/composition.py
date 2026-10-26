"""Use FastMCP proxy composition rather than implementing MCP framing/routing."""
import os
from pathlib import Path
import httpx2
from fastmcp import FastMCP
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport
from fastmcp.server.providers.proxy import FastMCPProxy, ProxyClient
from .policy import CapabilityBoundary

def local_http_client(headers=None, timeout=None, auth=None, follow_redirects=False):
    # FastMCP passes follow_redirects=True, but local backends must not leave their origin.
    return httpx2.AsyncClient(headers=headers, timeout=timeout or 15, auth=auth,
                             trust_env=False, follow_redirects=False)

def build_server(config, *, auth=None, secret_store=None, observations=None):
    server = FastMCP("Grok Local Bridge", version="0.1.1a0", auth=auth,
                     mask_error_details=True, tasks=False,
                     instructions="Independent local MCP capabilities; only explicitly granted tools are available.")
    server.add_middleware(CapabilityBoundary(config, observations))
    for backend in config.backends:
        # Client.new() copies session state but shares its transport. A shared
        # keep_alive=False stdio transport closes concurrent callers' sessions.
        # Build the entire transport/client pair per request instead.
        def client_factory(backend=backend):
            return backend_client(backend, secret_store)
        proxy = FastMCPProxy(client_factory=client_factory, name=backend.name,
                             provider_error_strategy="raise", mask_error_details=True)
        server.mount(proxy, namespace=backend.name)
    return server


def backend_client(backend, secret_store=None):
    def secret(name):
        if secret_store is None: raise ValueError("backend secret store is required")
        return secret_store.load(name)
    if backend.transport == "stdio":
        transport = StdioTransport(backend.command, backend.args, cwd=backend.cwd,
                                   env={key:secret(ref) for key,ref in backend.env_secrets.items()}, keep_alive=False, log_file=Path(os.devnull))
    else:
        transport = StreamableHttpTransport(backend.url, httpx_client_factory=local_http_client,
                                            auth=secret(backend.bearer_secret) if backend.bearer_secret else None)
    return ProxyClient(transport, forward_incoming_headers=False,
                       sampling_handler=None, elicitation_handler=None,
                       roots=[], log_handler=None, progress_handler=None,
                       timeout=backend.timeout_seconds,
                       init_timeout=backend.timeout_seconds)
