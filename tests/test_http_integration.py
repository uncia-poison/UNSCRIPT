"""End-to-end HTTP tests using two local in-process servers; no external API."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest
import urllib.error
import urllib.request

from speech987.proxy import SpeechHandler


class FakeUpstream(BaseHTTPRequestHandler):
    seen_payloads = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0"))
        data = json.loads(self.rfile.read(size))
        self.__class__.seen_payloads.append(data)
        response = {
            "id": "mock-1",
            "object": "chat.completion",
            "choices": [{"index": 0, "message": {
                "role": "assistant",
                "content": "Скажу честно: ошибка в модуле.",
            }, "finish_reason": "stop"}],
            "usage": {"total_tokens": 18},
        }
        self._json(200, response)

    def do_GET(self):
        if self.path == "/v1/models":
            self._json(200, {"object": "list", "data": [{"id": "local-model"}]})
        else:
            self._json(404, {})

    def _json(self, status, value):
        raw = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class SilentSpeechHandler(SpeechHandler):
    def log_message(self, *args):
        pass


class HTTPIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upstream = ThreadingHTTPServer(("127.0.0.1", 0), FakeUpstream)
        upstream_url = "http://127.0.0.1:" + str(cls.upstream.server_port) + "/v1"

        class ConfiguredSpeech(SilentSpeechHandler):
            upstream = upstream_url

        cls.speech = ThreadingHTTPServer(("127.0.0.1", 0), ConfiguredSpeech)
        cls.upstream_thread = threading.Thread(target=cls.upstream.serve_forever, daemon=True)
        cls.speech_thread = threading.Thread(target=cls.speech.serve_forever, daemon=True)
        cls.upstream_thread.start()
        cls.speech_thread.start()
        cls.base_url = "http://127.0.0.1:" + str(cls.speech.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.speech.shutdown()
        cls.upstream.shutdown()
        cls.speech.server_close()
        cls.upstream.server_close()
        cls.speech_thread.join(timeout=5)
        cls.upstream_thread.join(timeout=5)

    def setUp(self):
        FakeUpstream.seen_payloads.clear()

    def _request(self, path, data=None):
        request = urllib.request.Request(
            self.base_url + path,
            data=None if data is None else json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer unused-client-key"},
            method="GET" if data is None else "POST",
        )
        return urllib.request.urlopen(request, timeout=5)

    def test_clean_roundtrip(self):
        with self._request("/v1/chat/completions", {
            "model": "local-model",
            "messages": [{"role": "user", "content": "Check module"}],
            "stream": False,
        }) as response:
            result = json.load(response)
        self.assertEqual(result["choices"][0]["message"]["content"], "Ошибка в модуле.")
        self.assertEqual(result["usage"]["total_tokens"], 18)
        forwarded = FakeUpstream.seen_payloads[0]
        self.assertEqual(forwarded["model"], "local-model")
        self.assertEqual(forwarded["messages"][0]["role"], "system")
        self.assertEqual(forwarded["messages"][1]["content"], "Check module")

    def test_reject_streaming_before_upstream(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self._request("/v1/chat/completions", {
                "model": "local-model", "messages": [], "stream": True,
            })
        self.assertEqual(caught.exception.code, 400)
        self.assertEqual(FakeUpstream.seen_payloads, [])

    def test_health_and_models(self):
        with self._request("/health") as response:
            self.assertEqual(json.load(response)["status"], "ok")
        with self._request("/v1/models") as response:
            self.assertEqual(json.load(response)["data"][0]["id"], "local-model")


if __name__ == "__main__":
    unittest.main()
