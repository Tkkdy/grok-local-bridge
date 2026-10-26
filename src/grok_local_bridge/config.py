"""Explicit capability grants; configuration never contains credentials."""
from __future__ import annotations
import ipaddress
import re
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, model_validator

Permission = Literal["read", "write", "delete", "exec", "hardware"]

class ToolGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,100}$")
    permission: Permission = "read"

class Backend(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9]{0,23}$")
    transport: Literal["stdio", "http"]
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    cwd: str | None = None
    url: str | None = None
    tools: list[ToolGrant] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)
    permissions: list[Permission] = Field(default_factory=lambda: ["read"])
    env_secrets: dict[str, str] = Field(default_factory=dict)
    bearer_secret: str | None = None
    timeout_seconds: int = Field(default=15, ge=2, le=120)

    @model_validator(mode="after")
    def boundary(self):
        if len({t.name for t in self.tools}) != len(self.tools):
            raise ValueError("duplicate tool grant")
        if any(t.permission not in self.permissions for t in self.tools):
            raise ValueError("tool requires an explicit corresponding permission")
        refs = list(self.env_secrets.values()) + ([self.bearer_secret] if self.bearer_secret else [])
        if any(not re.fullmatch(r"[a-z][a-z0-9-]{0,62}", ref) for ref in refs):
            raise ValueError("invalid secret reference")
        reserved = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "PYTHONPATH", "PYTHONHOME", "NODE_OPTIONS"}
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,99}", key) or key.upper() in reserved for key in self.env_secrets):
            raise ValueError("invalid credential environment name")
        if self.transport == "stdio":
            if self.bearer_secret:
                raise ValueError("stdio credentials use explicit environment secret references")
            if not self.command or self.url:
                raise ValueError("stdio requires command and forbids url")
        else:
            if self.command or self.args or self.cwd or self.env_secrets or not self.url:
                raise ValueError("http requires only url")
            u = urlsplit(self.url)
            if u.scheme != "http" or u.username or u.password or u.query or u.fragment:
                raise ValueError("local HTTP backend must have no embedded credentials or query")
            try:
                loopback = ipaddress.ip_address(u.hostname or "").is_loopback
            except ValueError:
                loopback = False
            if not loopback:
                raise ValueError("V0.1 HTTP backends require literal loopback address")
        if self.resources and "read" not in self.permissions:
            raise ValueError("resources require read permission")
        if any("{" in r or "}" in r or not re.match(r"^[a-zA-Z][\w+.-]*://", r) for r in self.resources):
            raise ValueError("only explicit resource URIs are supported")
        return self

class ConnectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    backends: list[Backend] = Field(default_factory=list)
    tool_calls_per_minute: int = Field(default=60, ge=1, le=600)

    @model_validator(mode="after")
    def unique(self):
        if len({b.name for b in self.backends}) != len(self.backends):
            raise ValueError("duplicate backend namespace")
        return self
