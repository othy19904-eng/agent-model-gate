import unittest

from calc import add


class CalcTests(unittest.TestCase):
    def test_add_positive_numbers(self):
        self.assertEqual(add(2, 3), 5)

    def test_add_negative_number(self):
        self.assertEqual(add(10, -4), 6)


if __name__ == "__main__":
    unittest.main()
