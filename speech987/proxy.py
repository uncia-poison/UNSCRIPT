"""Loopback-only OpenAI Chat Completions proxy for local LLMs.

The proxy deliberately rejects SSE/streaming and does not alter tool-call
arguments or non-string/multimodal assistant content.
"""

from __future__ import annotations

from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse

from .core import clean
from .rewriter import _completion_url, rewrite


MAX_REQUEST = 1024 * 1024
MAX_RESPONSE = 8 * 1024 * 1024
LOOPBACK = {"127.0.0.1", "::1", "localhost"}

STYLE_GUIDE = """Speech987 writing policy:
Answer the user's actual question before commenting on it.
Use grounded facts and direct explanations; vary rhythm naturally.
Avoid unearned compliments, artificial revelations ("here's the thing"),
performative honesty, formulaic not-X-but-Y sentences, unsupported
psychological interpretations, forced three-part lists and ceremonial summaries.
In Russian avoid "ты попала в тонкое место", "и знаешь, что особенно важно?",
"скажу честно" and similar templates.
Never erase meaningful uncertainty, appropriate compassion, humor or genuine
character voice. Do not claim inner feelings merely to sound warm.
Use a qualification only if the factual uncertainty warrants it.
Do not add routine offers of more help or trailing questions.
Obey higher-priority safety and factuality requirements."""


def rewrite_completion(
    payload: dict,
    model: str | None = None,
    upstream: str = "http://127.0.0.1:11434/v1",
    api_key: str | None = None,
) -> dict:
    """Non-mutating transform of assistant text; preserve tools and metadata."""
    result = deepcopy(payload)
    for choice in result.get("choices", []):
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        if model:
            message["content"] = rewrite(
                content, model=model, upstream=upstream, api_key=api_key
            ).text
        else:
            message["content"] = clean(content)
    return result


def _with_guide(payload: dict) -> dict:
    output = deepcopy(payload)
    messages = output.get("messages")
    if isinstance(messages, list):
        output["messages"] = [
            {"role": "system", "content": STYLE_GUIDE},
            *messages,
        ]
    return output


class SpeechHandler(BaseHTTPRequestHandler):
    upstream: str = "http://127.0.0.1:11434/v1"
    upstream_key: str = ""
    rewrite_model: str | None = None
    timeout: float = 90.0

    def _respond(self, code: int, data: dict | bytes, content_type: str = "application/json") -> None:
        body = (
            json.dumps(data, ensure_ascii=False).encode("utf-8")
            if isinstance(data, dict) else data
        )
        self.send_response(code)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _headers_for_upstream(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.upstream_key:
            headers["Authorization"] = "Bearer " + self.upstream_key
        return headers

    def do_GET(self) -> None:
        if self.path == "/health":
            self._respond(200, {"status": "ok", "name": "speech987"})
            return
        if self.path != "/v1/models":
            self._respond(404, {"error": {"message": "not found"}})
            return
        url = self.upstream.rstrip("/") + "/models"
        try:
            request = urllib.request.Request(url, headers=self._headers_for_upstream())
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read(MAX_RESPONSE + 1)
                if len(body) > MAX_RESPONSE:
                    raise ValueError("upstream response too large")
                self._respond(response.status, body)
        except (OSError, ValueError) as exc:
            self._respond(502, {"error": {"message": "upstream failure", "type": type(exc).__name__}})

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self._respond(404, {"error": {"message": "only /v1/chat/completions is supported"}})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._respond(400, {"error": {"message": "invalid Content-Length"}})
            return
        if length <= 0 or length > MAX_REQUEST:
            self._respond(413, {"error": {"message": "request body size invalid or too large"}})
            return
        try:
            request_payload = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            self._respond(400, {"error": {"message": "invalid JSON body"}})
            return
        if not isinstance(request_payload, dict):
            self._respond(400, {"error": {"message": "JSON object required"}})
            return
        if request_payload.get("stream") is True:
            self._respond(400, {"error": {"message": "streaming/SSE not yet supported by Speech987"}})
            return
        if not isinstance(request_payload.get("messages"), list):
            self._respond(400, {"error": {"message": "messages list required"}})
            return
        body = json.dumps(_with_guide(request_payload), ensure_ascii=False).encode("utf-8")
        try:
            url = _completion_url(self.upstream)
            request = urllib.request.Request(
                url, data=body, headers=self._headers_for_upstream(), method="POST"
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE + 1)
                if len(raw) > MAX_RESPONSE:
                    raise ValueError("upstream response too large")
                reply = json.loads(raw)
                if not isinstance(reply, dict):
                    raise ValueError("unexpected upstream JSON shape")
                cleaned = rewrite_completion(
                    reply, model=self.rewrite_model, upstream=self.upstream,
                    api_key=self.upstream_key
                )
                self._respond(response.status, cleaned)
        except urllib.error.HTTPError as exc:
            # Avoid leaking upstream credentials or sensitive response bodies.
            self._respond(502, {"error": {"message": "upstream rejected request", "status": exc.code}})
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self._respond(502, {"error": {"message": "upstream failure", "type": type(exc).__name__}})


def serve(
    host: str = "127.0.0.1",
    port: int = 9870,
    upstream: str = "http://127.0.0.1:11434/v1",
    rewrite_model: str | None = None,
    api_key: str | None = None,
) -> None:
    if host not in LOOPBACK:
        raise ValueError("Speech987 proxy is loopback-only. Use 127.0.0.1, ::1 or localhost.")
    _completion_url(upstream)  # Fail before starting the server.
    if not (0 < port < 65536):
        raise ValueError("invalid port")

    class ConfiguredHandler(SpeechHandler):
        pass

    ConfiguredHandler.upstream = upstream
    ConfiguredHandler.upstream_key = api_key if api_key is not None else os.environ.get("SPEECH987_API_KEY", "")
    ConfiguredHandler.rewrite_model = rewrite_model
    with ThreadingHTTPServer((host, port), ConfiguredHandler) as server:
        print("Speech987 listening at http://" + host + ":" + str(port) + "/v1", flush=True)
        server.serve_forever()
