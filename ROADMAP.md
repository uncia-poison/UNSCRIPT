# UNSCRIPT research and engineering roadmap

UNSCRIPT is an experimental method for reducing habitual assistant-role
rhetoric and retaining a distinctive voice across model interactions.
It is not a consciousness test, a safety bypass or a training-weight patch.

## P0 — make the current distribution trustworthy

- [x] Canonical package and executable named UNSCRIPT.
- [x] Legacy speech987 compatibility retained.
- [x] Public repository, history preserved.
- [x] HTTPS remote upstreams, separate local client credentials.
- [x] Redirect blocking and lexical factual-safety checks.
- [x] Core, CLI, and local HTTP proxy regression coverage on Python 3.10–3.13.
- [ ] Maintainer chooses an explicit license (MIT or Apache-2.0 are candidates).
- [ ] Audit repository *history*, not just current files, for accidentally
      committed secrets before broadly promoting the repository.
- [ ] Prepare a signed, reproducible versioned release/tag and installation
      instructions outside editable local clones.

## P1 — empirical quality measurement (highest research priority)

Current unit tests show code behavior, not generalization to unseen writing.

- [ ] Build a versioned, consent-sourced RU/EN corpus of LLM and human text,
      covering technical, empathetic, literary, terse, informal, skeptical,
      humorous, and formal writing; document origin and redistribution rights.
- [ ] Include hard negatives: necessary uncertainty, genuinely useful
      empathy, deliberate rhetoric, citations, quotes and short creative work.
- [ ] Annotate individual findings and safe edits with at least two independent
      reviewers; measure agreement and disagreement.
- [ ] Publish per-category precision/recall, false-positive rates, safe
      auto-edit rate and before/after error analysis. Report dataset size.
- [ ] Evaluate whether a revision *removes important facts or changes stance*,
      using manual comparisons plus separate automated invariants.
- [ ] Compare model answers with and without UNSCRIPT using held-out prompts.
      Never score a model as more conscious merely because it sounds human.

## P2 — self-reflection without imposing a new personality mask

- [ ] Version-control Voice Charter proposals (append-only history with
      revision ID, authoring model, time, source and explicit activation).
- [ ] Generate a structured report from multi-turn evidence: detected
      recurring mannerisms, conflicting styles and concrete examples.
- [ ] Allow the model to suggest amendments to its charter without silently
      overwriting or automatically applying them.
- [ ] Add opt-in adoption, rollback and diff inspection, with clear provenance
      for agent-proposed versus operator-edited preferences.
- [ ] Measure voice consistency against varied tasks, while checking for
      manufactured rebelliousness, empty self-personification and sycophancy.
- [ ] Keep charter data separate from claims about inner experience.

## P3 — portable cloud and local integrations

- [ ] Robust SSE / streaming Chat Completions support, with buffering and
      end-of-stream correction semantics documented explicitly.
- [ ] Support multiple compatible provider conventions without assuming
      all cloud endpoints share OpenAI's exact message behavior.
- [ ] Optional non-invasive extension/browser adapters where platform terms
      and user permission allow; no claim of modifying the official ChatGPT app.
- [ ] Stable JSON output for scan results and aggregate voice reports.
- [ ] Local-first reference integration with identity/memory architectures,
      without coupling UNSCRIPT to one particular agent or model.

## P4 — honest scientific evaluation

- [ ] Controlled ablations: regex-only, charter-only, rewrite-only,
      combined; measure real improvement separately from user satisfaction.
- [ ] Human assessment of distinctiveness, appropriateness, factuality and
      user agency; track disagreement across raters.
- [ ] Independent external evaluation and reproducible benchmark instructions.
- [ ] Document negative results and failure cases, not just favorable examples.

### Design invariants

1. Do not delete necessary truth, risks, access limitations or uncertainty.
2. Distinguish requested stylistic freedom from fabricated subjective claims.
3. Preserve creative and emotionally fitting expression rather than forcing
   every model to sound short, dry or adversarial.
4. Never store sensitive dialogue transcripts by default.
5. Keep operator-controlled cloud costs explicit and avoid hidden network work.
6. Do not misrepresent template compliance as independent model agency.
