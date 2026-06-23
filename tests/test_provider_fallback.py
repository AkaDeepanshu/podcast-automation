"""Unit tests for provider error handling and fallback behavior."""

import unittest
from unittest.mock import MagicMock, patch

from groq import APIStatusError

from core.providers.fallback_script import FallbackScriptGenerator
from core.providers.groq_script import GroqScriptGenerator, _is_unsupported_json_schema_error
from core.providers.provider_errors import classify_provider_error


class TestClassifyProviderError(unittest.TestCase):
    def test_quota_resource_exhausted(self):
        exc = Exception("503... no wait 429 RESOURCE_EXHAUSTED limit: 20")
        exc.code = 429
        self.assertEqual(classify_provider_error(exc), "quota")

    def test_transient_unavailable(self):
        exc = Exception("503 UNAVAILABLE. high demand")
        exc.code = 503
        self.assertEqual(classify_provider_error(exc), "transient")

    def test_config_json_schema(self):
        exc = Exception(
            "400 - does not support response format `json_schema`"
        )
        exc.status_code = 400
        self.assertEqual(classify_provider_error(exc), "config")

    def test_other(self):
        self.assertEqual(classify_provider_error(ValueError("bad data")), "other")


class TestGroqUnsupportedSchemaDetection(unittest.TestCase):
    def test_detects_json_schema_message(self):
        exc = Exception("This model does not support response format `json_schema`")
        self.assertTrue(_is_unsupported_json_schema_error(exc))


class TestGroqFailFast(unittest.TestCase):
    def _make_generator(self):
        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            with patch("core.providers.groq_script.Groq"):
                return GroqScriptGenerator(model="llama-3.3-70b-versatile")

    def test_fail_fast_on_unsupported_json_schema_400(self):
        gen = self._make_generator()
        err = APIStatusError(
            "does not support response format `json_schema`",
            response=MagicMock(status_code=400),
            body={"error": {"message": "does not support response format `json_schema`"}},
        )
        self.assertTrue(gen._should_fail_fast(err))

    def test_auto_mode_downgrades_on_unsupported_schema(self):
        gen = self._make_generator()
        gen.structured_output_mode = "auto"

        schema_err = APIStatusError(
            "does not support response format `json_schema`",
            response=MagicMock(status_code=400),
            body={"error": {"message": "does not support response format `json_schema`"}},
        )
        ok_content = (
            '{"segments": [{"segment_number": 1, "theme": "t", '
            '"beats": ["a"], "target_minutes": 5}]}'
        )

        with patch.object(gen, "_call_api", side_effect=[schema_err, ok_content]) as mock_call:
            result = gen._generate_json(
                "prompt", {"name": "x", "schema": {}}, "hint", max_retries=3
            )

        self.assertEqual(gen._effective_output_mode, "json_object")
        self.assertEqual(mock_call.call_count, 2)
        self.assertEqual(len(result["segments"]), 1)


class TestFallbackScriptGenerator(unittest.TestCase):
    def test_falls_through_on_failure_with_category_in_log(self):
        failing = MagicMock()
        failing.generate_outline.side_effect = RuntimeError(
            "503 UNAVAILABLE high demand"
        )
        succeeding = MagicMock()
        succeeding.generate_outline.return_value = ["outline"]

        fb = FallbackScriptGenerator([("gemini", failing), ("groq", succeeding)])
        result = fb.generate_outline(
            topic="test",
            num_segments=1,
            target_duration_minutes=5,
            speakers={},
        )
        self.assertEqual(result, ["outline"])
        succeeding.generate_outline.assert_called_once()

    def test_sticks_with_provider_after_fallback(self):
        first = MagicMock()
        first.generate_outline.side_effect = RuntimeError("quota exhausted 429")
        second = MagicMock()
        second.generate_outline.return_value = ["outline"]
        second.generate_segment_script.return_value = ["lines"]

        fb = FallbackScriptGenerator([("gemini", first), ("groq", second)])
        fb.generate_outline(topic="t", num_segments=1, target_duration_minutes=5, speakers={})
        fb.generate_segment_script(
            topic="t",
            outline_segment=MagicMock(),
            speakers={},
            previous_context="",
            target_word_count=100,
        )
        second.generate_segment_script.assert_called_once()
        first.generate_segment_script.assert_not_called()


if __name__ == "__main__":
    unittest.main()
