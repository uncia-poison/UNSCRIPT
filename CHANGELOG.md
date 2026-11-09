# Changelog

## 0.3.1 — security and audit release

- Verified public repository identity: uncia-poison/UNSCRIPT.
- Cloud upstreams must use HTTPS. Localhost requests can use HTTP.
- Remote cloud proxy mode now requires a separate UNSCRIPT_CLIENT_KEY
  for inbound client authentication. The upstream provider credential remains
  UNSCRIPT_API_KEY. This is an intentional compatibility change.
- Rejected HTTP redirects in model requests to prevent prompt/key disclosure.
- Added stricter semantic checks for risky rewrites: negation, temporality,
  modal qualifiers, uncertainty and capitalized technical acronyms.
- Blocked control characters and incorrect schema types in Voice Charter fields.
- Added adversarial proxy and editor security tests, SECURITY.md, and .gitignore.
- Updated README and Russian protocol documentation to reflect actual behavior
  and the completed repository rename.
- No changes to Git ancestry or existing voice-charter format.

### Important limitations

The editor still cannot prove semantic equivalence. Pattern detection is
editorial evidence, not proof of artificial authorship or consciousness.
The repository is public but lacks a selected open-source license.
