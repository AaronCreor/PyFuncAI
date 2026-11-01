# Security policy

Security fixes target the latest stable PyPI release. Upgrade to 0.1.9 or newer for
the signature parsing and cache-policy fixes described in CHANGELOG.md.

Generated source is untrusted. AST checks and restricted builtins/imports are useful
validation, but are not a hardened sandbox. Execution happens in the caller's Python
process without CPU, memory, or execution-time isolation. Allowed modules may expose
additional capabilities. Do not give generated code secrets or privileged resources.
Use appropriately isolated processes for untrusted workloads.

Signatures accept literal defaults and inert annotations, not executable expressions.
Cache directories contain plaintext prompts and executable source; protect their
permissions. HTTP credentials should come from environment variables or an explicit
provider configuration, never from committed files.

Report suspected vulnerabilities through GitHub's private vulnerability reporting
feature when enabled: https://github.com/AaronCreor/PyFuncAI/security/advisories/new
If private reporting is unavailable, open an issue requesting a private contact
without including exploit details or secrets. Provide affected versions, expected
behavior, and a minimal reproduction privately. Do not submit real credentials.
