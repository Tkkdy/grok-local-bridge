# Grok Local Bridge v0.1.1-alpha — Release notes

Experimental **Pre-release**, 2026-10-26. Package version: `0.1.1a0`. The previous `v0.1.0-alpha` tag, source and assets are preserved.

## Changes from v0.1.0-alpha

- Detect missing/broken Tcl/Tk before installation creates its target. doctor reports owner-window component readiness, not successful GUI authorization.
- Record returned backend MCP errors as audit errors instead of successes; preserve error payloads and all existing OAuth/grant enforcement.
- Include examples in independent installations so the optional Filesystem manifest remains available.
- Provide a short Windows beta guide and commit-identified source archives.

Filesystem MCP 2.0.1 remains an **optional recipe**: Node >=24, only text reading and filename search, a user-approved directory, upstream execution-layer path checks and Bridge operation grants. The default installer does not install Node/npm/Filesystem or add Shell/hardware tools. Backend code runs with the Windows user's privileges; this is not an OS sandbox.

## Validation and external beta

The Release links the Windows CI run for its exact source commit. Its ZIP, RELEASE_MANIFEST.json and SHA256SUMS.txt refer to that commit; the manifest includes the source tree. PR-head checks are not substituted for a changed merge commit's artifacts.

The original v0.1.0-alpha real GrokBot OAuth/discovery/two-synthetic-call acceptance and local Filesystem boundary tests keep their original scope. No historical real-client experiment or public Tunnel was repeated for this release. Missing-Tk and audit regression failures remain recorded in [validation history](validation.md).

Clean Windows first installation, actual winget bootstrap and first-use authorization GUI remain **EXTERNAL BETA / NOT VERIFIED**. OS reboot recovery, long-term availability, stable public origins, all filesystem race/link attacks, WorkBuddy import and per-client ACL are not claimed.

## Downloads and installation

Download the three assets from [v0.1.1-alpha](https://github.com/Tkkdy/grok-local-bridge/releases/tag/v0.1.1-alpha):

- `grok-local-bridge-v0.1.1-alpha.zip`: reviewed source only.
- `RELEASE_MANIFEST.json`: version, source commit/tree, ZIP SHA-256 and member count.
- `SHA256SUMS.txt`: archive checksum.

Use a new directory and follow the [Windows beta guide](windows-beta-guide.md). First run doctor/demo/verify without creating a public Tunnel. GrokBot is optional and requires owner consent. Stop after testing; uninstall only the verified test installation, never the allowed data directory. [Optional Filesystem recipe](filesystem-readonly.md) includes its separate setup, removal, path boundary and upstream license packaging limitation.
