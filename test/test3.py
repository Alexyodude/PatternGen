#!/usr/bin/env python3
"""
Test PatternGen encoder/decoder panel boundary conditions using Playwright.
Tests 23, 24, 46, and 22 character inputs to verify panel splitting logic.
"""

import sys
import io
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

# Enable UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def run_tests():
    """Run panel boundary condition tests."""

    # HTML file path
    html_path = Path(r"C:\Users\user\Project\ClaudeCode\PatternGen\index.html")
    file_url = html_path.as_uri()

    print(f"Testing PatternGen encoder/decoder")
    print(f"HTML file: {html_path}")
    print(f"URL: {file_url}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            await page.goto(file_url, wait_until="networkidle")
            print("Page loaded successfully\n")

            # Test cases: (char_count, text, expected_panels, test_name)
            test_cases = [
                (23, "ABCDEFGHIJKLMNOPQRSTUVW", 1, "Exactly 23 chars (1 full panel)"),
                (24, "ABCDEFGHIJKLMNOPQRSTUVWX", 2, "Exactly 24 chars (2 panels)"),
                (46, "ABCDEFGHIJKLMNOPQRSTUVWABCDEFGHIJKLMNOPQRSTUVW", 2, "Exactly 46 chars (2 full panels)"),
                (22, "ABCDEFGHIJKLMNOPQRSTUV", 1, "Exactly 22 chars (1 panel)"),
            ]

            results = []

            for char_count, text, expected_panels, test_name in test_cases:
                print(f"\n{'='*70}")
                print(f"TEST: {test_name}")
                print(f"Input: {text}")
                print(f"Expected panels: {expected_panels}")
                print(f"Length: {len(text)} chars")
                print(f"{'='*70}")

                # Test encode variant 0 and check grids.length
                try:
                    # Encode variant 0
                    variant0_result = await page.evaluate(f"""
                        (() => {{
                            const text = "{text}";

                            // Encode returns grids array
                            const grids = TextEncoder_.encode(text, 0);

                            return {{
                                text_len: text.length,
                                grids_len: grids.length
                            }};
                        }})()
                    """)

                    panel_count_v0 = variant0_result['grids_len']
                    print(f"Variant 0 - Grids length: {panel_count_v0}")

                    if panel_count_v0 == expected_panels:
                        print(f"  PASS: Panel count matches expected ({expected_panels})")
                    else:
                        print(f"  FAIL: Panel count {panel_count_v0} != expected {expected_panels}")
                        results.append((test_name, "FAIL", f"Panel count mismatch: {panel_count_v0} vs {expected_panels}"))
                        continue

                except Exception as e:
                    print(f"  FAIL: Error during variant 0 encoding: {e}")
                    results.append((test_name, "FAIL", f"Variant 0 error: {e}"))
                    continue

                # Test full encode (all 3 variants) and decode
                try:
                    full_test_result = await page.evaluate(f"""
                        (() => {{
                            const text = "{text}";

                            // Encode all 3 variants
                            const svgs = [];
                            for (let v = 0; v < 3; v++) {{
                                const grids = TextEncoder_.encode(text, v);
                                const svg = SVGRenderer.render(grids);
                                svgs.push(svg);
                            }}

                            // Decode
                            const decoded = PatternDecoder.decode3(svgs);

                            return {{
                                original: text,
                                decoded: decoded,
                                match: text === decoded,
                                svg_count: svgs.length
                            }};
                        }})()
                    """)

                    original = full_test_result['original']
                    decoded_obj = full_test_result['decoded']
                    decoded = decoded_obj['text'] if isinstance(decoded_obj, dict) else str(decoded_obj)
                    svg_count = full_test_result['svg_count']

                    print(f"Encoded variants: {svg_count}")
                    print(f"Original: '{original}'")
                    print(f"Decoded:  '{decoded}'")

                    match = original == decoded
                    if match:
                        print(f"  PASS: Text matches after encode/decode")
                        results.append((test_name, "PASS", "Text correctly round-tripped"))
                    else:
                        print(f"  FAIL: Decoded text does not match original")
                        results.append((test_name, "FAIL", f"Mismatch: '{original}' != '{decoded}'"))

                except Exception as e:
                    print(f"  FAIL: Error during full encode/decode: {e}")
                    results.append((test_name, "FAIL", f"Encode/decode error: {e}"))

            # Summary
            print(f"\n{'='*70}")
            print(f"SUMMARY")
            print(f"{'='*70}")
            for test_name, status, message in results:
                status_str = f"[{status}]"
                print(f"{status_str:8} {test_name:40} {message}")

            passed = sum(1 for _, s, _ in results if s == "PASS")
            total = len(results)
            print(f"\nTotal: {passed}/{total} tests passed")

            if passed == total:
                print("\nAll tests PASSED!")
                return 0
            else:
                print(f"\n{total - passed} test(s) FAILED")
                return 1

        finally:
            await browser.close()

if __name__ == "__main__":
    exit_code = asyncio.run(run_tests())
    sys.exit(exit_code)
