#!/usr/bin/env python3
"""
Test checksum validation in PatternGen encoder using Playwright.

Tests:
1. Compute expected checksum manually for "HELLO WORLD"
2. Verify TextEncoder_.computeChecksum matches
3. Test 5 different inputs with correct checksum verification
4. Verify that corrupting a bit in the encoded array causes checksum mismatch
"""

import sys
import io
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

# Set up UTF-8 encoding for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Character set from index.html
CHARSET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,-!?\':'

def char_to_code(ch):
    """Convert character to code (0-43)."""
    idx = CHARSET.find(ch.upper())
    return idx if idx >= 0 else -1

def compute_checksum_manual(text):
    """Manually compute checksum: XOR all char codes & 0x7."""
    text_upper = text.upper()
    xor_val = 0
    for ch in text_upper:
        code = char_to_code(ch)
        if code < 0:
            raise ValueError(f"Invalid character: {ch}")
        xor_val ^= code
    return xor_val & 0x7

def print_section(title):
    """Print a test section header."""
    print(f"\n{'='*70}")
    print(f" {title}")
    print(f"{'='*70}")

def print_test(test_num, description, passed):
    """Print a test result."""
    status = "??PASS" if passed else "??FAIL"
    print(f"[Test {test_num}] {status}: {description}")

