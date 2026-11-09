"""Explainable scanner and conservative speech cleanup.

The core deliberately has no network calls or model dependencies.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import re
from typing import Any

from .rules import RULES, Rule


@dataclass(frozen=True)
class Finding:
    rule_id: str
    category: str
    start: int
    end: int
    matched: str
    weight: int
    safe_remove: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Report:
    words: int
    score: int
    score_per_100_words: float
    categories: dict[str, int]
    findings: tuple[Finding, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "words": self.words,
            "score": self.score,
            "score_per_100_words": self.score_per_100_words,
            "categories": self.categories,
            "findings": [f.as_dict() for f in self.findings],
        }


@dataclass(frozen=True)
class ProcessResult:
    original: str
    cleaned: str
    removals: int
    before: Report
    after: Report

    def as_dict(self) -> dict[str, Any]:
        return {
            "original": self.original,
            "cleaned": self.cleaned,
            "removals": self.removals,
            "before": self.before.as_dict(),
            "after": self.after.as_dict(),
        }


COMPILED: tuple[tuple[Rule, re.Pattern[str]], ...] = tuple(
    (rule, re.compile(rule.pattern)) for rule in RULES
)


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def protected_spans(text: str) -> list[tuple[int, int]]:
    """Find code, URLs, direct quotes, citations and blockquote lines.

    Rules should not rewrite cited examples or code, even if they resemble
    an assistant's mannerisms. This is a best-effort Markdown-aware scanner,
    not a complete CommonMark parser.
    """
    if not text:
        return []

    spans: list[tuple[int, int]] = []
    index = 0
    fence_start: int | None = None
    fence_char: str | None = None
    fence_size = 0
    tick = chr(96)

    for line in text.splitlines(keepends=True):
        stripped = line.lstrip(" \t")
        if fence_start is None:
            match = re.match(r"^(" + re.escape(tick) + r"{3,}|~{3,})", stripped)
            if match:
                fence_start = index
                fence_char = match.group(1)[0]
                fence_size = len(match.group(1))
            elif stripped.startswith(">"):
                spans.append((index, index + len(line)))
        else:
            if fence_char and re.match(
                r"^[ \t]*" + re.escape(fence_char) +
                "{" + str(fence_size) + r",}[ \t]*\r?\n?$", line
            ):
                spans.append((fence_start, index + len(line)))
                fence_start = None
                fence_char = None
                fence_size = 0
        index += len(line)

    if fence_start is not None:
        spans.append((fence_start, len(text)))

    inline_code = re.escape(tick) + "[^" + tick + "\n]+" + re.escape(tick)
    spans.extend((m.start(), m.end()) for m in re.finditer(inline_code, text))
    for pattern in (
        r"(?<!\w)https?://[^\s<>\]\)]+",
        r"\[[^\]\n]+\]\(https?://[^)\s]+\)",
        r"«[^»\n]*»",
        r"“[^”\n]*”",
        r'"[^"\n]{2,}"',
        r"cite[^\n]*?",
    ):
        spans.extend((m.start(), m.end()) for m in re.finditer(pattern, text))

    return _merge_spans(spans)


def _overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    # Lists here are small; simple linear iteration avoids indexing complexity.
    return any(start < span_end and end > span_start for span_start, span_end in spans)


def analyze(text: str, language: str = "auto") -> Report:
    """Audit text. language may be auto, ru, en or both.

    A reported pattern is an editorial signal, NOT proof that AI wrote it.
    """
    if language not in {"auto", "ru", "en", "both"}:
        raise ValueError("language must be auto, ru, en, or both")
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    has_ru = bool(re.search(r"[А-Яа-яЁё]", text))
    has_en = bool(re.search(r"[A-Za-z]", text))
    if language == "auto":
        languages = ({"ru"} if has_ru else set()) | ({"en"} if has_en else set())
    elif language == "both":
        languages = {"ru", "en"}
    else:
        languages = {language}

    protected = protected_spans(text)
    findings: list[Finding] = []
    for rule, rx in COMPILED:
        if rule.language not in languages and rule.language != "both":
            continue
        for match in rx.finditer(text):
            if _overlaps(match.start(), match.end(), protected):
                continue
            findings.append(
                Finding(rule.id, rule.category, match.start(), match.end(),
                        match.group(), rule.weight, rule.safe_remove)
            )

    # Avoid counting same-span synonyms twice; prefer higher-weight findings.
    findings.sort(key=lambda f: (f.start, -f.weight, -(f.end - f.start), f.rule_id))
    unique: list[Finding] = []
    for f in findings:
        if any(f.start == previous.start and f.end == previous.end for previous in unique):
            continue
        unique.append(f)

    categories = dict(sorted(Counter(f.category for f in unique).items()))
    words = len(re.findall(r"[\w]+(?:[-’'][\w]+)*", text, flags=re.UNICODE))
    score = sum(f.weight for f in unique)
    return Report(words, score, round(score * 100 / max(words, 1), 2),
                  categories, tuple(unique))


def process(text: str, language: str = "auto") -> ProcessResult:
    """Remove only explicit, context-free preambles; never invent replacements."""
    before = analyze(text, language)
    output = text
    total_removals = 0
    # Re-scan until stable: nested empty preambles must not survive or make
    # the cleanup non-idempotent. A hard cap prevents accidental infinite loops.
    for _ in range(32):
        current = analyze(output, language)
        removals = [finding for finding in current.findings if finding.safe_remove]
        chosen: list[Finding] = []
        for f in sorted(removals, key=lambda f: (f.start, -(f.end - f.start))):
            if not chosen or f.start >= chosen[-1].end:
                chosen.append(f)
        if not chosen:
            break

        updated = output
        for f in reversed(chosen):
            remainder = updated[f.end:]
            if remainder and remainder[0].islower():
                remainder = remainder[0].upper() + remainder[1:]
            updated = updated[:f.start] + remainder

        if updated == output:
            break
        total_removals += len(chosen)
        output = updated

    after = analyze(output, language)
    return ProcessResult(text, output, total_removals, before, after)

def clean(text: str, language: str = "auto") -> str:
    """Return conservatively cleaned text. Idempotent by design."""
    return process(text, language).cleaned
