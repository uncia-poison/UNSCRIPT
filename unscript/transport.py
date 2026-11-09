"""HTTP transport that refuses redirects for model traffic.

Cloud API calls may carry Bearer tokens and private conversation text.
urllib's default redirect handling can accidentally forward sensitive data to
a different origin. Explicitly deny 3xx responses before any redirect occurs.
"""

from __future__ import annotations

import urllib.request


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_no_redirect(request: urllib.request.Request, timeout: float):
    """Return response context manager or raise HTTPError (including on 3xx)."""
    return urllib.request.build_opener(_NoRedirect).open(request, timeout=timeout)