async def main():
    """Main test function using Playwright."""

    print_section("PatternGen Checksum Validation Tests")

    index_path = Path('C:/Users/user/Project/ClaudeCode/PatternGen/index.html')
    if not index_path.exists():
        print("ERROR: index.html not found at", index_path)
        sys.exit(1)

    index_uri = index_path.as_uri()
    print(f"Loading: {index_uri}\n")

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Load the page with increased timeout
        try:
            await page.goto(index_uri, wait_until='domcontentloaded')
        except Exception as e:
            print(f"ERROR: Failed to load page: {e}")
            await browser.close()
            sys.exit(1)

        # Wait for the page to be ready - give scripts time to execute
        import time
        for attempt in range(30):  # Try for up to 30 seconds
            has_encoder = await page.evaluate('() => typeof window.TextEncoder_ !== "undefined"')
            if has_encoder:
                break
            await page.wait_for_timeout(1000)

        if not has_encoder:
            print(f"ERROR: TextEncoder_ not available after 30 seconds")
            await browser.close()
            sys.exit(1)

        test_num = 1
        results = []

        # ??? Test 1: Manual checksum for "HELLO WORLD" ???
        print_section("Test 1: Manual Checksum Computation")
        test_text = "HELLO WORLD"
        manual_checksum = compute_checksum_manual(test_text)

        print(f"Text: '{test_text}'")
        print(f"Characters: {' '.join(test_text)}")
        print(f"Character codes:")
        for ch in test_text:
            code = char_to_code(ch)
            print(f"  '{ch}' ??{code:2d} ({bin(code)[2:].zfill(6)})")

        # Compute XOR manually
        xor_val = 0
        for ch in test_text:
            code = char_to_code(ch)
            xor_val ^= code
            print(f"    XOR so far: {xor_val:2d} ({bin(xor_val)[2:].zfill(6)})")

        print(f"\nFinal XOR: {xor_val}")
        print(f"Masked (& 0x7): {manual_checksum}")

        test_num += 1

        # ??? Test 2: Verify TextEncoder_.computeChecksum ???
        print_section("Test 2: Verify TextEncoder_.computeChecksum")

        js_code = f"""
        (function() {{
            const text = '{test_text}';
            const charCodes = [];
            for (const ch of text) {{
                const idx = window.CHARSET.indexOf(ch);
                if (idx >= 0) charCodes.push(idx);
            }}
            return window.TextEncoder_.computeChecksum(charCodes);
        }})()
        """

        js_checksum = await page.evaluate(js_code)

        print(f"Expected (manual): {manual_checksum}")
        print(f"Actual (JS):       {js_checksum}")

        passed = (manual_checksum == js_checksum)
        print_test(test_num, f"JS computeChecksum matches manual for '{test_text}'", passed)
        results.append(passed)
        test_num += 1

        # ??? Test 3-7: Test 5 different inputs ???
        print_section("Tests 3-7: Checksum Validation for 5 Different Inputs")

        test_inputs = [
            "HELLO",
            "TEST",
            "HELLO WORLD",
            "ABC123",
            "PATTERN"
        ]

        for test_input in test_inputs:
            manual = compute_checksum_manual(test_input)

            js_code = f"""
            (function() {{
                const text = '{test_input}';
                const charCodes = [];
                for (const ch of text) {{
                    const idx = window.CHARSET.indexOf(ch);
                    if (idx >= 0) charCodes.push(idx);
                }}
                return window.TextEncoder_.computeChecksum(charCodes);
            }})()
            """

            js_result = await page.evaluate(js_code)

            passed = (manual == js_result)
            print_test(test_num, f"Checksum for '{test_input}': manual={manual}, js={js_result}", passed)
            results.append(passed)
            test_num += 1

        # ??? Test 8: Bit corruption detection ???
        print_section("Test 8: Bit Corruption Detection")

        test_input = "HELLO"

        print(f"Test input: '{test_input}'")
        print("\nStep 1: Encode text and get the bit array")

        js_code = f"""
        (function() {{
            try {{
                const text = '{test_input}';
                const upper = text.toUpperCase();
                const charCodes = [];
                for (const ch of upper) {{
                    const idx = window.CHARSET.indexOf(ch);
                    if (idx >= 0) charCodes.push(idx);
                }}

                // Compute checksum BEFORE corruption
                const originalChecksum = window.TextEncoder_.computeChecksum(charCodes);

                // Now simulate bit corruption in the encoded data
                // Get the bit array that would be created
                const dataBits = new Array(148).fill(0); // TOTAL_BITS = 148
                let pos = 0;

                // 5-bit length
                const len = charCodes.length;
                for (let b = 4; b >= 0; b--) dataBits[pos++] = (len >> b) & 1;

                // 3-bit checksum
                const chk = originalChecksum;
                for (let b = 2; b >= 0; b--) dataBits[pos++] = (chk >> b) & 1;

                // 6-bit character codes
                for (const code of charCodes) {{
                    for (let b = 5; b >= 0; b--) dataBits[pos++] = (code >> b) & 1;
                }}

                // Flip bit 13 (rightmost bit of first character code)
                // 'H' = 0b000111 = 7. Flipping rightmost bit: 0b000110 = 6
                // 7 XOR remaining = 5, so remaining = 2
                // 6 XOR remaining = 6 XOR 2 = 4
                // 4 & 0x7 = 4, which is different from 5!
                const corruptPos = 13;
                dataBits[corruptPos] = dataBits[corruptPos] === 0 ? 1 : 0;

                // Now try to read it back
                // Extract the length and checksum from corrupted bits
                let bitPos = 0;

                // Read 5-bit length
                let decodedLen = 0;
                for (let i = 0; i < 5; i++) {{
                    decodedLen = (decodedLen << 1) | dataBits[bitPos++];
                }}

                // Read 3-bit checksum
                let decodedChecksum = 0;
                for (let i = 0; i < 3; i++) {{
                    decodedChecksum = (decodedChecksum << 1) | dataBits[bitPos++];
                }}

                // Read character codes
                const decodedCharCodes = [];
                for (let i = 0; i < decodedLen; i++) {{
                    let code = 0;
                    for (let b = 0; b < 6; b++) {{
                        code = (code << 1) | dataBits[bitPos++];
                    }}
                    decodedCharCodes.push(code);
                }}

                // DEBUG: print the decoded character codes and their XOR
                let debugXor = 0;
                for (const c of decodedCharCodes) {{
                    debugXor ^= c;
                }}

                // Compute checksum of decoded characters
                const verifyChecksum = window.TextEncoder_.computeChecksum(decodedCharCodes);

                // Show the corrupted character code
                const originalFirstChar = charCodes[0];
                const corruptedFirstChar = decodedCharCodes[0];

                // Check if the corruption caused a checksum mismatch
                // The decodedChecksum comes from the header (which is NOT corrupted)
                // The verifyChecksum is computed from the corrupted character codes
                // They should NOT match if corruption was successful
                const corruptionDetected = (decodedChecksum !== verifyChecksum);

                return {{
                    originalChecksum: originalChecksum,
                    originalFirstCharCode: originalFirstChar,
                    corruptedFirstCharCode: corruptedFirstChar,
                    allDecodedCharCodes: decodedCharCodes,
                    decodedChecksum: decodedChecksum,
                    verifyChecksum: verifyChecksum,
                    debugXor: debugXor,
                    corruptionDetected: corruptionDetected,
                    corruption: {{
                        position: corruptPos,
                        afterFlip: dataBits[corruptPos]
                    }}
                }};
            }} catch (e) {{
                return {{ error: e.message }};
            }}
        }})()
        """

        result = await page.evaluate(js_code)

        if 'error' in result:
            print(f"ERROR: {result['error']}")
            passed = False
        else:
            print(f"\nOriginal first character code: {result['originalFirstCharCode']}")
            print(f"Corrupted first character code: {result['corruptedFirstCharCode']}")
            print(f"All decoded character codes: {result['allDecodedCharCodes']}")
            print(f"Original checksum (before corruption): {result['originalChecksum']}")
            print(f"Decoded checksum (from header):        {result['decodedChecksum']}")
            print(f"Computed checksum (from corrupted data): {result['verifyChecksum']}")
            print(f"Debug XOR of decoded chars: {result['debugXor']}")
            print(f"Corruption at bit position {result['corruption']['position']}: "
                  f"bit flipped to {result['corruption']['afterFlip']}")

            # The key test: checksum mismatch should be detected
            # After corruption of a character code, the verify checksum should NOT match
            # the header checksum (which is uncorrupted)
            passed = result['corruptionDetected']

            print(f"\nCharacter code changed: {result['originalFirstCharCode'] != result['corruptedFirstCharCode']}")
            print(f"Checksum mismatch detected: {result['corruptionDetected']}")

        print_test(test_num, f"Bit corruption in '{test_input}' causes checksum mismatch", passed)
        results.append(passed)
        test_num += 1

        # ??? Summary ???
        print_section("Summary")
        total_tests = len(results)
        passed_tests = sum(results)

        print(f"Total tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")

        if all(results):
            print("\n??All tests PASSED!")
        else:
            print("\n??Some tests FAILED")
            sys.exit(1)

        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
