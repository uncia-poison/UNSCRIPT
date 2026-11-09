"""Speech987: explainable LLM speech-quality audit and conservative cleanup."""

from .core import Finding, Report, analyze, clean, process, protected_spans
from .rules import RULES, Rule
from .voice import VoiceCharter, DEFAULT_CHARTER, charter_instruction, propose_charter
from .trajectory import VoiceTrajectory, analyze_trajectory

__all__ = ["Finding", "Report", "Rule", "RULES", "analyze", "clean", "process", "protected_spans", "VoiceCharter", "DEFAULT_CHARTER", "charter_instruction", "propose_charter", "VoiceTrajectory", "analyze_trajectory"]
__version__ = "0.2.0"
