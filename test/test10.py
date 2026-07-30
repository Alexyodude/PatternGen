#!/usr/bin/env python3
"""
Multi-panel encoder/decoder tests for PatternGen via Playwright.
Tests long inputs (50, 69, 92, 115 chars) that span 3-5 panels.
"""

import sys
import io
import asyncio
from pathlib import Path

# Ensure UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright")
    print("Then run: playwright install chromium")
    sys.exit(1)


async def test_multi_panel():
    """Run multi-panel encoder/decoder tests."""

    # Test cases: (text, description)
    test_cases = [
        ("THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG 12345", "3 panels (49 chars)"),
        ("ABCDEFGHIJKLMNOPQRSTUVWABCDEFGHIJKLMNOPQRSTUVWABCDEFGHIJKLMNOPQRSTUVW", "3 panels (69 chars)"),
        ("HELLO WORLD " * 7 + "HELLO WO",  # Exactly 92 chars
         "4 panels (92 chars)"),
        ("ABCDE" * 23,  # Exactly 115 chars
         "5 panels (115 chars)"),
    ]

    # Verify exact lengths
    for text, desc in test_cases:
        expected_len = int(desc.split("(")[-1].split()[0])
        actual_len = len(text)
        if actual_len != expected_len:
            print(f"WARNING: {desc} actual length is {actual_len} chars (expected in description: {expected_len})")

    index_path = Path("C:/Users/user/Project/ClaudeCode/PatternGen/index.html")
    index_uri = index_path.as_uri()

    async with async_playwright() as p:
        # Use chromium browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Load the index
            print(f"Loading: {index_uri}")
            await page.goto(index_uri, wait_until='networkidle')
            print("Page loaded successfully.\n")

            # Run tests
            results = []
            for text, description in test_cases:
                result = await test_single_case(page, text, description)
                results.append(result)
                print()

            # Summary
            print("\n" + "="*70)
            print("SUMMARY")
            print("="*70)
            passed = sum(1 for r in results if r['status'] == 'PASS')
            total = len(results)
            print(f"Passed: {passed}/{total}")
            for r in results:
                status_str = r['status']
                desc = r['description']
                print(f"  {status_str}: {desc}")
                if r.get('error'):
                    print(f"    Error: {r['error']}")

        finally:
            await browser.close()


async def test_single_case(page, text, description):
    """Test a single multi-panel case."""
    print(f"Testing: {description}")
    print(f"Text: {text!r}")
    print(f"Length: {len(text)}")

    result = {
        'description': description,
        'text': text,
        'status': 'FAIL',
        'error': None
    }

    try:
        # Set input text and wait for encoding
        await page.fill('#inputText', text)
        await page.wait_for_timeout(500)  # Wait for UI to update

        # Get panel count from UI
        panel_count_text = await page.text_content('#panelCount')
        print(f"Panel count UI: {panel_count_text}")

        # Extract number from "X panels" or "1 panel"
        panel_count = int(panel_count_text.split()[0])
        expected_panels = (len(text) + 22) // 23  # Ceiling division
        print(f"Expected panels: {expected_panels}, Got: {panel_count}")

        if panel_count != expected_panels:
            result['error'] = f"Panel count mismatch: expected {expected_panels}, got {panel_count}"
            return result

        # Encode all 3 variants via page.evaluate()
        # TextEncoder_.encode returns grids; SVGRenderer.render converts to SVG string
        encode_result = await page.evaluate(f"""
        (async () => {{
            const text = {repr(text)};
            const svgs = [];
            for (let variant = 0; variant < 3; variant++) {{
                const grids = TextEncoder_.encode(text, variant);
                const svg = SVGRenderer.render(grids);
                svgs.push(svg);
            }}
            // Store SVGs in window for later retrieval
            window._testSvgs = svgs;
            return {{
                text: text,
                variant_count: svgs.length,
                lengths: svgs.map(s => s.length),
                firstSvgStart: svgs[0] ? svgs[0].substring(0, 100) : 'empty'
            }};
        }})()
        """)

        variant_count = encode_result['variant_count']
        if variant_count != 3:
            result['error'] = f"Expected 3 SVG variants, got {variant_count}"
            return result

        print(f"Encoded 3 variants: lengths {encode_result['lengths']}")
        print(f"First SVG start: {encode_result['firstSvgStart']}")

        # Decode using decode3() with all 3 SVGs (stored in window._testSvgs)
        decode_result = await page.evaluate("""
        (async () => {
            const svgs = window._testSvgs;
            if (!svgs || svgs.length !== 3) {
                return {
                    text: '',
                    valid: false,
                    error: 'SVGs not available or wrong count: ' + (svgs ? svgs.length : 'null'),
                    panelCount: 0
                };
            }
            const decoded = PatternDecoder.decode3(svgs);
            return {
                text: decoded.text,
                valid: decoded.valid,
                error: decoded.error,
                panelCount: decoded.panels ? decoded.panels.length : 0
            };
        })()
        """)

        decoded_text = decode_result['text']
        is_valid = decode_result['valid']
        decode_error = decode_result['error']
        decoded_panels = decode_result['panelCount']

        print(f"Decoded text: {decoded_text!r}")
        print(f"Decoded valid: {is_valid}")
        print(f"Decoded panels: {decoded_panels}")
        if decode_error:
            print(f"Decode error: {decode_error}")

        # Verify
        if not is_valid:
            result['error'] = f"Decode validation failed: {decode_error}"
            return result

        if decoded_text != text:
            result['error'] = f"Text mismatch: expected {text!r}, got {decoded_text!r}"
            return result

        if decoded_panels != panel_count:
            result['error'] = f"Decoded panel count {decoded_panels} != encoded {panel_count}"
            return result

        # All checks passed
        result['status'] = 'PASS'
        print(f"Result: PASS")

    except Exception as e:
        result['error'] = str(e)
        print(f"Exception: {e}")

    return result


if __name__ == '__main__':
    asyncio.run(test_multi_panel())
