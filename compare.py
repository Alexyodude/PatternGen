"""
Compare generated circuit patterns against reference Vector (Stroke) SVGs.

Renders both in Chromium via Playwright, captures screenshots, and analyzes:
  1. White pixel coverage (density)
  2. Edge type distribution (H, V, arc, diagonal counts)
  3. Stroke length distribution (chain lengths)
  4. Spatial coverage per grid quadrant
"""

import base64
import json
import pathlib
import sys
from playwright.sync_api import sync_playwright

PROJECT = pathlib.Path(__file__).parent
REF_DIR = PROJECT / "Reference"
INDEX   = PROJECT / "index.html"
OUT_DIR = PROJECT / "compare_output"
OUT_DIR.mkdir(exist_ok=True)

# Reference SVGs to compare against (the fill-mode stroke outlines)
REF_FILES = sorted(REF_DIR.glob("Vector (Stroke)*.svg"))

# Test inputs to generate patterns for
TEST_INPUTS = [
    "HELLO WORLD",
    "THE QUICK BROWN FOX JUM",
    "ABCDEFGHIJKLM",
    "1234567890",
]


def render_svg_to_png(page, svg_content, out_path, width=1840, height=507):
    """Render an SVG string in the browser and screenshot it."""
    html = f"""<!DOCTYPE html>
<html><head><style>
  body {{ margin:0; padding:0; background:#000; display:flex;
         align-items:center; justify-content:center;
         width:{width}px; height:{height}px; }}
</style></head>
<body>{svg_content}</body></html>"""
    page.set_content(html)
    page.set_viewport_size({"width": width, "height": height})
    page.screenshot(path=str(out_path))


def analyze_pixels(page, png_path):
    """Load a screenshot and analyze white pixel coverage by quadrant."""
    # Encode image as base64 data URL to avoid file:// issues
    raw = png_path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    data_url = f"data:image/png;base64,{b64}"

    page.set_content("<html><body></body></html>")
    result = page.evaluate("""async (dataUrl) => {
        const img = new Image();
        await new Promise((resolve, reject) => {
            img.onload = resolve;
            img.onerror = reject;
            img.src = dataUrl;
        });
        const canvas = document.createElement('canvas');
        canvas.width = img.width;
        canvas.height = img.height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0);
        const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;

        const w = canvas.width, h = canvas.height;
        const total = w * h;
        let whiteTotal = 0;
        const qCols = 4, qRows = 2;
        const quadrants = Array.from({length: qRows}, () => Array(qCols).fill(0));
        const quadrantTotals = Array.from({length: qRows}, () => Array(qCols).fill(0));

        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                const i = (y * w + x) * 4;
                const brightness = (data[i] + data[i+1] + data[i+2]) / 3;
                const isWhite = brightness > 128 ? 1 : 0;
                whiteTotal += isWhite;
                const qr = Math.min(Math.floor(y / h * qRows), qRows - 1);
                const qc = Math.min(Math.floor(x / w * qCols), qCols - 1);
                quadrants[qr][qc] += isWhite;
                quadrantTotals[qr][qc]++;
            }
        }

        const quadrantPct = quadrants.map((row, ri) =>
            row.map((v, ci) => +(v / quadrantTotals[ri][ci] * 100).toFixed(1))
        );

        return {
            width: w,
            height: h,
            totalPixels: total,
            whitePixels: whiteTotal,
            coveragePct: +(whiteTotal / total * 100).toFixed(2),
            quadrantCoverage: quadrantPct,
        };
    }""", data_url)
    return result


