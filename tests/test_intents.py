import unittest

from jarvis_pc.intents import Action, command_phrases, normalize_text, parse_command


class IntentTests(unittest.TestCase):
    def test_absolute_volume(self):
        for phrase, value in [
            ("громкость 50", 50),
            ("громкость на пятьдесят процентов", 50),
            ("Установи громкость 0%.", 0),
            ("поставь громкость сто процентов", 100),
            ("сделай громкость двадцать один процент", 21),
            ("громкость девяносто девять", 99),
        ]:
            with self.subTest(phrase=phrase):
                self.assertEqual(parse_command(phrase), Action("volume_set", value))

    def test_relative_volume(self):
        for phrase, value in [
            ("сделай громче", 10), ("тише", -10),
            ("увеличь громкость на 20 процентов", 20),
            ("уменьши громкость на тридцать пять процентов", -35),
            ("громче на два процента", 2), ("убавь громкость", -10),
        ]:
            with self.subTest(phrase=phrase):
                self.assertEqual(parse_command(phrase), Action("volume_change", value))

    def test_desktop_actions(self):
        for phrase, kind in [
            ("выключи звук", "mute"), ("включи звук", "unmute"),
            ("Сверни окно!", "minimize_window"),
            ("сверни все окна", "minimize_all"),
            ("покажи рабочий стол", "minimize_all"),
            ("заблокируй ноутбук", "lock"),
            ("заблокируй ноут", "lock"),
            ("заблокируй компьютер пожалуйста", "lock"),
        ]:
            with self.subTest(phrase=phrase):
                self.assertEqual(parse_command(phrase), Action(kind))

    def test_rejects_negated_or_embedded_commands(self):
        for phrase in [
            "не выключи звук", "не надо сверни окно", "не блокируй компьютер",
            "если скажу заблокируй компьютер", "скажи сверни окно",
            "сверни окно и заблокируй ноутбук", "ты можешь выключи звук",
            "расскажи про громкость 50", "джарвис сверни окно", "",
            "заблокируй", "громкость 101", "громкость -1", "громкость 10.5",
            "громкость десять двадцать", "увеличь громкость на двести процентов",
            "сделай громче на минус пять", "громкость двадцать один два",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIsNone(parse_command(phrase))

    def test_normalization(self):
        self.assertEqual(normalize_text("  СВЁРНИ,   окно! "), "сверни окно")
        self.assertEqual(parse_command("Пожалуйста, сверни окно."), Action("minimize_window"))

    def test_all_canonical_phrases_parse(self):
        phrases = command_phrases()
        self.assertEqual(len(phrases), len(set(phrases)))
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertIsNotNone(parse_command(phrase))


if __name__ == "__main__":
    unittest.main()
