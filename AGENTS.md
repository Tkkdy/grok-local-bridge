# Grok Local Bridge

Use only isolated synthetic backends for development and CI. Never import a private Hub runtime, credentials, business database or device state. Runtime binds loopback; public MCP always requires OAuth. Keep tests, Inspector and real-client evidence separate. Preserve MIT vendor notices. New processes must be owned and cleanup must never kill a PID merely because it appears in a state file. Do not change firewall, proxy, DNS or Windows tasks as a diagnostic shortcut. Exclude runtime artifacts and old Git history from releases.
