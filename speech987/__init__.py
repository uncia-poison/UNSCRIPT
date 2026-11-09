"""Compatibility facade for the former speech987 package.

New code should import unscript. Existing speech987 imports remain supported.
"""
from unscript import *  # noqa: F401,F403
from unscript import __version__ as __version__
