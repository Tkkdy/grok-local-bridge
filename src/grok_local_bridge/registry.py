"""Atomic provider replacement; the public HTTP/OAuth application stays alive."""
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError, ResourceError
from fastmcp.server.providers import Provider, FastMCPProvider
from .composition import build_server
from .policy import CapabilityBoundary

class ReloadableProvider(Provider):
    def __init__(self,config,secret_store=None,observations=None):
        super().__init__();self.secret_store=secret_store;self.observations=observations;self.blocked=False
        self.replace(config)
    def replace(self,config):
        delegate=FastMCPProvider(build_server(config,secret_store=self.secret_store,observations=self.observations))
        boundary=CapabilityBoundary(config)
        self.snapshot=(delegate,boundary)
        self.blocked=False
    def block(self): self.blocked=True
    def current(self):
        if self.blocked: raise ToolError("Local configuration is invalid; tools are closed")
        return self.snapshot
    async def _list_tools(self):
        delegate,_=self.current()
        return await delegate.list_tools()
    async def _get_tool(self,name,version=None):
        delegate,boundary=self.current()
        if name not in boundary.tools: return None
        return await delegate.get_tool(name,version)
    async def _list_resources(self):
        delegate,_=self.current()
        return await delegate.list_resources()
    async def _get_resource(self,uri,version=None):
        delegate,boundary=self.current()
        if str(uri) not in boundary.resources: return None
        return await delegate.get_resource(uri,version)
    async def _list_resource_templates(self): return []
    async def _list_prompts(self): return []


def build_reloadable_server(config,*,auth=None,secret_store=None,observations=None):
    registry=ReloadableProvider(config,secret_store,observations)
    server=FastMCP("Grok Local Bridge",version="0.1.0a0",auth=auth,tasks=False,
                   mask_error_details=True,providers=[registry])
    server.provider_error_strategy="raise"
    return server,registry
