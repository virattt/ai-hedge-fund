import unittest
from unittest.mock import patch, Mock
import sys
import os

class TestCLI(unittest.TestCase):
    def test_cli_script_exists(self):
        # Test that the CLI script can be imported
        try:
            import screen_stocks
            self.assertTrue(True)
        except ImportError:
            self.fail('CLI script screen_stocks.py should exist and be importable')

if __name__ == '__main__':
    unittest.main()
