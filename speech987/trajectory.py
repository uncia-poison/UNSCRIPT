"""Multi-turn analysis of recurring assistant-role habits.

Tracks only a bounded window of normalized rhetorical fingerprints by default.
No transcript, user messages or personal identifiers are stored.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
import hashlib
import re
from typing import Iterable


_WORD_RE = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)
_BULLET_RE = re.compile(r"(?m)^\s*(?:[-*+]|\d+[.)])\s+\S")
_CLOSING_RE = re.compile(
    r"(?im)^\s*(?:итак|подвед[её]м итог|in conclusion|to sum up|"
    r"если хочешь, я могу|if you(?:'|’)d like, i can)\b"
)


def _fingerprint(text: str) -> str | None:
    # Only use the first nonempty paragraph; matching is an exact repeated
    # opening, not a speculative psychological interpretation.
    nonempty = next((line.strip() for line in text.splitlines() if line.strip()), "")
    words = _WORD_RE.findall(nonempty.lower())
    if len(words) < 3:
        return None
    opening = " ".join(words[:min(6, len(words))])
    return hashlib.sha256(opening.encode("utf-8")).hexdigest()[:16]


def _shape(text: str) -> tuple[str, bool, bool]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    bullet_lines = sum(bool(_BULLET_RE.match(line)) for line in lines)
    uses_list = len(lines) >= 3 and bullet_lines >= 3
    starts_with_hook = bool(re.match(
        r"(?i)^(?:и знаешь|а знаешь|here(?:'|’)s the thing|"
        r"let(?:'|’)s unpack|давай разбер[её]м)",
        lines[0],
    )) if lines else False
    wraps_up = bool(_CLOSING_RE.search(text))
    return ("list" if uses_list else "prose", starts_with_hook, wraps_up)


@dataclass(frozen=True)
class TrajectoryReport:
    samples: int
    repeated_openings: int
    repeated_shapes: int
    hook_openings: int
    formulaic_closings: int
    risk: int

    def as_dict(self) -> dict[str, int]:
        return {
            "samples": self.samples,
            "repeated_openings": self.repeated_openings,
            "repeated_shapes": self.repeated_shapes,
            "hook_openings": self.hook_openings,
            "formulaic_closings": self.formulaic_closings,
            "risk": self.risk,
        }


class VoiceTrajectory:
    """Bounded, privacy-minimizing style memory.

    Use one instance per agent / client session. Do not mix users or models.
    Does not infer consciousness, personality or psychological states.
    """

    def __init__(self, window: int = 24):
        if not isinstance(window, int) or not 2 <= window <= 128:
            raise ValueError("window must be 2..128")
        self._samples: deque[tuple[str | None, tuple[str, bool, bool]]] = deque(maxlen=window)

    def observe(self, reply: str) -> None:
        if not isinstance(reply, str):
            raise TypeError("reply must be text")
        if not reply.strip():
            return
        self._samples.append((_fingerprint(reply), _shape(reply)))

    def report(self) -> TrajectoryReport:
        samples = len(self._samples)
        openings = Counter(fp for fp, _ in self._samples if fp is not None)
        repeated_openings = sum(count - 1 for count in openings.values() if count > 1)
        shapes = Counter(shape for _, shape in self._samples)
        # Identical list/prose shape alone is ordinary; only flag
        # near-monoculture over at least 5 turns, not short conversations.
        repeated_shapes = (
            max(0, max(shapes.values(), default=0) - int(samples * 0.8))
            if samples >= 5 else 0
        )
        hooks = sum(1 for _, shape in self._samples if shape[1])
        closings = sum(1 for _, shape in self._samples if shape[2])
        risk = (2 * repeated_openings + repeated_shapes
                + max(0, hooks - 1) + max(0, closings - 1))
        return TrajectoryReport(samples, repeated_openings,
                                repeated_shapes, hooks, closings, risk)


def analyze_trajectory(replies: Iterable[str], window: int = 24) -> TrajectoryReport:
    tracker = VoiceTrajectory(window)
    for reply in replies:
        tracker.observe(reply)
    return tracker.report()
