---
name: grok-local-bridge
description: Help install, diagnose, and extend Grok Local Bridge on an authorized Windows computer, using approved local MCP backends and OAuth. Use for this project, not arbitrary remote execution or unrelated MCP configuration.
---

# Grok Local Bridge

Use the Bridge already supplied by this project. Read [README](README.md) for the supported install/manage commands, [architecture](docs/architecture.md) for transport choices, and [troubleshooting](docs/troubleshooting.md) when a failure occurs.

Before running scripts, establish whether the agent actually has an authorized execution channel to the target Windows PC. A cloud Skill import does not grant one. If unavailable, provide the local Companion commands from README for the user to execute and record local execution as unverified. WorkBuddy UI import remains unverified; do not bypass platform checks.

Use a separate persistent installation directory, not a Skill cache. Reuse an existing authorized installation without overwriting unknown state. Run install -CheckOnly, isolated install, doctor, demo (empty config only), then verify. Installation and local verify do not start public access or prove Grok acceptance. Start a Tunnel only within the user's authorized scope.

Add only user-designated trusted MCPs. Discovery executes their code. Use explicit namespaces, exact tool/resource grants, literal loopback HTTP or trusted stdio commands. Default to read-only. Write/delete/exec/hardware require corresponding explicit scope/flags and backend safety restrictions; labels are not a sandbox. Prefer a new backend manifest to changes in core OAuth.

Use local masked secret slots and the owner window. Never request credentials/codes in chat or put them into command arguments. OAuth Allow and account/domain decisions remain with the user. Preserve the existing grant/PKCE/callback checks.

For add/remove, wait for APPLIED and the expected runtime count, then refresh the client's full catalog and actually invoke the intended tools. Keep local, Inspector, public automated-client and real Grok results separate; demo business data is SYNTHETIC. Historical acceptance cannot prove a current connection.

On shutdown, stop only this installation's owned processes. Do not stop independent production services, change network policy, import private OAuth databases or use hardware to make a demo pass. See [security](docs/security.md) for remaining limits.
