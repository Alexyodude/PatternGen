#!/usr/bin/env python3
import sys
import io
import asyncio
from pathlib import Path

# Set up UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Playwright imports
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright")
    sys.exit(1)


async def test_smooth_corners():
    """
    Test that smoothCorners keys are consistent across variants 0, 1, 2.
    For each input text, encode with all 3 variants and verify the keys
    in grid.smoothCorners are identical.
    """
    test_inputs = [
        "HELLO WORLD",
        "12345",
        "ABCDEFGHIJKLM",
        "THE QUICK BROWN FOX JUM"
    ]

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Load the index.html file
        index_path = Path(r"C:\Users\user\Project\ClaudeCode\PatternGen\index.html")
        file_uri = index_path.as_uri()
        await page.goto(file_uri)

        # Wait for page to fully load
        await page.wait_for_load_state('networkidle')

        for test_input in test_inputs:
            print(f"\nTesting: {test_input!r}")

            # Encode with all 3 variants and extract smoothCorners keys
            variant_corners = {}

            for variant in [0, 1, 2]:
                try:
                    # Call TextEncoder_.encode(text, variant) to get grids
                    result = await page.evaluate(
                        f"""
                        () => {{
                            const text = {repr(test_input)};
                            const variant = {variant};
                            const grids = TextEncoder_.encode(text, variant);
                            return grids.map(grid => {{
                                const keys = Array.from(grid.smoothCorners.keys()).sort();
                                return keys;
                            }});
                        }}
                        """
                    )
                    variant_corners[variant] = result
                    print(f"  Variant {variant}: {len(result)} panels, {sum(len(panel) for panel in result)} total smoothCorners")
                    if result:
                        for panel_idx, panel_keys in enumerate(result):
                            if panel_keys:
                                print(f"    Panel {panel_idx}: {panel_keys}")

                except Exception as e:
                    print(f"  ERROR encoding with variant {variant}: {e}")
                    variant_corners[variant] = None

            # Verify all 3 variants have the same smoothCorners keys
            corners_v0 = variant_corners.get(0)
            corners_v1 = variant_corners.get(1)
            corners_v2 = variant_corners.get(2)

            if corners_v0 is None or corners_v1 is None or corners_v2 is None:
                status = "FAIL (encoding error)"
                print(f"  Result: {status}")
                results.append((test_input, status))
                continue

            # Compare all three variants
            if corners_v0 == corners_v1 == corners_v2:
                status = "PASS"
                print(f"  Result: {status}")
                results.append((test_input, status))
            else:
                status = "FAIL (variants differ)"
                print(f"  Result: {status}")
                print(f"    V0: {corners_v0}")
                print(f"    V1: {corners_v1}")
                print(f"    V2: {corners_v2}")
                results.append((test_input, status))

        await browser.close()

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for test_input, status in results:
        print(f"{test_input:30s} | {status}")

    # Exit with success only if all pass
    all_pass = all(status == "PASS" for _, status in results)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    asyncio.run(test_smooth_corners())
