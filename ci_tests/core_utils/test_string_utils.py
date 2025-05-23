"""
Test string utility functions.
"""

import os
import sys
import unittest


class TestStringUtils(unittest.TestCase):
    """Test cases converted from pytest file: test_string_utils.py"""

    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        # Add the project root to sys.path
        project_root = os.path.abspath(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        print(f"Python path: {sys.path}")

    def setUp(self):
        """Set up test case."""
        pass

    def tearDown(self):
        """Tear down test case."""
        pass

    def test_normalize_text(self):
        """Test text normalization."""
        from bin.utils.string_utils import normalize_text

        # Test basic normalization
        self.assertEqual(normalize_text("  Hello  World  "), "hello world")

        # Test with special characters
        self.assertEqual(normalize_text("Hello-World!"), "hello world")

        # Test with empty string
        self.assertEqual(normalize_text(""), "")

        # Test with None
        self.assertEqual(normalize_text(None), "")

    def test_clean_html(self):
        """Test HTML cleaning."""
        from bin.utils.string_utils import clean_html

        # Test basic HTML cleaning
        self.assertEqual(clean_html("<p>Hello World</p>"), "Hello World")

        # Test with nested tags
        self.assertEqual(
            clean_html("<div><p>Hello <b>World</b></p></div>"), "Hello World"
        )

        # Test with empty HTML
        self.assertEqual(clean_html(""), "")

        # Test with None
        self.assertEqual(clean_html(None), "")

    def test_extract_domain(self):
        """Test domain extraction."""
        from bin.utils.string_utils import extract_domain

        # Test basic domain extraction
        self.assertEqual(extract_domain("user@example.com"), "example.com")

        # Test with subdomain
        self.assertEqual(extract_domain("user@sub.example.com"), "example.com")

        # Test with empty string
        self.assertEqual(extract_domain(""), "")

        # Test with None
        self.assertEqual(extract_domain(None), "")

        # Test with invalid email
        self.assertEqual(extract_domain("not-an-email"), "")


if __name__ == "__main__":
    unittest.main()
