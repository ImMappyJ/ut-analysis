"""Synthetic catalog tests; no services or credentials."""
import unittest


def reserve(stock, quantity):
    if quantity <= 0 or quantity > stock:
        raise ValueError("invalid quantity")
    return stock - quantity


class InventoryTests(unittest.TestCase):
    def test_reserve_valid(self):
        self.assertEqual(reserve(8, 3), 5)

    def test_reject_invalid(self):
        for quantity in (0, -1, 9):
            with self.subTest(quantity=quantity):
                with self.assertRaises(ValueError):
                    reserve(8, quantity)

    def test_catalog_empty(self):
        self.assertEqual([], [])


if __name__ == "__main__":
    unittest.main()
