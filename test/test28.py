#!/usr/bin/env python3
"""
Test PatternGen encoder/decoder with Playwright.
Tests various random-style inputs via page.evaluate().
"""

import asyncio
import sys
import io
from pathlib import Path

# Set up UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Playwright imports
from playwright.async_api import async_playwright


async def test_patterngen():
    """Test PatternGen with various inputs."""

    test_inputs = [
        "XYZZY",
        "QWERTY",
        "FOO BAR BAZ",
        "LOREM IPSUM",
        "PACK MY BOX",
        "JINXED",
        "WALTZ",
        "QUIZ",
    ]

    # Convert file path to file:// URI
    index_path = Path("C:\\Users\\yejun\\Project\\ClaudeCode\\PatternGen\\index.html")
    index_uri = index_path.as_uri()

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Navigate to the app
        print(f"Loading {index_uri}...")
        await page.goto(index_uri, wait_until="networkidle")

        # Wait for the app to be ready
        await page.wait_for_function("() => typeof PatternDecoder !== 'undefined'")
        print("App loaded successfully.\n")

        results = []

        for test_input in test_inputs:
            test_upper = test_input.upper()
            print(f"Testing: '{test_input}'")

            try:
                # Call the encoder and decoder via page.evaluate()
                result = await page.evaluate(f"""
                async (inputText) => {{
                    const svgs = [];

                    // Encode all 3 variants
                    for (let variant = 0; variant < 3; variant++) {{
                        const grids = TextEncoder_.encode(inputText, variant);
                        const svg = SVGRenderer.render(grids);
                        svgs.push(svg);
                    }}

                    // Decode using all 3 variants
                    const decoded = PatternDecoder.decode3(svgs);

                    return {{
                        input: inputText,
                        decodedText: decoded.text,
                        decodedValid: decoded.valid,
                        svgs: svgs.map((s, i) => ({{
                            variant: i,
                            length: s.length
                        }})),
                        success: decoded.valid && decoded.text === inputText.toUpperCase()
                    }};
                }}
                """, test_upper)

                # Print result
                if result['success']:
                    print(f"  PASS: Decoded correctly to '{result['decodedText']}'")
                    results.append((test_input, True))
                else:
                    print(f"  FAIL: Expected '{test_upper}', got '{result['decodedText']}' (valid={result['decodedValid']})")
                    results.append((test_input, False))

                # Print variant info
                for variant_info in result['svgs']:
                    print(f"    Variant {variant_info['variant']}: {variant_info['length']} chars")

            except Exception as e:
                print(f"  ERROR: {e}")
                results.append((test_input, False))

            print()

        await browser.close()

    # Summary
    print("=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_input, success in results:
        status = "PASS" if success else "FAIL"
        print(f"{status}: {test_input}")

    print(f"\nTotal: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(test_patterngen())
    sys.exit(0 if success else 1)
