"""Enforce grants for discovery AND direct access before proxy dispatch."""
import time
from collections import defaultdict, deque
from fastmcp.exceptions import ToolError, ResourceError
from fastmcp.server.middleware import Middleware

def namespaced_uri(namespace: str, uri: str) -> str:
    scheme, rest = uri.split("://", 1)
    return f"{scheme}://{namespace}/{rest}"

class CapabilityBoundary(Middleware):
    def __init__(self, config, observations=None):
        self.tools = {f"{b.name}_{t.name}" for b in config.backends
                      for t in b.tools if t.permission in b.permissions}
        self.observations = observations
        self.limit = config.tool_calls_per_minute
        self.windows = defaultdict(deque)
        if observations is not None:
            observations.tool_names.update(self.tools)
        self.resources = {namespaced_uri(b.name, r) for b in config.backends if "read" in b.permissions for r in b.resources}

    async def on_list_tools(self, context, call_next):
        tools = [t for t in await call_next(context) if t.name in self.tools]
        if {t.name for t in tools} != self.tools:
            # Never let a client cache a silently truncated authorized catalog.
            raise ToolError("Authorized tool catalog is incomplete; retry or diagnose backends")
        return tools

    def audit(self, outcome, name=None):
        if self.observations is not None:
            self.observations.record("tool_call", outcome=outcome, **({"tool": name} if name in self.tools else {}))

    async def on_call_tool(self, context, call_next):
        name = context.message.name
        if name not in self.tools:
            self.audit("denied")
            raise ToolError("Tool is not authorized")
        now = time.monotonic()
        window = self.windows[name]
        while window and window[0] <= now - 60:
            window.popleft()
        if len(window) >= self.limit:
            self.audit("rate_limited", name)
            raise ToolError("Tool rate limit reached; retry after the minute window")
        window.append(now)
        self.audit("allowed", name)  # If the pre-call audit cannot persist, do not dispatch.
        try:
            result = await call_next(context)
        except Exception:
            self.audit("error", name)
            raise
        try:
            self.audit("ok", name)
        except OSError:
            raise ToolError("Tool completed but audit recording failed; do not automatically retry") from None
        return result

    async def on_list_resources(self, context, call_next):
        if not self.resources:
            return []
        return [r for r in await call_next(context) if str(r.uri) in self.resources]

    async def on_read_resource(self, context, call_next):
        if str(context.message.uri) not in self.resources:
            raise ResourceError("Resource is not authorized")
        return await call_next(context)

    async def on_list_resource_templates(self, context, call_next):
        return []

    async def on_list_prompts(self, context, call_next):
        return []

    async def on_get_prompt(self, context, call_next):
        raise ToolError("Prompts are not enabled in V0.1")
