"""Deprecated import path. Use unscript.rewriter."""
import urllib.request  # Shared transport module retained for mock compatibility.
from unscript.rewriter import *  # noqa: F401,F403
from unscript.rewriter import _acceptable, _completion_url, _anchors
