# Grok Local Bridge v0.1.1-alpha — Release proposal

Status: candidate; public release requires owner confirmation. Internal package version: `0.1.1a0`. Preserve `v0.1.0-alpha` and its original commit/assets; no tag is overwritten.

## Changes from v0.1.0-alpha

- Detect missing/broken Tcl/Tk before installation creates its target. doctor reports owner-window component readiness, not successful GUI authorization.
- Record backend MCP error results as audit errors instead of successes; returned errors and authorization checks are preserved.
- Copy examples into independent installations so the optional Filesystem manifest remains available.
- Add a short Windows beta guide and commit-identified CI source archives.
- Keep Filesystem MCP 2.0.1 **optional**: Node >=24, two read operations, user-approved directory, upstream execution-level path checks and Bridge grants. No added default dependency, platform, Shell or hardware tool.

## Acceptance and limits

The exact proposed commit must pass complete local tests, source-file review, redacted secret scans and GitHub Windows CI before release. Link the observed CI and commit in the final Release, with SHA-256 from RELEASE_MANIFEST.json. Do not transfer a green result from another commit.

v0.1.0-alpha passed real GrokBot OAuth/discovery/two synthetic calls. Filesystem passed local real-file boundary tests. These remain attributed to those runs; the new candidate is not automatically a new real Grok acceptance.

External beta must verify clean Windows first installation, actual winget bootstrap and first-use GUI. OS reboot recovery, long-term availability, stable public origins, all filesystem race/link attacks, WorkBuddy import and per-client ACL remain unverified or unsupported. This is not an OS sandbox.

## Proposed assets and installation

- `grok-local-bridge-v0.1.1-alpha.zip`: reviewed source only; no private history/state/credentials or bundled executables.
- `RELEASE_MANIFEST.json`: version, source commit/tree, ZIP SHA-256 and member count.
- `SHA256SUMS.txt`: archive checksum.

Follow the [Windows beta guide](windows-beta-guide.md) in a new installation directory. First run doctor/demo/verify without a public Tunnel. Grok is optional and requires owner consent. Stop and remove only the owned test installation.

CI artifacts can be shared before Release approval, but may require GitHub login and expire; they are not a published Release or permanent download.
