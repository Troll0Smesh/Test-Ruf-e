import unittest
from unittest.mock import Mock, patch

from jarvis_pc.intents import Action, parse_command, command_phrases
from jarvis_pc.actions import Actions, ActionError


class ExpandedCommands(unittest.TestCase):
    def test_volume_variants(self):
        for phrase, kind, number in [
            ('громче на двадцать', 'volume_change', 20),
            ('грочме на 15', 'volume_change', 15),
            ('тише на семь процентов', 'volume_change', -7),
            ('сделай звук тише на десять', 'volume_change', -10),
            ('добавь звук на пять', 'volume_change', 5),
            ('снизь громкость на двадцать один процент', 'volume_change', -21),
            ('звук 40', 'volume_set', 40),
            ('звук на сорок', 'volume_set', 40),
            ('выставь уровень громкости на пятьдесят процентов', 'volume_set', 50),
            ('установи звук на сто процентов', 'volume_set', 100),
            ('сделай звук ноль', 'volume_set', 0),
        ]:
            with self.subTest(phrase=phrase):
                self.assertEqual(parse_command(phrase), Action(kind, number))

    def test_media_variants(self):
        for phrase in ['пауза','поставь на паузу','поставь музыку на паузу','останови видео','приостанови воспроизведение']:
            self.assertEqual(parse_command(phrase), Action('media_pause'))
        for phrase in ['продолжи','продолжить','продолжай','возобнови музыку','сними с паузы','продолжить воспроизведение']:
            self.assertEqual(parse_command(phrase), Action('media_play'))

    def test_rejects_negation_and_multiple_actions(self):
        for phrase in ['не ставь на паузу','не продолжай','пауза и продолжи','звук -20','звук 101','расскажи про звук 50','тише на минус пять']:
            self.assertIsNone(parse_command(phrase),phrase)

    def test_new_words_are_in_voice_grammar(self):
        phrases=command_phrases()
        for phrase in ['звук на сорок','громче на двадцать','пауза','продолжить','поставь музыку на паузу']:
            self.assertIn(phrase,phrases)

    def test_explicit_media_messages_are_distinct(self):
        user32=Mock()
        user32.GetForegroundWindow.return_value=123
        with patch('jarvis_pc.actions.sys.platform','win32'), patch('jarvis_pc.actions._user32',return_value=user32):
            Actions().execute(Action('media_pause'))
            Actions().execute(Action('media_play'))
        calls=user32.SendMessageTimeoutW.call_args_list
        self.assertEqual(calls[0].args[3],47<<16)
        self.assertEqual(calls[1].args[3],46<<16)
        user32.keybd_event.assert_not_called()

    def test_media_timeout_reports_error(self):
        user32=Mock();user32.SendMessageTimeoutW.return_value=0
        with patch('jarvis_pc.actions.sys.platform','win32'), patch('jarvis_pc.actions._user32',return_value=user32):
            with self.assertRaises(ActionError): Actions().execute(Action('media_pause'))
