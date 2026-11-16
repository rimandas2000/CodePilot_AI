import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from language_detection import detect_language


class LanguageDetectionTests(unittest.TestCase):
    def test_common_languages(self):
        examples = {
            "C": '#include <stdio.h>\nint main(void) { printf("Hello"); return 0; }',
            "C++": '#include <iostream>\nint main() { std::cout << "Hello"; }',
            "Python": 'def hello():\n    print("Hello")',
            "Java": 'public class Main { public static void main(String[] args) { System.out.println("Hello"); } }',
            "JavaScript": 'const greeting = "Hello"; console.log(greeting);',
        }
        for language, code in examples.items():
            with self.subTest(language=language):
                self.assertEqual(detect_language(code), language)

    def test_unrecognizable_code_is_not_guessed(self):
        self.assertIsNone(detect_language(''))
        self.assertIsNone(detect_language('x = 5'))

    def test_file_extensions(self):
        self.assertEqual(detect_language('hello', 'main.c'), 'C')
        self.assertEqual(detect_language('hello', 'main.cpp'), 'C++')


if __name__ == '__main__':
    unittest.main()
