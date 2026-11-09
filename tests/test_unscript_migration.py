"""Canonical UNSCRIPT import and migration compatibility regression tests."""

import importlib
import io
import json
import os
from unittest.mock import patch
import unittest

import unscript
import speech987


class TestBrandMigration(unittest.TestCase):
    def test_canonical_version_and_api(self):
        self.assertEqual(unscript.__version__, "0.3.0")
        self.assertIs(unscript.analyze, speech987.analyze)
        self.assertIs(unscript.VoiceCharter, speech987.VoiceCharter)
        self.assertEqual(unscript.clean("Скажу честно: проблема в коде."),
                         "Проблема в коде.")

    def test_cli_both_paths(self):
        from unscript.__main__ import main as modern_main
        from speech987.__main__ import main as legacy_main
        output = io.StringIO()
        with patch("sys.stdout", output):
            self.assertEqual(modern_main(["evaluate"]), 0)
            self.assertEqual(legacy_main(["evaluate"]), 0)
        self.assertIn("self-check", output.getvalue())

    def test_proxy_name_and_legacy_class_alias(self):
        from unscript.proxy import UnscriptHandler, SpeechHandler
        from speech987.proxy import SpeechHandler as LegacySpeechHandler
        self.assertIs(UnscriptHandler, SpeechHandler)
        self.assertIs(LegacySpeechHandler, UnscriptHandler)

    def test_legacy_api_key_fallback(self):
        from unscript.proxy import serve, SpeechHandler
        import unscript.proxy as proxy
        class Probe(Exception):
            pass
        def fail_before_loop(bind, handler):
            self.assertEqual(handler.upstream_key, "legacy-token")
            raise Probe()
        with patch.dict(os.environ, {"SPEECH987_API_KEY":"legacy-token"}, clear=True):
            with patch.object(proxy, "ThreadingHTTPServer", side_effect=fail_before_loop):
                with self.assertRaises(Probe):
                    serve()

    def test_new_key_takes_precedence(self):
        import unscript.proxy as proxy
        class Probe(Exception):
            pass
        def check(bind, handler):
            self.assertEqual(handler.upstream_key, "new-token")
            raise Probe()
        with patch.dict(os.environ, {
            "SPEECH987_API_KEY": "legacy-token",
            "UNSCRIPT_API_KEY": "new-token",
        }, clear=True):
            with patch.object(proxy, "ThreadingHTTPServer", side_effect=check):
                with self.assertRaises(Probe):
                    proxy.serve()


if __name__ == "__main__":
    unittest.main()
