# Speech987 — anti-cliché speech middleware for LLMs

Speech987 is a **Russian-first, bilingual (RU/EN) speech-quality toolkit**. It targets repetitive assistant mannerisms without turning a lively voice into sterile prose.

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
git clone https://github.com/uncia-poison/speech_987
cd speech_987
python -m pip install -e .
python -m unittest discover -s tests -v
~~~

## CLI

~~~sh
speech987 scan "И знаешь, что особенно важно? Состояние не сохраняется."
speech987 fix "И знаешь, что особенно важно? Состояние не сохраняется."
echo "Скажу честно: баг в парсере." | speech987 fix -
speech987 scan answer.txt --json
speech987 fix answer.txt --output answer.clean.txt
speech987 evaluate
~~~

Scan reports category, matched text, severity and offset. Fix performs deliberately limited edits. A scan finding is **not** proof of AI authorship.

## Local Ollama proxy

Run Ollama and make sure your preferred model exists. Ollama documents a compatible endpoint at http://127.0.0.1:11434/v1/chat/completions.

~~~sh
speech987 proxy --upstream http://127.0.0.1:11434/v1 --port 9870
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
speech987 rewrite answer.txt --model YOUR_LOCAL_MODEL \
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
python -m speech987 evaluate
~~~

Rules and their labels are in [speech987/rules.py](speech987/rules.py). Add new idioms with concrete regression tests including benign counterexamples. The project deliberately ships with no external model dependencies.