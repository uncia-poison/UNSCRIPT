"""Speech987 command-line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .core import analyze, clean, process
from .proxy import serve
from .rewriter import rewrite
from .voice import DEFAULT_CHARTER, VoiceCharter, propose_charter
from .trajectory import analyze_trajectory


def _read(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    try:
        path = Path(source)
        if path.is_file():
            return path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        # Very long literal text is not a valid filesystem path.
        pass
    return source


def _write(text: str, output: str | None) -> None:
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        print(text, end="" if text.endswith("\n") else "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="speech987", description="Audit and reduce formulaic LLM speech in RU/EN."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="report style issues without rewriting")
    scan.add_argument("source", help="literal text, UTF-8 filename or '-' for stdin")
    scan.add_argument("--language", choices=("auto", "ru", "en", "both"), default="auto")
    scan.add_argument("--json", action="store_true", help="machine-readable report")

    fix = sub.add_parser("fix", help="apply conservative preamble removal")
    fix.add_argument("source")
    fix.add_argument("--language", choices=("auto", "ru", "en", "both"), default="auto")
    fix.add_argument("--output", help="write into another file (never overwrite input implicitly)")
    fix.add_argument("--report", action="store_true", help="print summary to stderr")

    edit = sub.add_parser("rewrite", help="optional LLM style editor with invariants")
    edit.add_argument("source")
    edit.add_argument("--model", required=True)
    edit.add_argument("--upstream", default="http://127.0.0.1:11434/v1")
    edit.add_argument("--output")
    edit.add_argument("--report", action="store_true")
    edit.add_argument("--charter", help="path to expressive-preference charter JSON")

    proxy = sub.add_parser("proxy", help="loopback-only nonstreaming LLM gateway")
    proxy.add_argument("--host", default="127.0.0.1")
    proxy.add_argument("--port", type=int, default=9870)
    proxy.add_argument("--upstream", default="http://127.0.0.1:11434/v1")
    proxy.add_argument("--rewrite-model", help="opt in to an extra LLM editing request")
    proxy.add_argument("--charter", help="apply voice charter to every completion")

    voice_init = sub.add_parser("voice-init", help="create a neutral starter voice charter")
    voice_init.add_argument("--output", required=True, help="JSON path")
    voice_init.add_argument("--force", action="store_true", help="replace an existing charter")

    voice_propose = sub.add_parser("voice-propose", help="ask a model to propose its own charter")
    voice_propose.add_argument("--model", required=True)
    voice_propose.add_argument("--upstream", default="http://127.0.0.1:11434/v1")
    voice_propose.add_argument("--sample", default="", help="optional prior answer (literal or file)")
    voice_propose.add_argument("--output", required=True, help="proposal JSON path")
    voice_propose.add_argument("--force", action="store_true", help="replace an existing proposal")

    trajectory = sub.add_parser("trajectory", help="scan repeated patterns across replies")
    trajectory.add_argument("source", help="file, literal text or - for stdin")
    trajectory.add_argument("--delimiter", default="\\n---\\n", help="separate responses (default: newline---newline)")
    trajectory.add_argument("--window", type=int, default=24)

    sub.add_parser("evaluate", help="run built-in regression examples")
    return parser


def _evaluate() -> int:
    cases = [
        ("И знаешь, что особенно важно? Состояние не сохраняется.",
         "Состояние не сохраняется."),
        ("Скажу честно: проблема в файловой системе.",
         "Проблема в файловой системе."),
        ("Honestly, that is a bug.", "That is a bug."),
        ("А знаешь, что самое интересное? Ничего не изменилось.",
         "Ничего не изменилось."),
        ("Я не могу утверждать, что сервер доступен.", None),
        ("«Скажу честно: это пример». Снаружи всё хорошо.", None),
        ("В коде написано: " + chr(96) + "Скажу честно: баг" + chr(96), None),
        ("Это не просто программа. Это история.", None),
        ("Мы обсуждали сроки: 2026-11-09.", None),
    ]
    errors = []
    for original, expected in cases:
        expected = original if expected is None else expected
        actual = clean(original)
        if actual != expected:
            errors.append((original, expected, actual))
    for original, expected, actual in errors:
        print("FAILED:\n original: " + original +
              "\n expected: " + expected + "\n actual: " + actual, file=sys.stderr)
    print(f"Speech987 self-check: {len(cases)-len(errors)}/{len(cases)} cases passed")
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    def parser_error(message: str) -> None:
        raise SystemExit(message)
    if args.command == "scan":
        report = analyze(_read(args.source), args.language)
        if args.json:
            print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"Words: {report.words}; weighted findings: {report.score}; "
                  f"per 100 words: {report.score_per_100_words}")
            for finding in report.findings:
                status = "safe-removable" if finding.safe_remove else "review-only"
                print(f"{finding.start}:{finding.end} [{finding.category}] "
                      f"{status}: {finding.matched!r}")
        return 0
    if args.command == "fix":
        result = process(_read(args.source), args.language)
        _write(result.cleaned, args.output)
        if args.report:
            print(f"Removed: {result.removals}; score: {result.before.score} -> "
                  f"{result.after.score}", file=sys.stderr)
        return 0
    if args.command == "rewrite":
        charter = VoiceCharter.read(args.charter) if args.charter else None
        result = rewrite(_read(args.source), args.model, upstream=args.upstream, charter=charter)
        _write(result.text, args.output)
        if args.report:
            print(f"Accepted: {result.accepted}; reason: {result.reason}; "
                  f"score: {result.score_before} -> {result.score_after}", file=sys.stderr)
        return 0
    if args.command == "proxy":
        charter = VoiceCharter.read(args.charter) if args.charter else None
        serve(host=args.host, port=args.port, upstream=args.upstream,
              rewrite_model=args.rewrite_model, charter=charter)
        return 0
    if args.command == "voice-init":
        path = Path(args.output)
        if path.exists() and not args.force:
            parser_error("Charter exists; use --force to overwrite")
        DEFAULT_CHARTER.write(path)
        print(f"Created charter: {path}")
        return 0
    if args.command == "voice-propose":
        path = Path(args.output)
        if path.exists() and not args.force:
            parser_error("Proposal exists; use --force to overwrite")
        charter = propose_charter(args.model, upstream=args.upstream,
                                  sample=_read(args.sample) if args.sample else "")
        charter.write(path)
        print(f"Saved model proposal: {path}; not applied automatically")
        return 0
    if args.command == "trajectory":
        delimiter = args.delimiter.replace("\\n", "\n")
        if not delimiter:
            parser_error("delimiter must not be empty")
        replies = _read(args.source).split(delimiter)
        print(json.dumps(analyze_trajectory(replies, window=args.window).as_dict(),
                         ensure_ascii=False, indent=2))
        return 0
    if args.command == "evaluate":
        return _evaluate()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
