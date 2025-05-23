"""
Test string utility functions.
"""

from bin.utils.string_utils import clean_html, extract_domain, normalize_text


def test_normalize_text():
    """Test text normalization."""
    # Test basic normalization
    assert normalize_text("  Hello  World  ") == "hello world"

    # Test with special characters
    assert normalize_text("Hello-World!") == "hello world"

    # Test with empty string
    assert normalize_text("") == ""

    # Test with None
    assert normalize_text(None) == ""


def test_clean_html():
    """Test HTML cleaning."""
    # Test basic HTML cleaning
    assert clean_html("<p>Hello World</p>") == "Hello World"

    # Test with nested tags
    assert clean_html("<div><p>Hello <b>World</b></p></div>") == "Hello World"

    # Test with empty HTML
    assert clean_html("") == ""

    # Test with None
    assert clean_html(None) == ""


def test_extract_domain():
    """Test domain extraction."""
    # Test basic domain extraction
    assert extract_domain("user@example.com") == "example.com"

    # Test with subdomain
    assert extract_domain("user@sub.example.com") == "example.com"

    # Test with empty string
    assert extract_domain("") == ""

    # Test with None
    assert extract_domain(None) == ""

    # Test with invalid email
    assert extract_domain("not-an-email") == ""
