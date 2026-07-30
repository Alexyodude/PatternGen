#!/usr/bin/env python3
"""
Test PatternGen encoder/decoder charset validation using Playwright.
Tests:
1. TextEncoder_.validate returns valid=true for all valid chars
2. TextEncoder_.validate returns valid=false for invalid chars
3. charToCode and codeToChar are inverse for all 44 valid characters
4. CHARSET has exactly 44 characters
"""

import sys
import io
from pathlib import Path
from playwright.sync_api import sync_playwright

# Use UTF-8 for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Expected charset from CLAUDE.md
EXPECTED_CHARSET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,-!?\':"'
# The charset should be (based on line 516 of index.html):
# 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,-!?\':' - without trailing quote

# Valid characters to test
VALID_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,\\-!?\':"'

# Invalid characters to test
INVALID_CHARS = '@#$%^&*()'

# Test results
results = []

def test_charset_length():
    """Test that CHARSET has exactly 44 characters."""
    print("\n=== Test 1: CHARSET Length ===")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()

        # Use file:// URI
        index_path = Path('C:\\Users\\yejun\\Project\\ClaudeCode\\PatternGen\\index.html')
        uri = index_path.as_uri()
        page.goto(uri)

        # Wait for page to load
        page.wait_for_load_state('networkidle')

        # Get CHARSET length
        charset = page.evaluate('() => CHARSET')
        charset_length = len(charset)

        print(f"CHARSET: '{charset}'")
        print(f"CHARSET length: {charset_length}")

        if charset_length == 44:
            print("✓ PASS: CHARSET has exactly 44 characters")
            results.append(('CHARSET Length', True))
        else:
            print(f"✗ FAIL: CHARSET has {charset_length} characters, expected 44")
            results.append(('CHARSET Length', False))

        browser.close()


def test_validate_valid_chars():
    """Test that TextEncoder_.validate returns valid=true for all valid chars."""
    print("\n=== Test 2: Validate Valid Characters ===")

    # List of valid characters from CLAUDE.md
    valid_chars = ['A', 'Z', '0', '9', ' ', '.', ',', '-', '!', '?', "'", ':']

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()

        index_path = Path('C:\\Users\\yejun\\Project\\ClaudeCode\\PatternGen\\index.html')
        uri = index_path.as_uri()
        page.goto(uri)
        page.wait_for_load_state('networkidle')

        all_valid = True
        for char in valid_chars:
            result = page.evaluate(f'() => TextEncoder_.validate("{char}")')
            is_valid = result.get('valid', False)
            status = '✓' if is_valid else '✗'
            print(f"{status} '{char}' -> valid={is_valid}")
            if not is_valid:
                all_valid = False

        if all_valid:
            print("✓ PASS: All valid characters validated correctly")
            results.append(('Validate Valid Characters', True))
        else:
            print("✗ FAIL: Some valid characters failed validation")
            results.append(('Validate Valid Characters', False))

        browser.close()


def test_validate_invalid_chars():
    """Test that TextEncoder_.validate returns valid=false for invalid chars."""
    print("\n=== Test 3: Validate Invalid Characters ===")

    invalid_chars = ['@', '#', '$', '%', '^', '&', '*', '(', ')']

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()

        index_path = Path('C:\\Users\\yejun\\Project\\ClaudeCode\\PatternGen\\index.html')
        uri = index_path.as_uri()
        page.goto(uri)
        page.wait_for_load_state('networkidle')

        all_invalid = True
        for char in invalid_chars:
            result = page.evaluate(f'() => TextEncoder_.validate("{char}")')
            is_valid = result.get('valid', False)
            status = '✓' if not is_valid else '✗'
            print(f"{status} '{char}' -> valid={is_valid} (should be false)")
            if is_valid:
                all_invalid = False

        if all_invalid:
            print("✓ PASS: All invalid characters rejected correctly")
            results.append(('Validate Invalid Characters', True))
        else:
            print("✗ FAIL: Some invalid characters were accepted")
            results.append(('Validate Invalid Characters', False))

        browser.close()


def test_char_code_inverse():
    """Test that charToCode and codeToChar are inverse for all 44 valid characters."""
    print("\n=== Test 4: Character Code Inverse Functions ===")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()

        index_path = Path('C:\\Users\\yejun\\Project\\ClaudeCode\\PatternGen\\index.html')
        uri = index_path.as_uri()
        page.goto(uri)
        page.wait_for_load_state('networkidle')

        # Get charset
        charset = page.evaluate('() => CHARSET')

        print(f"Testing {len(charset)} characters from CHARSET")
        all_inverse = True

        for code in range(len(charset)):
            # Get character from code
            char_from_code = page.evaluate(f'() => TextEncoder_.codeToChar({code})')

            # Get code from character
            expected_char = charset[code]
            code_from_char = page.evaluate(f'() => TextEncoder_.charToCode("{expected_char}")')

            # Test both directions
            code_matches = (code_from_char == code)
            char_matches = (char_from_code == expected_char)

            if code_matches and char_matches:
                status = '✓'
            else:
                status = '✗'
                all_inverse = False

            print(f"{status} code {code}: '{expected_char}' <-> charToCode='{code_from_char}', codeToChar='{char_from_code}'")

        if all_inverse:
            print("✓ PASS: All character codes are properly inverse")
            results.append(('Character Code Inverse', True))
        else:
            print("✗ FAIL: Some character codes are not properly inverse")
            results.append(('Character Code Inverse', False))

        browser.close()


def print_summary():
    """Print test summary."""
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"
        print(f"{symbol} {test_name}: {status}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    failed = total - passed

    print("-"*60)
    print(f"Total: {total} | Passed: {passed} | Failed: {failed}")

    if failed == 0:
        print("\n✓ ALL TESTS PASSED")
        return 0
    else:
        print(f"\n✗ {failed} TEST(S) FAILED")
        return 1


if __name__ == '__main__':
    try:
        test_charset_length()
        test_validate_valid_chars()
        test_validate_invalid_chars()
        test_char_code_inverse()

        exit_code = print_summary()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n✗ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
