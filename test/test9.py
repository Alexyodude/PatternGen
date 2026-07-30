#!/usr/bin/env python3
"""
Test PatternGen variant diversity using Playwright.

Tests that for each input text:
1. All 3 variant SVGs are different
2. All 3 variants decode to the same text via decode3()
"""

import sys
import io
import asyncio
from pathlib import Path

# Fix encoding for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: playwright not installed. Install with: pip install playwright", file=sys.stderr)
    sys.exit(1)

INDEX = Path(r"C:\Users\user\Project\ClaudeCode\PatternGen\index.html")
TEST_INPUTS = [
    "HELLO WORLD",
    "12345",
    "A",
    "THE QUICK BROWN FOX JUM",
]


async def test_variant_diversity():
    """Test variant diversity for each input."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Load the encoder page
        index_uri = INDEX.as_uri()
        await page.goto(index_uri)

        # Wait for page to be ready
        await page.wait_for_load_state("networkidle")

        # Wait for the TextEncoder_ class to be available
        await page.wait_for_function("() => typeof TextEncoder_ !== 'undefined'")

        results = []

        for input_text in TEST_INPUTS:
            print(f"\nTesting: {input_text!r}")

            try:
                # Generate SVGs for all 3 variants using page.evaluate()
                svg_data = await page.evaluate(
                    """(input) => {
                        const svgs = [];
                        try {
                            for (let variant = 0; variant < 3; variant++) {
                                const grids = TextEncoder_.encode(input, variant);
                                const svg = SVGRenderer.render(grids);
                                svgs.push(svg);
                            }
                            return { svgs: svgs };
                        } catch (e) {
                            return { error: 'Encoding failed: ' + e.message };
                        }
                    }""",
                    input_text,
                )

                if "error" in svg_data:
                    print(f"  FAIL: {svg_data['error']}")
                    results.append(("FAIL", input_text, svg_data["error"]))
                    continue

                svgs = svg_data["svgs"]

                # Verify all 3 SVGs are different
                unique_svgs = set(svgs)
                if len(unique_svgs) != 3:
                    print(f"  FAIL: Not all variants are different (unique count: {len(unique_svgs)})")
                    results.append(("FAIL", input_text, f"Only {len(unique_svgs)} unique SVGs"))
                    continue

                print(f"  ??All 3 variants are different")

                # Verify all 3 decode to the same text via decode3
                decoded = await page.evaluate(
                    """(svgs) => {
                        const result = PatternDecoder.decode3(svgs);
                        return result;
                    }""",
                    svgs,
                )

                if not decoded.get("valid"):
                    print(f"  FAIL: decode3 returned invalid result: {decoded}")
                    results.append(("FAIL", input_text, f"decode3 invalid: {decoded}"))
                    continue

                decoded_text = decoded.get("text", "")
                expected_text = input_text.upper()

                if decoded_text == expected_text:
                    print(f"  ??All 3 variants decode to: {decoded_text!r}")
                    results.append(("PASS", input_text, decoded_text))
                else:
                    print(
                        f"  FAIL: Decoded text mismatch. Expected {expected_text!r}, got {decoded_text!r}"
                    )
                    results.append(
                        ("FAIL", input_text, f"Expected {expected_text!r}, got {decoded_text!r}")
                    )

            except Exception as e:
                print(f"  FAIL: Exception: {e}")
                results.append(("FAIL", input_text, str(e)))

        await browser.close()

        # Print summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)

        passes = sum(1 for status, _, _ in results if status == "PASS")
        total = len(results)

        for status, input_text, detail in results:
            symbol = "PASS" if status == "PASS" else "FAIL"
            print(f"{symbol}: {input_text!r}")
            if status == "FAIL":
                print(f"    Reason: {detail}")

        print(f"\nPassed: {passes}/{total}")

        if passes == total:
            print("\nALL TESTS PASSED")
            return 0
        else:
            print(f"\n{total - passes} TEST(S) FAILED")
            return 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_variant_diversity())
    sys.exit(exit_code)
