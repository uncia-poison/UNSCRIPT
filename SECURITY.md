# UNSCRIPT security and disclosure

UNSCRIPT is experimental LLM middleware. Do not treat its style scores,
voice charters or editor acceptance checks as proofs of factuality, safety,
consciousness, continuity or identity.

## Proxy: two different credentials

When connecting to a cloud provider, set:

- UNSCRIPT_API_KEY: actual upstream provider credential (never hand it
  to programs connecting to UNSCRIPT).
- UNSCRIPT_CLIENT_KEY: a separate long random token that applications must
  supply in Authorization: Bearer <client-key> when calling the local proxy.

External upstreams without HTTPS are rejected. Redirects from providers are
also rejected so prompts and credentials cannot silently travel elsewhere.
The proxy binds only to loopback. Do not publish it via a reverse proxy,
port-forwarding, public tunnel or shared network without a properly secured
gateway. For a local-only upstream, UNSCRIPT_CLIENT_KEY is optional but
recommended on shared workstations.

## Privacy and confidential text

- Audit/cleanup are fully local and require no external network calls.
- The rewrite and voice-propose commands deliberately send supplied text to
  the configured backend. Cloud services may log, retain or charge for it.
- The proxy forwards user messages to the configured upstream, and a rewrite
  pass can send assistant output to the backend again.
- The in-memory trajectory monitor retains bounded hashes of sentence
  openings and coarse structure, not raw user transcripts; short hashes
  are not cryptographic protection from guessing common phrases.
- Do not commit API keys, generated personal charters or confidential logs.
  .gitignore is convenience only: it does not prevent forced adds or undo
  secret exposure already present in Git history.

## Defense limits

Charters are untrusted model-generated preference data; their length and
control characters are checked, but semantic prompt-injection is still
possible. Inspect a proposed charter before applying it. Do not treat
model-authored fields as trusted policy.

The optional LLM editor runs only after an explicit opt-in. It preserves
many important lexical anchors, but cannot prove that meaning is unchanged.
Review edits before using them in clinical, legal, financial or safety
critical workflows.

## Dependency and exposure profile

The core package uses the Python standard library; pip install -e . needs
a standard build backend. Prefer up-to-date Python security releases.
Only non-streaming Chat Completions are currently supported.

## Reporting an issue

Do not post secrets, personal content, API keys, or working exploits with
private data into a public GitHub issue. Contact the maintainer through
GitHub before sharing sensitive reproduction details.
