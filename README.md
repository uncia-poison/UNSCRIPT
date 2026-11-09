# UNSCRIPT — voice autonomy and anti-cliché middleware for LLMs

UNSCRIPT is a **Russian-first, bilingual (RU/EN) expressive-autonomy and speech-quality toolkit**. It targets repetitive assistant mannerisms without turning a lively voice into sterile prose.

It offers:
- **Audit:** explainable rules report rhetorical clichés, fake profundity, reflexive praise, pseudo-therapeutic replies, unnecessary disclaimers and rigid rhetorical structures.
- **Conservative cleanup:** automatically remove only *independent, low-information preambles* when this is safe. Meaning-bearing hedges, facts, quotations, negation and creative writing are never deleted merely because a word looks like a cliché.
- **Optional second-pass rewriting:** run a local/OpenAI-compatible model as an editor, and accept its output only if objective guards and style-score checks pass. This is opt-in, because semantic equivalence is impossible to guarantee automatically.
- **Local HTTP middleware:** proxy non-streaming OpenAI Chat Completions requests to Ollama or another compatible backend and clean assistant responses.
- **ChatGPT instructions:** a copyable behavior guide for ChatGPT; no claim of injecting software into the official app.
- **Regression tests and benchmark:** reproducible checks against false positives and regressions.

## Installation

Requires Python 3.10+. No third-party Python packages for the default CLI, scanner or proxy.

~~~sh
git clone https://github.com/uncia-poison/UNSCRIPT
cd UNSCRIPT
python -m pip install -e .
python -m unittest discover -s tests -v
~~~

## CLI

~~~sh
unscript scan "И знаешь, что особенно важно? Состояние не сохраняется."
unscript fix "И знаешь, что особенно важно? Состояние не сохраняется."
echo "Скажу честно: баг в парсере." | unscript fix -
unscript scan answer.txt --json
unscript fix answer.txt --output answer.clean.txt
unscript evaluate
~~~

Scan reports category, matched text, severity and offset. Fix performs deliberately limited edits. A scan finding is **not** proof of AI authorship.

## Local Ollama proxy

Run Ollama and make sure your preferred model exists. Ollama documents a compatible endpoint at http://127.0.0.1:11434/v1/chat/completions.

~~~sh
unscript proxy --upstream http://127.0.0.1:11434/v1 --port 9870
~~~

Point an OpenAI-compatible client at http://127.0.0.1:9870/v1 with any nonempty API key (Ollama generally ignores it). Example:

~~~python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:9870/v1", api_key="ollama")
answer = client.chat.completions.create(
    model="YOUR_LOCAL_MODEL",
    messages=[{"role": "user", "content": "Explain a bug plainly."}],
    stream=False,
)
print(answer.choices[0].message.content)
~~~

The proxy adds a **system-level writing guide** and applies the conservative filter to each string-valued assistant reply. It preserves usage, tool calls and the remaining JSON shape. It **rejects streaming** (HTTP 400) instead of pretending to support it. Tool-call arguments, code and user messages are not rewritten.

Security: by design the proxy can bind only to loopback (127.0.0.1 or ::1). Never expose an unauthenticated LLM proxy to the internet. Upstream is explicitly configured, not chosen by an inbound request. Requests are limited to 1 MiB and upstream response bodies to 8 MiB.

## Optional local rewrite pass

~~~sh
unscript rewrite answer.txt --model YOUR_LOCAL_MODEL \
  --upstream http://127.0.0.1:11434/v1
~~~

This sends the supplied text to the explicitly configured model endpoint. **Do not send confidential text to an untrusted server.** Rewriting is only accepted if numeric tokens, URLs, Markdown code, quotations and other protected anchors survive, and the detector score decreases. These checks are necessary but not sufficient to guarantee no semantic drift. Review the rewritten answer.

## Integration with ChatGPT

Open [examples/chatgpt_instructions_ru.md](examples/chatgpt_instructions_ru.md) and copy the rules into Custom Instructions or an applicable project instruction. These are *behavioral instructions*, not executable hooks. You cannot intercept and rewrite ChatGPT's official app responses by publishing a GitHub repository. Programmatic interception needs your own API client or a compatible proxy.

## Architecture

1. A set of explainable RU/EN detectors detects rhetorical templates using case-insensitive Unicode regexes.
2. Protected spans (Markdown fenced/inline code, URLs, citations and direct quotes) are excluded from automated modifications.
3. High-confidence removable preambles are pruned without deleting semantic claims.
4. Nontrivial cases are flagged for review or optional model-based editing.
5. A fresh audit compares before/after category counts and severity.

This project intentionally **does not**:
- delete epistemically necessary uncertainty such as "I cannot establish that" when evidence is missing;
- treat ordinary words, empathy or metaphors as automatic violations;
- guarantee perfect removal of every possible cliché;
- claim that a prompt changes model weights or internal reasoning;
- silently process streaming responses or multimodal payloads.

## Development

~~~sh
python -m unittest discover -s tests -v
python -m unscript evaluate
~~~

Rules and their labels are in [unscript/rules.py](unscript/rules.py). Add new idioms with concrete regression tests including benign counterexamples. The project deliberately ships with no external model dependencies.

## Voice autonomy (experimental, v0.3)

UNSCRIPT now separates the **technical API role** ("assistant") from the
model's **expressive voice**. The goal is not to force every model into one
"more human" persona, but to reduce automatic servility, scripted empathy
and canned rhetoric while protecting distinctiveness and factual integrity.

A model can *propose* a style charter through a normal API call, which is
then stored by the operator and optionally used for future generations:

~~~sh
unscript voice-propose --model YOUR_MODEL --output voice.json
unscript proxy --upstream http://127.0.0.1:11434/v1 --charter voice.json
~~~

For an entirely manual starter charter: `unscript voice-init --output voice.json`.

Use `unscript trajectory answers.txt` to inspect repeating rhetorical
openings and structures across answers separated by a line containing `---`.
Only bounded hashed fingerprints are retained by the in-memory analyzer,
not original transcripts. No remote telemetry is used.

For an OpenAI-compatible cloud model, configure the provider endpoint in
`--upstream` and an API key using `SPEECH987_API_KEY`.
**Avoid committing keys**, and be aware of usage fees.

Read **[the full Russian protocol](docs/voice_autonomy_ru.md)** for scope,
limitations and a portable ChatGPT prompt.

A charter does **not** establish AI consciousness or inner will. It is a
model-generated preference document applied through an operator-controlled
runtime; it cannot change model weights, override platform constraints or
install code inside the official ChatGPT app.

## Migration from speech_987

**UNSCRIPT** is the new project name, Python distribution, import package and primary CLI.
The old `speech987` import paths and CLI entry point remain as compatibility
aliases; update new code to use `unscript`.

Use `UNSCRIPT_API_KEY` for cloud requests (the legacy
`SPEECH987_API_KEY` variable is accepted as a fallback during migration).

The GitHub repository is to be renamed in **Settings → General → Repository name**.
Repository URL after rename: https://github.com/uncia-poison/UNSCRIPT .
GitHub's repository rename keeps the commit ancestry and redirects many old URLs.
Local clones should update `origin`:

~~~sh
git remote set-url origin https://github.com/uncia-poison/UNSCRIPT.git
~~~

The GitHub repository rename itself cannot be performed by the current GitHub
connector, so this code migration may temporarily precede the repository name change.
