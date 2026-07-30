#!/usr/bin/env python3
"""
Determinism test for PatternGen encoder using Playwright.
Tests that the same input + variant always produces identical SVG output.
"""

import asyncio
import sys
import io
from pathlib import Path

# Force UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("FAIL: playwright not installed. Install with: pip install playwright")
    sys.exit(1)


async def test_determinism():
    """Test determinism by encoding the same input 5 times and comparing outputs."""

    # Test inputs
    test_inputs = [
        "HELLO",
        "TEST 123",
        "A.B,C-D!E?F'G:H"
    ]

    # Variants to test
    variants = [0, 1, 2]

    # Get path to index.html
    index_path = Path(r"C:\Users\user\Project\ClaudeCode\PatternGen\index.html")

    if not index_path.exists():
        print(f"FAIL: index.html not found at {index_path}")
        return False

    index_uri = index_path.as_uri()
    print(f"Loading: {index_uri}")

    all_passed = True

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Navigate to the page
            await page.goto(index_uri, wait_until="load")
            print("Page loaded successfully\n")

            # Run tests
            for input_text in test_inputs:
                print(f"Testing input: '{input_text}'")

                for variant in variants:
                    # Encode and render 5 times
                    svgs = []
                    for attempt in range(5):
                        svg = await page.evaluate(
                            """
                            ({text, variant}) => {
                                const grids = TextEncoder_.encode(text, variant);
                                return SVGRenderer.render(grids);
                            }
                            """,
                            {"text": input_text, "variant": variant}
                        )
                        svgs.append(svg)

                    # Check if all 5 SVGs are identical
                    first_svg = svgs[0]
                    all_identical = all(s == first_svg for s in svgs)

                    if all_identical:
                        print(f"  Variant {variant}: PASS (5/5 identical)")
                    else:
                        print(f"  Variant {variant}: FAIL (SVGs differ)")
                        all_passed = False

                        # Show which ones differ
                        for i in range(1, 5):
                            if svgs[i] != first_svg:
                                print(f"    Attempt {i} differs from attempt 0")

                print()

        except Exception as e:
            print(f"FAIL: Error during test execution: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False

        finally:
            await context.close()
            await browser.close()

    return all_passed


async def main():
    """Main entry point."""
    print("=" * 70)
    print("PatternGen Determinism Test")
    print("=" * 70 + "\n")

    success = await test_determinism()

    print("=" * 70)
    if success:
        print("RESULT: PASS - All 5 renders match for every input+variant combo")
        print("=" * 70)
        sys.exit(0)
    else:
        print("RESULT: FAIL - Some renders did not match")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