def get_generated_stats(page):
    """Open index.html and extract edge/chain stats from generated patterns."""
    page.goto(INDEX.as_uri())
    page.wait_for_selector("#testResults")

    results = {}
    for text in TEST_INPUTS:
        stats = page.evaluate(f"""() => {{
            const text = {json.dumps(text)};
            const grids = TextEncoder_.encode(text);
            const svg = SVGRenderer.render(grids);

            // Count edge types
            let hCount = 0, vCount = 0, arcCount = 0, diagCount = 0;
            for (const grid of grids) {{
                for (let r = 0; r < ROWS; r++)
                    for (let c = 0; c < COLS - 1; c++)
                        if (grid.getH(r, c)) hCount++;
                for (let r = 0; r < ROWS - 1; r++)
                    for (let c = 0; c < COLS; c++)
                        if (grid.getV(r, c)) vCount++;
                for (const e of grid.dEdges) {{
                    if (e.type === 'arc') arcCount++;
                    else diagCount++;
                }}
            }}

            // Count chain lengths from the SVG paths
            const parser = new DOMParser();
            const doc = parser.parseFromString(svg, 'image/svg+xml');
            const paths = doc.querySelectorAll('path');
            const chainLengths = [];
            for (const p of paths) {{
                const d = p.getAttribute('d') || '';
                // Count segments: M is start, each H/V/L/C is one segment
                const segs = (d.match(/[HVLC]/g) || []).length;
                chainLengths.push(segs);
            }}

            const totalEdges = hCount + vCount + arcCount + diagCount;
            const maxCells = ROWS * COLS; // 85 nodes
            const maxEdges = 80 + 68 + 64; // H + V + all possible diags

            return {{
                text,
                panels: grids.length,
                hEdges: hCount,
                vEdges: vCount,
                arcs: arcCount,
                diags: diagCount,
                totalEdges,
                edgeDensity: +(totalEdges / maxEdges * 100).toFixed(1),
                pathCount: paths.length,
                chainLengths,
                avgChain: chainLengths.length > 0
                    ? +(chainLengths.reduce((a,b) => a+b, 0) / chainLengths.length).toFixed(1)
                    : 0,
                maxChain: chainLengths.length > 0 ? Math.max(...chainLengths) : 0,
                svg,
            }};
        }}""")
        results[text] = stats
    return results


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        print("=" * 70)
        print("REFERENCE SVG ANALYSIS")
        print("=" * 70)

        ref_stats = []
        for ref_file in REF_FILES:
            svg_content = ref_file.read_text(encoding="utf-8")
            png_path = OUT_DIR / f"ref_{ref_file.stem}.png"
            render_svg_to_png(page, svg_content, png_path)
            stats = analyze_pixels(page, png_path)
            stats["name"] = ref_file.name
            ref_stats.append(stats)
            print(f"\n  {ref_file.name}")
            print(f"    Coverage: {stats['coveragePct']}%")
            print(f"    Quadrant coverage:")
            for row in stats["quadrantCoverage"]:
                print(f"      {row}")

        # Average reference coverage
        avg_ref_coverage = sum(s["coveragePct"] for s in ref_stats) / len(ref_stats) if ref_stats else 0
        avg_ref_quadrants = None
        if ref_stats:
            rows_n = len(ref_stats[0]["quadrantCoverage"])
            cols_n = len(ref_stats[0]["quadrantCoverage"][0])
            avg_ref_quadrants = [
                [round(sum(s["quadrantCoverage"][r][c] for s in ref_stats) / len(ref_stats), 1)
                 for c in range(cols_n)]
                for r in range(rows_n)
            ]

        print(f"\n  Average reference coverage: {avg_ref_coverage:.1f}%")
        if avg_ref_quadrants:
            print(f"  Average quadrant coverage:")
            for row in avg_ref_quadrants:
                print(f"    {row}")

        print()
        print("=" * 70)
        print("GENERATED PATTERN ANALYSIS")
        print("=" * 70)

        gen_stats = get_generated_stats(page)

        gen_coverages = []
        for text, stats in gen_stats.items():
            # Render generated SVG to PNG
            png_path = OUT_DIR / f"gen_{text.replace(' ', '_')[:20]}.png"
            render_svg_to_png(page, stats["svg"], png_path)
            px = analyze_pixels(page, png_path)
            gen_coverages.append(px["coveragePct"])

            print(f"\n  \"{text}\" ({stats['panels']} panel{'s' if stats['panels'] > 1 else ''})")
            print(f"    Edges: H={stats['hEdges']} V={stats['vEdges']} "
                  f"Arc={stats['arcs']} Diag={stats['diags']} "
                  f"Total={stats['totalEdges']} ({stats['edgeDensity']}% density)")
            print(f"    Paths: {stats['pathCount']} chains, "
                  f"avg={stats['avgChain']} max={stats['maxChain']} segments")
            print(f"    Chain lengths: {stats['chainLengths']}")
            print(f"    Pixel coverage: {px['coveragePct']}%")
            print(f"    Quadrant coverage:")
            for row in px["quadrantCoverage"]:
                print(f"      {row}")

        avg_gen_coverage = sum(gen_coverages) / len(gen_coverages) if gen_coverages else 0

        print()
        print("=" * 70)
        print("COMPARISON SUMMARY")
        print("=" * 70)
        print(f"  Reference avg coverage:  {avg_ref_coverage:.1f}%")
        print(f"  Generated avg coverage:  {avg_gen_coverage:.1f}%")
        diff = avg_gen_coverage - avg_ref_coverage
        print(f"  Difference:              {diff:+.1f}% "
              f"({'denser' if diff > 0 else 'sparser'} than reference)")

        if avg_ref_quadrants:
            print(f"\n  Quadrant comparison (ref -> gen avg):")
            gen_quads_all = []
            for text, stats in gen_stats.items():
                png_path = OUT_DIR / f"gen_{text.replace(' ', '_')[:20]}.png"
                px = analyze_pixels(page, png_path)
                gen_quads_all.append(px["quadrantCoverage"])
            if gen_quads_all:
                rows_n = len(gen_quads_all[0])
                cols_n = len(gen_quads_all[0][0])
                avg_gen_quads = [
                    [round(sum(g[r][c] for g in gen_quads_all) / len(gen_quads_all), 1)
                     for c in range(cols_n)]
                    for r in range(rows_n)
                ]
                for r in range(rows_n):
                    ref_row = avg_ref_quadrants[r]
                    gen_row = avg_gen_quads[r]
                    diffs = [f"{g-r_:+.1f}" for g, r_ in zip(gen_row, ref_row)]
                    print(f"    ref={ref_row}  gen={gen_row}  diff={diffs}")

        browser.close()
        print(f"\n  Screenshots saved to: {OUT_DIR}")
        print()


if __name__ == "__main__":
    main()
