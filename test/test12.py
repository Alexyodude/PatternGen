#!/usr/bin/env python3
"""
Test PatternGen encoder/decoder SVG structure via Playwright.

For "HELLO WORLD" variant 0:
1. Parse SVG, count total path elements
2. Count paths with C (bezier) commands
3. Count standalone bezier paths (M+C only, no H/V)
4. Count inline bezier paths (C within H/V chain)
5. Verify inline beziers > 0
6. Verify all paths have valid d attributes
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
    print("ERROR: playwright not installed. Run: pip install playwright")
    sys.exit(1)


def parse_svg_paths(svg_string: str) -> list:
    """
    Parse SVG string and extract all <path> elements with their d attributes.
    Returns list of dicts with 'element' (str) and 'd' (str) keys.
    """
    paths = []
    import re

    # Find all <path d="..." /> or <path ... d="..."> patterns
    # Look for the d attribute specifically
    path_pattern = r'<path[^>]*\sd="([^"]*)"[^>]*/?>'
    matches = re.finditer(path_pattern, svg_string)

    for match in matches:
        d_attr = match.group(1)
        paths.append({
            'element': match.group(0),
            'd': d_attr
        })

    return paths


def analyze_path_commands(d_attr: str) -> dict:
    """
    Analyze a path's d attribute.
    Returns dict with:
    - has_bezier: True if has C command
    - has_h_or_v: True if has H or V commands
    - is_standalone_bezier: True if M+C only (no H/V)
    - is_inline_bezier: True if has both C and H/V
    """
    import re

    # Normalize whitespace and extract command letters
    d_normalized = d_attr.replace('\n', ' ').strip()

    # Find all command letters (M, L, H, V, C, S, Q, T, A, Z)
    commands = set(re.findall(r'[MLHVCSQTAZ]', d_normalized))

    has_c = 'C' in commands or 'S' in commands  # C or S (smooth bezier)
    has_h_or_v = 'H' in commands or 'V' in commands
    has_m = 'M' in commands

    is_standalone = has_c and not has_h_or_v  # M+C only
    is_inline = has_c and has_h_or_v  # C within H/V chain

    return {
        'has_bezier': has_c,
        'has_h_or_v': has_h_or_v,
        'is_standalone_bezier': is_standalone,
        'is_inline_bezier': is_inline,
        'commands': commands
    }


async def test_pattern_gen():
    """Main test function using Playwright."""

    # Get absolute path to index.html
    index_path = Path(r"C:\Users\user\Project\ClaudeCode\PatternGen\index.html")

    if not index_path.exists():
        print(f"ERROR: {index_path} not found")
        return False

    file_url = index_path.as_uri()
    print(f"Testing: {file_url}\n")

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            # Navigate to the HTML file
            await page.goto(file_url, wait_until="networkidle")
            print("??Page loaded")

            # Set input text to "HELLO WORLD"
            await page.fill('textarea', "HELLO WORLD")
            print("??Input set to 'HELLO WORLD'")

            # Encode (click encode button or trigger encoding)
            # Wait for encode button and click it
            encode_btn = await page.query_selector('button:has-text("Encode")')
            if not encode_btn:
                # Try to find by text content differently
                buttons = await page.query_selector_all('button')
                for btn in buttons:
                    text = await btn.text_content()
                    if "Encode" in text:
                        await btn.click()
                        print("??Clicked Encode button")
                        break
            else:
                await encode_btn.click()
                print("??Clicked Encode button")

            # Wait a bit for encoding to complete
            await page.wait_for_timeout(1000)

            # Get the variant 0 SVG via evaluate
            svg_content = await page.evaluate("""
            () => {
                // Find the first SVG container or get the rendered SVG
                const svgElement = document.querySelector('svg');
                if (!svgElement) {
                    return null;
                }
                return new XMLSerializer().serializeToString(svgElement);
            }
            """)

            if not svg_content:
                print("ERROR: Could not retrieve SVG from page")
                await browser.close()
                return False

            print("??Retrieved SVG from page (variant 0)")
            print(f"  SVG size: {len(svg_content)} characters\n")

            # Parse SVG paths
            paths = parse_svg_paths(svg_content)
            print(f"SVG Structure Analysis:")
            print(f"  Total <path> elements: {len(paths)}")

            if len(paths) == 0:
                print("  ERROR: No path elements found in SVG!")
                await browser.close()
                return False

            # Analyze each path
            paths_with_bezier = 0
            standalone_bezier_paths = 0
            inline_bezier_paths = 0
            invalid_paths = 0

            for i, path_obj in enumerate(paths):
                d_attr = path_obj['d']

                if not d_attr or d_attr.strip() == '':
                    invalid_paths += 1
                    print(f"    Path {i}: INVALID (empty d attribute)")
                    continue

                analysis = analyze_path_commands(d_attr)

                if analysis['has_bezier']:
                    paths_with_bezier += 1

                if analysis['is_standalone_bezier']:
                    standalone_bezier_paths += 1
                    print(f"    Path {i}: Standalone bezier (fill-diagonal arc)")

                if analysis['is_inline_bezier']:
                    inline_bezier_paths += 1

            print(f"\n  Paths with C (bezier) commands: {paths_with_bezier}")
            print(f"  Standalone bezier paths (M+C only): {standalone_bezier_paths}")
            print(f"  Inline bezier paths (C within H/V chain): {inline_bezier_paths}")
            print(f"  Invalid paths (empty d): {invalid_paths}")

            # Validation checks
            print(f"\nValidation Results:")
            checks = []

            # Check 1: All paths have valid d attributes
            check1 = invalid_paths == 0
            checks.append(check1)
            print(f"  ??All paths have valid d attributes: {check1}")

            # Check 2: Bezier paths exist
            check2 = paths_with_bezier > 0
            checks.append(check2)
            print(f"  ??Paths with bezier commands exist: {check2} ({paths_with_bezier} paths)")

            # Check 3: Inline beziers exist (smooth corners)
            check3 = inline_bezier_paths > 0
            checks.append(check3)
            print(f"  ??Inline bezier paths (smooth corners) exist: {check3} ({inline_bezier_paths} paths)")

            # Check 4: At least some standalone beziers (fill diagonals)
            check4 = standalone_bezier_paths > 0
            checks.append(check4)
            print(f"  ??Standalone bezier paths (fill diagonals) exist: {check4} ({standalone_bezier_paths} paths)")

            # Overall result
            overall_pass = all(checks)
            print(f"\n{'='*50}")
            print(f"OVERALL RESULT: {'PASS' if overall_pass else 'FAIL'}")
            print(f"{'='*50}")

            await browser.close()
            return overall_pass

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            await browser.close()
            return False


async def main():
    """Entry point."""
    success = await test_pattern_gen()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    asyncio.run(main())
