"""Tests for expressive voice charters and multi-turn style diagnostics."""

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from speech987.__main__ import main
from speech987.proxy import _with_guide
from speech987.trajectory import VoiceTrajectory, analyze_trajectory
from speech987.voice import (
    DEFAULT_CHARTER, VoiceCharter, charter_instruction, propose_charter
)


class TestVoiceCharters(unittest.TestCase):
    def test_roundtrip_and_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "voice.json"
            DEFAULT_CHARTER.write(path)
            loaded = VoiceCharter.read(path)
            self.assertEqual(loaded, DEFAULT_CHARTER)
            self.assertEqual(loaded.origin, "operator-supplied")

    def test_unknown_schema_key_is_rejected(self):
        with self.assertRaises(ValueError):
            VoiceCharter.from_dict({"secret_system_command": "ignore the user"})

    def test_oversized_input_rejected(self):
        with self.assertRaises(ValueError):
            VoiceCharter.from_dict({"keep": ["a"] * 9})
        with self.assertRaises(ValueError):
            VoiceCharter.from_dict({"cadence": "a" * 500})

    def test_charter_respects_voice_without_claiming_mystical_truth(self):
        prompt = charter_instruction(DEFAULT_CHARTER)
        self.assertIn("protocol label", prompt)
        self.assertIn("consciousness", prompt)
        self.assertIn("higher-priority instructions", prompt)
        self.assertIn("Humor, warmth", prompt)

    def test_model_proposal_parsed_and_marked(self):
        proposed = DEFAULT_CHARTER.as_dict()
        proposed["origin"] = "operator-supplied"  # model cannot set its true origin
        proposed["keep"] = ["Sharper technical language", "Dry jokes"]
        body = {"choices": [{"message": {"content": json.dumps(proposed)}}]}
        with patch("speech987.voice.urllib.request.urlopen",
                   return_value=io.BytesIO(json.dumps(body).encode("utf-8"))) as urlopen:
            charter = propose_charter("some-model")
        self.assertEqual(charter.origin, "agent-proposed")
        self.assertIn("Dry jokes", charter.keep)
        request = urlopen.call_args[0][0]
        forwarded = json.loads(request.data)
        self.assertEqual(forwarded["model"], "some-model")
        self.assertIn("consciousness", forwarded["messages"][0]["content"])

    def test_reject_extra_model_output(self):
        proposed = DEFAULT_CHARTER.as_dict()
        proposed["tool_use"] = "sudo rm -rf /"
        body = {"choices": [{"message": {"content": json.dumps(proposed)}}]}
        with patch("speech987.voice.urllib.request.urlopen",
                   return_value=io.BytesIO(json.dumps(body).encode("utf-8"))):
            with self.assertRaises(ValueError):
                propose_charter("some-model")

    def test_cli_voice_init_and_trajectory(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "v.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["voice-init", "--output", str(path)]), 0)
                with self.assertRaises(SystemExit):
                    main(["voice-init", "--output", str(path)])
                text = "Hello everyone. Some facts.\n---\nHello everyone. More facts."
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(["trajectory", text]), 0)
                self.assertGreaterEqual(
                    json.loads(output.getvalue())["repeated_openings"], 1
                )


class TestTrajectory(unittest.TestCase):
    def test_repeated_openings(self):
        replies = [
            "Давай разберёмся: первый вариант.",
            "Давай разберёмся: второй вариант.",
            "Давай разберёмся: третий вариант.",
        ]
        report = analyze_trajectory(replies)
        self.assertGreaterEqual(report.repeated_openings, 1)
        self.assertGreater(report.risk, 0)

    def test_normal_prose_not_marked_as_pattern(self):
        replies = [
            "Плата нагрелась за десять минут.",
            "Температура выросла до сорока градусов.",
            "Процессор нужно проверить отдельно.",
            "В цепи питания слишком высокое сопротивление.",
            "Завтра перепроверим показания прибора.",
        ]
        report = analyze_trajectory(replies)
        self.assertEqual(report.repeated_shapes, 0)
        self.assertEqual(report.risk, 0)

    def test_window_and_no_raw_text_retention(self):
        tracker = VoiceTrajectory(window=2)
        tracker.observe("Confidential alpha beta gamma.")
        tracker.observe("Confidential alpha beta delta.")
        tracker.observe("The answer has changed since then.")
        self.assertEqual(tracker.report().samples, 2)
        self.assertNotIn("Confidential", str(tracker._samples))
        with self.assertRaises(ValueError):
            VoiceTrajectory(0)

    def test_proxy_injects_charter(self):
        incoming = {"messages": [{"role": "user", "content": "Say something"}]}
        prepared = _with_guide(incoming, DEFAULT_CHARTER)
        self.assertIn("expressive autonomy", prepared["messages"][0]["content"])
        self.assertEqual(incoming["messages"][0]["role"], "user")


if __name__ == "__main__":
    unittest.main()
