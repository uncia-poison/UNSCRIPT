"""Speech987: explainable LLM speech-quality audit and conservative cleanup."""

from .core import Finding, Report, analyze, clean, process, protected_spans
from .rules import RULES, Rule

__all__ = ["Finding", "Report", "Rule", "RULES", "analyze", "clean", "process", "protected_spans"]
__version__ = "0.1.0"
