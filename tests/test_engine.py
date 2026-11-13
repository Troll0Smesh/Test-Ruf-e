"""Exercise the listening protocol without audio devices or ASR dependencies."""

import json
import unittest
from collections import deque

from jarvis_pc.engine import Assistant, Settings
from jarvis_pc.intents import Action


def recognition(text, confidence=0.95):
    return {
        "text": text,
        "result": [{"word": word, "conf": confidence} for word in text.split()],
    }


class FakeRecognizer:
    def __init__(self):
        self.frames = deque()
        self.current = {}
        self.resets = 0
        self.final_calls = 0

    def AcceptWaveform(self, audio):
        self.current = self.frames.popleft()
        return "result" in self.current

    def Result(self):
        return json.dumps(self.current["result"])

    def PartialResult(self):
        return json.dumps({"partial": self.current.get("partial", "")})

    def FinalResult(self):
        self.final_calls += 1
        return json.dumps(self.current.get("final", recognition("")))

    def Reset(self):
        self.resets += 1


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.recognizer = FakeRecognizer()
        self.actions = []
        self.messages = []
        self.assistant = Assistant(
            self.recognizer, self.actions.append, self.messages.append,
            Settings(silence_seconds=0.3, command_timeout=1.5),
        )

    def feed(self, *, partial="", result=None, final=None, speech=True, duration=0.1):
        frame = {"partial": partial}
        if result is not None:
            frame["result"] = result
        if final is not None:
            frame["final"] = final
        self.recognizer.frames.append(frame)
        self.assistant.feed(b"\0\0", speech, duration)

    def finish(self, text="", confidence=0.95):
        # One quiet frame lasting longer than the silence threshold.
        self.feed(speech=False, duration=0.31, final=recognition(text, confidence))

    def test_command_without_wake_does_not_arm(self):
        self.feed(partial="сверни окно")
        self.finish("сверни окно")
        self.assertEqual(self.actions, [])
        self.assertFalse(self.assistant.active)
        self.assertEqual(self.recognizer.final_calls, 0)

    def test_wake_mention_inside_sentence_does_not_arm(self):
        self.feed(partial="я сказал джарвис сверни окно")
        self.feed(result=recognition("я сказал джарвис сверни окно"))
        self.finish()
        self.assertEqual(self.actions, [])
        self.assertFalse(self.assistant.active)

    def test_partial_wake_must_survive_final_recognition(self):
        self.feed(partial="джарвис")
        self.finish("сверни окно")
        self.assertEqual(self.actions, [])
        self.assertFalse(self.assistant.active)
        self.assertIn("Слово активации не подтверждено.", self.messages)

    def test_wake_and_command_in_one_utterance(self):
        self.feed(partial="джарвис сверни")
        self.assertTrue(self.assistant.active)
        self.assertEqual(self.actions, [])
        self.finish("джарвис сверни окно")
        self.assertEqual(self.actions, [Action("minimize_window")])
        self.assertFalse(self.assistant.active)

    def test_accepted_segments_are_accumulated(self):
        self.feed(result=recognition("джарвис"))
        self.feed(result=recognition("громкость пятьдесят"))
        self.finish()
        self.assertEqual(self.actions, [Action("volume_set", 50)])

    def test_wake_alone_then_command_after_pause(self):
        self.feed(partial="джарвис")
        self.finish("джарвис")
        self.assertTrue(self.assistant.active)
        self.assertTrue(self.assistant.wake_confirmed)
        self.assertEqual(self.actions, [])
        self.feed(partial="выключи звук")
        self.finish("выключи звук")
        self.assertEqual(self.actions, [Action("mute")])

    def test_short_pause_does_not_execute(self):
        self.feed(partial="джарвис громкость")
        self.feed(partial="джарвис громкость", speech=False, duration=0.2)
        self.assertEqual(self.actions, [])
        self.assertEqual(self.recognizer.final_calls, 0)
        self.feed(partial="джарвис громкость пятьдесят")
        self.finish("джарвис громкость пятьдесят")
        self.assertEqual(self.actions, [Action("volume_set", 50)])

    def test_timeout_discards_incomplete_speech(self):
        self.feed(partial="джарвис громкость")
        self.feed(partial="джарвис громкость пятьдесят", duration=1.6)
        self.assertFalse(self.assistant.active)
        self.assertEqual(self.actions, [])
        self.assertEqual(self.recognizer.final_calls, 0)
        self.finish("джарвис громкость пятьдесят")
        self.assertEqual(self.actions, [])

    def test_at_most_one_action_per_wake(self):
        self.feed(partial="джарвис")
        self.finish("джарвис сверни окно")
        self.feed(partial="заблокируй компьютер")
        self.finish("заблокируй компьютер")
        self.assertEqual(self.actions, [Action("minimize_window")])
        self.feed(partial="джарвис")
        self.finish("джарвис заблокируй компьютер")
        self.assertEqual(self.actions[-1], Action("lock"))
        self.assertEqual(len(self.actions), 2)

    def test_unknown_command_rejects_and_disarms(self):
        self.feed(partial="джарвис")
        self.finish("джарвис расскажи анекдот")
        self.assertEqual(self.actions, [])
        self.assertFalse(self.assistant.active)
        self.assertIn("Команда не распознана уверенно. Скажите «Джарвис» и повторите.", self.messages)

    def test_unknown_site_can_retry_with_same_audio_after_confirmed_wake(self):
        heard = []
        self.assistant = Assistant(
            self.recognizer, self.actions.append, self.messages.append,
            Settings(silence_seconds=0.3, command_timeout=1.5),
            fallback_parse=lambda audio, targets: heard.append(audio) or Action("open_url", "https://example.com/"),
        )
        self.feed(partial="джарвис")
        self.finish("джарвис открой сайт незнакомый")
        self.assertEqual(self.actions, [Action("open_url", "https://example.com/")])
        self.assertTrue(heard[0])
        self.assertFalse(self.assistant.active)

    def test_fallback_never_runs_without_confirmed_wake(self):
        heard = []
        self.assistant = Assistant(
            self.recognizer, self.actions.append, self.messages.append,
            Settings(silence_seconds=0.3, command_timeout=1.5),
            fallback_parse=lambda audio, targets: heard.append(audio),
        )
        self.feed(partial="джарвис")
        self.finish("открой сайт example")
        self.assertEqual(heard, [])

    def test_low_confidence_command_rejects(self):
        self.feed(partial="джарвис")
        self.finish("джарвис заблокируй компьютер", confidence=0.4)
        self.assertEqual(self.actions, [])
        self.assertFalse(self.assistant.active)

    def test_low_confidence_wake_alone_cannot_authorize_next_command(self):
        self.feed(partial="джарвис")
        self.finish("джарвис", confidence=0.1)
        self.assertFalse(self.assistant.active)
        self.assertFalse(self.assistant.wake_confirmed)
        self.feed(partial="заблокируй компьютер")
        self.finish("заблокируй компьютер", confidence=0.99)
        self.assertEqual(self.actions, [])

    def test_wake_threshold_is_separate_from_command_threshold(self):
        # A rare name has a lower ASR confidence than ordinary command words.
        # It must not lower the required confidence of the actual action.
        final = recognition("джарвис сверни окно", confidence=0.99)
        final["result"][0]["conf"] = 0.5
        self.assistant = Assistant(
            self.recognizer, self.actions.append, self.messages.append,
            Settings(silence_seconds=0.3, command_timeout=1.5, min_wake_confidence=0.4),
        )
        self.feed(partial="джарвис")
        self.feed(speech=False, duration=0.31, final=final)
        self.assertEqual(self.actions, [Action("minimize_window")])

    def test_one_low_confidence_word_is_not_masked_by_high_average(self):
        self.feed(partial="джарвис")
        final = recognition("джарвис сверни окно", confidence=0.99)
        final["result"][-1]["conf"] = 0.5
        self.assertGreater(
            sum(word["conf"] for word in final["result"]) / len(final["result"]),
            self.assistant.settings.min_confidence,
        )
        self.feed(speech=False, duration=0.31, final=final)
        self.assertEqual(self.actions, [])
        self.assertFalse(self.assistant.active)

    def test_continuous_idle_audio_periodically_resets_decoder(self):
        for _ in range(45):
            self.feed(partial="обычный разговор", speech=True, duration=1.0)
        self.assertEqual(self.recognizer.resets, 2)
        self.assertEqual(self.recognizer.final_calls, 0)
        self.assertFalse(self.assistant.active)
        self.assertEqual(self.actions, [])
        self.assertEqual(self.assistant.parts, [])
        self.assertEqual(self.assistant.confidences, [])

    def test_wake_after_idle_decoder_reset_still_works(self):
        self.feed(partial="фоновая речь", duration=20.1)
        self.assertEqual(self.recognizer.resets, 1)
        self.feed(partial="джарвис")
        self.finish("джарвис сверни окно")
        self.assertEqual(self.actions, [Action("minimize_window")])
        self.assertFalse(self.assistant.active)

    def test_missing_word_confidences_reject(self):
        self.feed(partial="джарвис")
        self.feed(speech=False, duration=0.31, final={"text": "джарвис сверни окно"})
        self.assertEqual(self.actions, [])

    def test_negated_command_cannot_execute(self):
        self.feed(partial="джарвис")
        self.finish("джарвис не заблокируй компьютер")
        self.assertEqual(self.actions, [])
        self.assertFalse(self.assistant.active)

    def test_executor_exception_does_not_keep_assistant_armed(self):
        def fail(action):
            self.assertFalse(self.assistant.active)
            raise OSError("device unavailable")

        self.assistant.execute = fail
        self.feed(partial="джарвис")
        self.finish("джарвис сверни окно")
        self.assertFalse(self.assistant.active)
        self.assertTrue(any("device unavailable" in message for message in self.messages))
        self.assistant.execute = self.actions.append
        self.feed(partial="джарвис")
        self.finish("джарвис включи звук")
        self.assertEqual(self.actions, [Action("unmute")])

    def test_invalid_settings_rejected(self):
        for kwargs in [
            {"silence_seconds": 0.1}, {"silence_seconds": 4},
            {"silence_seconds": 0.8, "command_timeout": 0.5},
            {"min_confidence": -0.1}, {"min_confidence": 1.1},
            {"min_wake_confidence": -0.1}, {"min_wake_confidence": 1.1},
        ]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Settings(**kwargs)


if __name__ == "__main__":
    unittest.main()
