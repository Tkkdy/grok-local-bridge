"""Explicit named secrets, encrypted for the current Windows user."""
from pathlib import Path
import re
from ._vendor.ar_dpapi import CredentialError, _dpapi
from .io_utils import atomic_bytes

SLOT=re.compile(r"[a-z][a-z0-9-]{0,62}")

class SecretStore:
    def __init__(self,path): self.path=Path(path)
    def slot_path(self,name):
        if not isinstance(name,str) or not SLOT.fullmatch(name):
            raise CredentialError("invalid secret reference")
        return self.path/(name+".dpapi")
    def save(self,name,value):
        data=value.encode("utf-8")
        if not data or len(data)>8192 or b"\x00" in data:
            raise CredentialError("invalid secret length")
        atomic_bytes(self.slot_path(name),_dpapi(data,protect=True))
    def load(self,name):
        try:
            data=self.slot_path(name).read_bytes()
            if not data or len(data)>16384: raise ValueError()
            return _dpapi(data,protect=False).decode("utf-8")
        except Exception:
            raise CredentialError("secret unavailable for this Windows user") from None
