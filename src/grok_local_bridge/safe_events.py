"""Structured events contain no request values, credentials, or exception text."""
import json
import time
from pathlib import Path

SAFE_FIELDS = {
    "accepted", "status", "expires_in", "refresh_present", "refreshed",
    "refresh_enabled", "code_issued", "callback_redirect", "registered_client",
    "code_challenge_present", "code_verifier_present", "client_secret_present",
    "authorization_header_present", "state_present", "pending_found",
    "pending_expired", "pending_identifier_present", "client_matches",
    "redirect_matches", "scope_matches", "pkce_challenge_restored",
    "pkce_method_s256", "mode", "decision", "reason", "outcome",
}
SAFE_ENUMS = {
    "allowed", "ok", "error", "denied", "rate_limited",
    "manual_link", "allow", "deny", "rotated", "invalid_grant", "refresh_replay",
    "invalid_form", "origin_mismatch", "invalid_decision", "pending_missing_or_pruned",
    "owner_pairing_required", "pending_binding_invalid", "pending_expired",
    "unsupported_grant_or_response_type", "invalid_request",
}
class SafeObservations:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.events = []
        self.tool_names = set()

    def record(self, event, **fields):
        clean = {}
        for key, value in fields.items():
            if key == "tool" and value in self.tool_names:
                clean[key] = value
                continue
            if key not in SAFE_FIELDS:
                continue
            if isinstance(value, (bool, int, float)) or value is None or (isinstance(value, str) and value in SAFE_ENUMS):
                clean[key] = value
        entry = {"time": int(time.time()), "event": event, **clean}
        self.events.append(entry)
        if len(self.events) > 2000:
            del self.events[:1000]
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=True) + "\n")

    def protocol(self, event, params, **fields):
        self.record(event, code_challenge_present=bool(params.get("code_challenge")),
                    code_verifier_present=bool(params.get("code_verifier")),
                    client_secret_present=bool(params.get("client_secret")), **fields)
