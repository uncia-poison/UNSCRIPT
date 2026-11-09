"""Regression suite for style checks, false positives and local proxy payloads."""

import io
import json
import unittest
from unittest.mock import patch

from unscript import RULES, analyze, clean, process, protected_spans
from unscript.__main__ import _evaluate
from unscript.proxy import _with_guide, rewrite_completion, serve
from unscript.rewriter import _acceptable, _completion_url, rewrite


class TestDetection(unittest.TestCase):
    def test_rule_set_nontrivial(self):
        self.assertGreaterEqual(len(RULES), 35)
        self.assertGreaterEqual(len({r.category for r in RULES}), 12)

    def test_russian_hook(self):
        r = analyze("И знаешь, что особенно важно? Нужно сохранить состояние.")
        self.assertIn("theatrical_hook", r.categories)
        self.assertTrue(any(f.safe_remove for f in r.findings))

    def test_russian_fake_insight(self):
        r = analyze("Ты попала в очень тонкое место.")
        self.assertIn("fake_insight", r.categories)
        self.assertFalse(any(f.safe_remove for f in r.findings))

    def test_antithesis_is_audit_only(self):
        text = "Это не просто программа. Это история."
        self.assertIn("rhetorical_antithesis", analyze(text).categories)
        self.assertEqual(clean(text), text)

    def test_uncertainty_is_flagged_not_erased(self):
        text = "Я не могу утверждать, что у нас есть доступ к логам."
        self.assertIn("unsupported_hedging", analyze(text).categories)
        self.assertEqual(clean(text), text)

    def test_emotional_cliche_is_detected(self):
        self.assertIn("unsolicited_therapy",
                      analyze("Твои чувства абсолютно валидны.").categories)

    def test_english(self):
        self.assertIn("self_advertised_honesty",
                      analyze("Honestly, this is broken.").categories)

    def test_bad_language(self):
        with self.assertRaises(ValueError):
            analyze("anything", language="xx")

    def test_protected_quotation(self):
        text = "«Ты абсолютно права» — цитата, не моя оценка."
        self.assertNotIn("sycophancy", analyze(text).categories)

    def test_protected_code(self):
        ticks = chr(96) * 3
        text = ticks + "text\nСкажу честно: ошибка здесь.\n" + ticks
        spans = protected_spans(text)
        self.assertTrue(spans)
        self.assertEqual(clean(text), text)

    def test_blockquote(self):
        text = "> Скажу честно: ошибка здесь.\nВне цитаты я проверяю код."
        self.assertEqual(clean(text), text)


class TestConservativeEdits(unittest.TestCase):
    def test_ru_hook(self):
        self.assertEqual(
            clean("И знаешь, что особенно важно? Состояние потеряно."),
            "Состояние потеряно."
        )

    def test_ru_honesty(self):
        self.assertEqual(clean("Скажу честно: баг найден."), "Баг найден.")

    def test_en_honesty(self):
        self.assertEqual(clean("Honestly, this is a bug."), "This is a bug.")

    def test_preserve_code_and_inline(self):
        tick = chr(96)
        text = "Выполни " + tick + "Скажу честно: команда" + tick
        self.assertEqual(clean(text), text)

    def test_leave_natural_sentence(self):
        text = "В письме автор сказал: Скажу честно — так произошло."
        self.assertEqual(clean(text), text)

    def test_not_delete_entire_line(self):
        text = "Скажу честно:\nЭто важно."
        self.assertEqual(clean(text), text)

    def test_not_replace_everyday_hedge(self):
        text = "Неизвестно, включён ли сервер. Я не могу утверждать, что он работает."
        self.assertEqual(clean(text), text)

    def test_no_change_blank(self):
        self.assertEqual(clean(""), "")
        self.assertEqual(clean("  \n"), "  \n")

    def test_process_scores(self):
        p = process("Скажу честно: это ошибка.")
        self.assertEqual(p.removals, 1)
        self.assertLess(p.after.score, p.before.score)

    def test_idempotent(self):
        text = "Скажу честно: Скажу честно: Состояние потеряно."
        once = clean(text)
        self.assertEqual(clean(once), once)


