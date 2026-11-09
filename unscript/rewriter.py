"""Opt-in second-pass local/OpenAI-compatible style editing with guards."""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
import json
import ipaddress
import os
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

from .core import analyze, clean, protected_spans
from .voice import VoiceCharter, charter_instruction


EDITOR_INSTRUCTION = """You are UNSCRIPT's minimal-diff style editor.
Rewrite only needless assistant-like rhetoric: empty praise, fake revelations,
theatrical hooks, unsolicited therapy, unearned emotional performance,
self-advertised honesty and formulaic antitheses.
Prefer clear, direct natural language with varied cadence.
Do not flatten genuine humor, tenderness, disagreement, specificity or voice.
Keep every fact, uncertainty, qualification, number, proper noun, URL, quotation,
code block, Markdown link, list item and explicit user instruction intact.
Do not invent facts, promises, feelings or claims of first-hand experience.
Do not explain your edits. Output only the complete edited text.
If rewriting safely would change meaning, return the text unchanged."""


@dataclass(frozen=True)
class RewriteResult:
    original: str
    text: str
    accepted: bool
    reason: str
    score_before: int
    score_after: int


def _completion_url(upstream: str) -> str:
    parsed = urlparse(upstream)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("upstream must be an absolute http(s) URL ending in /v1")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("do not embed credentials or query parameters in upstream")
    hostname = parsed.hostname or ""
    try:
        local = ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        local = hostname.rstrip(".").lower() == "localhost"
    if not local and parsed.scheme != "https":
        raise ValueError("non-loopback upstream must use HTTPS to protect API keys and text")
    return upstream.rstrip("/") + "/chat/completions"


def _anchors(text: str) -> tuple[list[str], list[str], list[str]]:
    # Numeric data, direct quotations and literal protected content are immutable.
    numbers = re.findall(r"(?<!\w)\d+(?:[.,]\d+)*(?!\w)", text)
    urls = re.findall(r"https?://[^\s<>\]\)]+", text)
    spans = protected_spans(text)
    anchors = [text[start:end] for start, end in spans]
    return numbers, urls, anchors


# Conservatively preserve tokens that encode polarity, modality, time,
# quantity and confidence. Rewriting these changes semantics even if numbers
# and quoted snippets stay unchanged. This is a lexical safeguard, NOT a
# semantic-equivalence proof; it may reject some good stylistic edits.
_MEANING_MARKERS = re.compile(
    r"(?iu)\b(?:"
    r"не|нет|ни|без|нельзя|невозможно|никогда|всегда|только|"
    r"обязательно|запрещено|разрешено|до|после|раньше|позже|"
    r"больше|меньше|выше|ниже|возможно|вероятно|примерно|"
    r"not|no|never|always|only|must|should|may|might|cannot|"
    r"can(?:'|’)t|won(?:'|’)t|before|after|more|less|"
    r"greater|smaller|above|below|perhaps|possibly|probably"
    r")\b"
)


def _critical_markers(text: str) -> tuple[Counter[str], Counter[str]]:
    # Exclude quoted spans from the token inventory; exact anchors are
    # already checked separately and must survive unchanged.
    spans = protected_spans(text)
    pieces: list[str] = []
    end = 0
    for start, finish in spans:
        pieces.append(text[end:start])
        end = finish
    pieces.append(text[end:])
    visible = "".join(pieces)
    words = Counter(m.group().lower() for m in _MEANING_MARKERS.finditer(visible))
    acronyms = Counter(re.findall(r"(?<!\w)[A-ZА-ЯЁ]{2,}(?!\w)", visible))
    return words, acronyms


def _acceptable(original: str, candidate: str) -> bool:
    if not candidate.strip():
        return False
    if len(candidate) < max(10, len(original) * 0.55):
        return False
    if len(candidate) > max(30, len(original) * 1.5):
        return False
    if _anchors(original) != _anchors(candidate):
        return False
    if _critical_markers(original) != _critical_markers(candidate):
        return False
    return True


def rewrite(
    text: str,
    model: str,
    upstream: str = "http://127.0.0.1:11434/v1",
    api_key: str | None = None,
    timeout: float = 60.0,
    charter: VoiceCharter | None = None,
) -> RewriteResult:
    """Use an explicitly chosen model, accepting only measurable improvements.

    The invariants are syntactic, not semantic proofs. Review output before
    trusting it with legal, clinical, financial or other high-stakes content.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not model.strip():
        raise ValueError("model must not be empty")

    original_score = analyze(text).score
    baseline = clean(text)
    baseline_score = analyze(baseline).score
    if baseline_score == 0:
        return RewriteResult(text, baseline, baseline != text, "no_remaining_patterns",
                             original_score, baseline_score)

    request_body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": (
                EDITOR_INSTRUCTION + ("\n\n" + charter_instruction(charter) if charter else "")
            )},
            {"role": "user", "content": baseline},
        ],
        "stream": False,
        "temperature": 0.2,
    }, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    secret = api_key if api_key is not None else (os.environ.get("UNSCRIPT_API_KEY") or os.environ.get("SPEECH987_API_KEY", ""))
    if secret:
        headers["Authorization"] = "Bearer " + secret

    request = urllib.request.Request(
        _completion_url(upstream), data=request_body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError("upstream response is too large")
            data = json.loads(raw)
        candidate = data["choices"][0]["message"]["content"]
    except (urllib.error.URLError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        return RewriteResult(text, baseline, baseline != text,
                             "editor_unavailable: " + type(exc).__name__,
                             original_score, baseline_score)

    if not isinstance(candidate, str):
        return RewriteResult(text, baseline, baseline != text, "non_text_response",
                             original_score, baseline_score)
    candidate = clean(candidate)
    if not _acceptable(baseline, candidate):
        return RewriteResult(text, baseline, baseline != text, "invariant_check_failed",
                             original_score, baseline_score)

    candidate_score = analyze(candidate).score
    if candidate_score >= baseline_score:
        return RewriteResult(text, baseline, baseline != text, "no_score_improvement",
                             original_score, baseline_score)
    return RewriteResult(text, candidate, True, "edited",
                         original_score, candidate_score)
