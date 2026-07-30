#!/usr/bin/env python3

import sys
import io
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

# Fix UTF-8 encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

INDEX = Path(r"C:\Users\user\Project\ClaudeCode\PatternGen\index.html")
INDEX_URI = INDEX.as_uri()

TEST_CASES = [
    "0123456789",
    "9876543210",
    "1111111111",
    "0",
    "9",
    "42",
]

async def run_tests():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        print(f"Loading: {INDEX_URI}")
        await page.goto(INDEX_URI, wait_until="networkidle")

        # Wait for the page to initialize
        await page.wait_for_selector("#inputText", timeout=5000)

        results = []

        for test_input in TEST_CASES:
            print(f"\nTesting: '{test_input}'")

            try:
                # Call encode and decode3 via page.evaluate
                result = await page.evaluate(f"""
                    (async () => {{
                        const text = '{test_input}';
                        const svgs = [];

                        // Encode all 3 variants
                        for (let v = 0; v < 3; v++) {{
                            const grids = TextEncoder_.encode(text, v);
                            const svg = SVGRenderer.render(grids);
                            svgs.push(svg);
                        }}

                        // Decode using all 3 variants
                        const decoded = PatternDecoder.decode3(svgs);

                        // Return result
                        return {{
                            input: text,
                            decoded: decoded,
                            match: decoded === text
                        }};
                    }})()
                """)

                input_text = result['input']
                decoded_result = result['decoded']

                # decode3 returns an object with text and valid properties
                if isinstance(decoded_result, dict):
                    decoded_text = decoded_result.get('text', '')
                else:
                    decoded_text = decoded_result

                match = decoded_text == input_text

                if match:
                    status = "PASS"
                    results.append(("PASS", input_text))
                else:
                    status = "FAIL"
                    results.append(("FAIL", input_text))
                    print(f"  Expected: '{input_text}'")
                    print(f"  Got:      '{decoded_text}'")

                print(f"  {status}")

            except Exception as e:
                print(f"  FAIL (Exception: {e})")
                results.append(("FAIL", test_input))

        await browser.close()

        # Print summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        passed = sum(1 for status, _ in results if status == "PASS")
        failed = sum(1 for status, _ in results if status == "FAIL")

        for status, text in results:
            print(f"  {status}: '{text}'")

        print(f"\nTotal: {passed} passed, {failed} failed out of {len(results)}")
        print("="*60)

if __name__ == "__main__":
    asyncio.run(run_tests())