class TestRewrite(unittest.TestCase):
    def test_reject_loss_of_number(self):
        a = "Показатель 2026 равен 100. Это не просто цифра. Это итог."
        b = "Показатель 2027 равен 100. Это итог."
        self.assertFalse(_acceptable(a, b))

    def test_reject_loss_of_quote(self):
        a = 'Он ответил: «пожалуйста, приходите завтра».'
        b = "Он ответил: приходите завтра."
        self.assertFalse(_acceptable(a, b))

    def test_reject_loss_of_link(self):
        a = "Адрес: https://example.org/docs; архив открыт."
        b = "Архив открыт, адрес неизвестен."
        self.assertFalse(_acceptable(a, b))

    def test_keep_polarity_and_modality(self):
        from unscript.rewriter import _acceptable
        self.assertFalse(_acceptable(
            "Сервер не принимает запросы через API.",
            "Сервер принимает запросы через API."
        ))
        self.assertFalse(_acceptable(
            "Соединение возможно после повторного запуска.",
            "Соединение возможно до повторного запуска."
        ))
        self.assertFalse(_acceptable(
            "The system should not delete this file.",
            "The system should delete this file."
        ))
        self.assertFalse(_acceptable(
            "The server probably responds slowly in this region.",
            "The server responds slowly in this region."
        ))

    def test_preserve_technical_acronyms(self):
        from unscript.rewriter import _acceptable
        self.assertFalse(_acceptable(
            "API reported a failed response when the gateway restarted.",
            "HTTP reported a failed response when the gateway restarted."
        ))

    def test_invalid_upstream(self):
        with self.assertRaises(ValueError):
            _completion_url("file:///etc/passwd")

    def test_accept_improved_mocked_edit(self):
        source = (
            "Ты абсолютно права. Ошибка происходит при чтении конфигурации. "
            "Конкретно отсутствует ключ порта, поэтому сервер не запускается."
        )
        candidate = (
            "Ошибка происходит при чтении конфигурации. "
            "Конкретно отсутствует ключ порта, поэтому сервер не запускается."
        )
        payload = {"choices": [{"message": {"content": candidate}}]}
        fake = io.BytesIO(json.dumps(payload).encode("utf-8"))
        with patch("unscript.rewriter.open_no_redirect", return_value=fake):
            result = rewrite(source, "local-model")
        self.assertTrue(result.accepted, result.reason)
        self.assertEqual(result.text, candidate)

    def test_mock_rewrite_cannot_change_number(self):
        source = "Ты абсолютно права. Ошибка 123 в очереди, повторяется каждый день."
        candidate = "Ошибка 999 в очереди, повторяется каждый день."
        fake = io.BytesIO(json.dumps(
            {"choices": [{"message": {"content": candidate}}]}
        ).encode("utf-8"))
        with patch("unscript.rewriter.open_no_redirect", return_value=fake):
            result = rewrite(source, "local-model")
        self.assertFalse(result.accepted)
        self.assertEqual(result.text, source)


class TestProxy(unittest.TestCase):
    def test_only_assistant_text(self):
        payload = {
            "id": "a1",
            "usage": {"total_tokens": 77},
            "choices": [
                {"message": {
                    "role": "assistant",
                    "content": "Скажу честно: ошибка в модуле.",
                    "tool_calls": [{"function": {"arguments": '{"x":1}'}}],
                }},
                {"message": {"role": "tool", "content": "Скажу честно: не трогай"}},
                {"message": {"role": "assistant", "content": [{"type": "text", "text": "Hi"}]}}
            ]
        }
        result = rewrite_completion(payload)
        self.assertEqual(result["choices"][0]["message"]["content"], "Ошибка в модуле.")
        self.assertEqual(result["choices"][0]["message"]["tool_calls"],
                         payload["choices"][0]["message"]["tool_calls"])
        self.assertEqual(result["choices"][1], payload["choices"][1])
        self.assertEqual(result["choices"][2], payload["choices"][2])
        self.assertEqual(result["usage"], payload["usage"])
        self.assertEqual(payload["choices"][0]["message"]["content"],
                         "Скажу честно: ошибка в модуле.")

    def test_guard_prepend_does_not_mutate(self):
        req = {"model": "test", "messages": [{"role": "user", "content": "Hi"}]}
        updated = _with_guide(req)
        self.assertEqual(updated["messages"][0]["role"], "system")
        self.assertEqual(req["messages"][0]["role"], "user")

    def test_cannot_bind_to_internet(self):
        with self.assertRaises(ValueError):
            serve(host="0.0.0.0")


class TestCLI(unittest.TestCase):
    def test_builtin_examples(self):
        with patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(_evaluate(), 0)


if __name__ == "__main__":
    unittest.main()
