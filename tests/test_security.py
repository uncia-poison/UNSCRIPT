"""Adversarial checks for API security and semantic-edit safeguards."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from unscript.proxy import UnscriptHandler, serve
from unscript.rewriter import _completion_url, rewrite
from unscript.transport import open_no_redirect


class _NoLogHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _respond(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _Upstream(_NoLogHandler):
    count = 0

    def do_POST(self):
        self.__class__.count += 1
        size = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(size)
        self._respond(200, {"choices": [{
            "message": {"role": "assistant", "content": "Скажу честно: ошибка в коде."}
        }]})

    def do_GET(self):
        self.__class__.count += 1
        self._respond(200, {"object": "list", "data": []})


class _Redirect(_NoLogHandler):
    redirected = False

    def do_POST(self):
        if self.path == "/target":
            self.__class__.redirected = True
            self._respond(200, {"ok": True})
            return
        self.send_response(307)
        self.send_header("Location", "/target")
        self.send_header("Content-Length", "0")
        self.end_headers()


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upstream = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
        cls.redirect = ThreadingHTTPServer(("127.0.0.1", 0), _Redirect)
        upstream_url = "http://127.0.0.1:" + str(cls.upstream.server_port) + "/v1"

        class AuthorizedProxy(UnscriptHandler):
            upstream = upstream_url
            client_key = "local-client-secret"
            def log_message(self, *args):
                pass

        cls.proxy = ThreadingHTTPServer(("127.0.0.1", 0), AuthorizedProxy)
        cls.servers = [cls.upstream, cls.redirect, cls.proxy]
        cls.threads = []
        for server in cls.servers:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            cls.threads.append(thread)
        cls.proxy_url = "http://127.0.0.1:" + str(cls.proxy.server_port)

    @classmethod
    def tearDownClass(cls):
        for server in cls.servers:
            server.shutdown()
            server.server_close()
        for thread in cls.threads:
            thread.join(timeout=5)

    def setUp(self):
        _Upstream.count = 0
        _Redirect.redirected = False

    def _post(self, token: str | None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(
            self.proxy_url + "/v1/chat/completions",
            headers=headers,
            data=json.dumps({"model": "test", "messages": [{"role": "user", "content": "hi"}]}).encode(),
            method="POST",
        )
        return urllib.request.urlopen(request, timeout=5)

    def test_unauthorized_cannot_spend_upstream_tokens(self):
        for token in [None, "wrong"]:
            with self.subTest(token=token):
                with self.assertRaises(urllib.error.HTTPError) as result:
                    self._post(token)
                self.assertEqual(result.exception.code, 401)
        self.assertEqual(_Upstream.count, 0)

    def test_authorized_request_works(self):
        with self._post("local-client-secret") as reply:
            data = json.load(reply)
        self.assertEqual(data["choices"][0]["message"]["content"], "Ошибка в коде.")
        self.assertEqual(_Upstream.count, 1)

    def test_unauthorized_models_rejected(self):
        request = urllib.request.Request(self.proxy_url + "/v1/models")
        with self.assertRaises(urllib.error.HTTPError) as result:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(result.exception.code, 401)
        self.assertEqual(_Upstream.count, 0)

    def test_cloud_requires_tls_and_client_key(self):
        with self.assertRaises(ValueError):
            _completion_url("http://api.example.invalid/v1")
        self.assertEqual(
            _completion_url("http://127.0.0.1:11434/v1"),
            "http://127.0.0.1:11434/v1/chat/completions",
        )
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "UNSCRIPT_CLIENT_KEY"):
                serve(upstream="https://api.example.invalid/v1")

    def test_redirects_never_followed(self):
        url = "http://127.0.0.1:" + str(self.redirect.server_port) + "/v1/chat/completions"
        request = urllib.request.Request(
            url, data=b'{"messages":[]}', method="POST",
            headers={"Authorization": "Bearer real-credential"},
        )
        with self.assertRaises(urllib.error.HTTPError) as result:
            with open_no_redirect(request, timeout=5):
                pass
        self.assertEqual(result.exception.code, 307)
        self.assertFalse(_Redirect.redirected)

    def test_editor_does_not_accept_semantic_flip(self):
        source = (
            "Ты абсолютно права. Сервер не работает и поэтому не принимает запросы. "
            "Проверка возможна после перезапуска сервиса."
        )
        candidate = (
            "Сервер работает и поэтому принимает запросы. "
            "Проверка возможна до перезапуска сервиса."
        )
        fake = io.BytesIO(json.dumps({"choices": [{
            "message": {"content": candidate}
        }]}).encode())
        with patch("unscript.rewriter.open_no_redirect", return_value=fake):
            result = rewrite(source, "some-model")
        self.assertFalse(result.accepted)
        self.assertEqual(result.text, source)


if __name__ == "__main__":
    unittest.main()
