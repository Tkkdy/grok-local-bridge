# Optional read-only Filesystem MCP

Use the existing Bridge with the official `@modelcontextprotocol/server-filesystem@2.0.1` as a separate stdio backend. This adds no Bridge Python dependency, gateway or OAuth implementation. It requires Node.js 24 or later; the Bridge installer does not install Node. This recipe searches **file names**, then reads selected text files; it is not a content-indexing engine.

## Prepare and approve

The user must choose the exact allowed directory. Start with disposable, non-sensitive test files. Do not use a drive root, home directory, browser profile, repository with credentials or production dataset by default. Trusted backend code executes with the Windows user's OS privileges; this is not an OS sandbox.

Install Node 24 from [the official site](https://nodejs.org/en/download), if absent. Choose a new dedicated backend directory and install the fixed package there:

```powershell
$backendRoot = Join-Path $env:LOCALAPPDATA 'Grok Local Bridge Backends/filesystem'
npm.cmd install --prefix $backendRoot --save-exact --ignore-scripts --no-fund @modelcontextprotocol/server-filesystem@2.0.1
$node = (Get-Command node.exe).Source
```

Keep the generated package-lock.json and use `npm.cmd ci --prefix $backendRoot --ignore-scripts` for subsequent reproductions. Do not use `npx @latest`, a global installation or a fresh dependency install on every tool call. Verify package provenance and licensing before redistribution; this recipe does not bundle dependencies.

## Register with the existing Bridge

Use [the manifest template](../examples/filesystem-readonly.backend.json). Replace the executable and package paths with the ones above, and the last argument with the user's approved absolute directory. Keep only `read_text_file` and `search_files` with permission `read`. The example paths are placeholders and do not grant access to any directory until configured locally.

```powershell
& $manage -InstallDir $installRoot -CommandArgs @('probe','--spec','C:/path/to/filesystem.backend.json')
& $manage -InstallDir $installRoot -CommandArgs @('add','--spec','C:/path/to/filesystem.backend.json')
& $manage -InstallDir $installRoot -CommandArgs @('status')
```

For a running Bridge, wait for APPLIED and the expected tool count, then refresh the full catalog. Expected additional names: `files_read_text_file` and `files_search_files`. Adding this backend does not itself require a new public Tunnel. Any remote test still requires authorization to expose the chosen files: tool results can reach a cloud client/model.

Search arguments: `path` = approved directory, `pattern` = `**/*.txt`. Read arguments: `path` = an approved text file. Test valid Unicode names too. Check that existing Hub/Ping tools continue working.

## Enforced boundaries and test status

Directory checks are performed by the Filesystem server, including normalized paths and resolved targets. The Bridge enforces the operation allowlist before proxy dispatch. The upstream server also implements write tools; granting only read tools at the Bridge is essential. Tool descriptions/annotations do not provide this restriction. The Bridge's downstream client supplies empty Roots, so this configuration retains its explicit CLI directories rather than forwarding remote directory grants.

On Windows, an automated loopback OAuth/MCP client verified the unchanged v0.1.0-alpha Bridge with the fixed npm package: real reads/search in user-approved disposable files, absolute/`..` outside denial, a Junction pointing to an outside canary denied by the downstream server, no canary enumeration during search, direct ungranted write rejection, unchanged file bytes, hot add/remove on the same authorized connection and healthy original tools. The temporary grant was revoked and the owned listener closed. This is not acceptance of arbitrary private documents, race conditions, all reparse/hard-link variants, OS sandboxing or a real GrokBot filesystem invocation.

## Remove and clean up

```powershell
& $manage -InstallDir $installRoot -CommandArgs @('remove','--name','files')
& $manage -InstallDir $installRoot -CommandArgs @('status')
```

Wait for APPLIED; the old names must be rejected while the other backends keep working. stdio sessions are request-scoped, so no independent Filesystem service needs a separate daemon stop. Stop the Bridge only if this entire installation is a temporary test. Revoke test authorization before deleting its owned state. Delete the optional package directory only after confirming it is the dedicated test directory; never recursively delete the user's allowed data directory as an uninstall step.

## License note

The examined 2.0.1 npm archive declares `SEE LICENSE IN LICENSE` but contains no LICENSE file. Its published npm SLSA provenance declares upstream commit `ef9808f71090d0db3eda99e2af2ba78f1086f4fb` (monorepo tag v2.1.0); the attestation signature was not independently verified in this test. [That commit's LICENSE](https://github.com/modelcontextprotocol/servers/blob/ef9808f71090d0db3eda99e2af2ba78f1086f4fb/LICENSE) describes an Apache-2.0 transition with retained MIT contributions and CC-BY-4.0 documentation. Do not describe the new package as simply MIT or redistribute it without preserving the applicable upstream notices. This external packaging issue does not change the existing Bridge source's MIT license.

Primary references: [official Filesystem MCP](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem), [npm package](https://www.npmjs.com/package/@modelcontextprotocol/server-filesystem/v/2.0.1).
