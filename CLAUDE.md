# Text-to-Circuit Pattern Encoder

Single-file HTML app (`index.html`) that encodes plain text into maze/circuit-like SVG patterns and decodes them back.

## Keep Documentation Updated

When modifying the encoder algorithm, grid parameters, encoding scheme, or aesthetic rules, update this file to reflect the changes. This is the source of truth for how the system works.

---

## Architecture

Five core classes, all in `index.html`:

| Class | Responsibility |
|---|---|
| `CircuitGrid` | Edge storage (H/V/diagonal), bit serialization, adjacency graph |
| `TextEncoder_` | Text → bit stream → grid edges |
| `AestheticSolver` | Adds decorative arcs/diagonals (non-data-carrying) |
| `SVGRenderer` | Grid → SVG path strings via polyline chaining |
| `PatternDecoder` | SVG string → grid → bit stream → text |

## Grid Parameters

Derived from `Reference/Vector (Stroke).svg`:

| Constant | Value | Meaning |
|---|---|---|
| `COLS` | 17 | Grid columns |
| `ROWS` | 5 | Grid rows |
| `CELL` | 111.141 | Spacing between adjacent nodes (px) |
| `PAD` | 30.8725 | Padding from viewBox edge to first node (= SW / 2) |
| `SW` | 61.745 | SVG stroke width |
| `VB_W` | 1840 | ViewBox width |
| `VB_H` | 507 | ViewBox height |
| `K` | 0.5523 | Cubic bezier control point factor for quarter-circle arcs |
| `PANEL_GAP` | 60 | Vertical spacing between multi-panel grids |
| `MAX_CHAIN` | 999 | Max edges per polyline chain (effectively unlimited) |

Node position formula:
```
x = PAD + col * CELL
y = PAD + row * CELL
```

## Encoding Algorithm

### Character Set (6-bit, 44 characters)

```
Index  0-25: A-Z
Index 26-35: 0-9
Index    36: SPACE
Index    37: .
Index    38: ,
Index    39: -
Index    40: !
Index    41: ?
Index    42: '
Index    43: :
```

### Data-Carrying Edges

Only **horizontal** and **vertical** edges carry encoded data:
- 80 horizontal slots (5 rows x 16 gaps per row)
- 68 vertical slots (17 columns x 4 gaps per column)
- **148 total bits** per panel

Diagonal edges (arcs and straight lines) are aesthetic only and ignored during decoding.

### Random H/V Fill (3-Variant Scheme)

Empty (data=0) H/V bit positions are filled with variant-dependent random noise to make patterns visually dense. For each empty bit position, a 3-bit pattern is chosen from `{000, 001, 010, 011, 100, 101, 110}` — **never `111`**. Each variant (0, 1, 2) uses its bit from the pattern.

This means:
- **Data bits** (1) → edge present in **all 3 variants** (pattern `111`)
- **Empty bits** (0) → edge present in **0, 1, or 2 variants** (never all 3)

**Decoding requires all 3 SVGs**: AND-intersect the H/V grids from all 3 variants. Only edges present in all 3 survive → exactly the data bits. Zero false positives by construction.

Pattern selection: `hash(bitIndex, chunkIndex, 99, 0) % 6 + 1` gives a value 1-6 (patterns 001..110). Only ~23% of empty slots receive fill (`h % 100 < 77` skips the rest). This rate is tuned so overall pixel coverage matches the reference ~44%.

### Bit Layout Per Panel

```
[5 bits: character count (0-23)]
[3 bits: XOR checksum of all char codes, masked to 3 bits]
[6 bits x N: character codes]
[zero-padded to 148 bits]
```

- Header = 8 bits (5 length + 3 checksum)
- Max characters per panel = floor((148 - 8) / 6) = **23**

### Canonical Bit-to-Edge Mapping (Stride-Permuted)

Bits are mapped using a **stride-based permutation** over the natural row-band order. This distributes data bits spatially across all grid regions, preventing header/early-character bits from clustering.

**Natural order** (base): for each row, emit H edges (left→right), then V edges below:
```
Row 0: H(0,0..15), V(0,0..16)   → 33 edges
Row 1: H(1,0..15), V(1,0..16)   → 33 edges
Row 2: H(2,0..15), V(2,0..16)   → 33 edges
Row 3: H(3,0..15), V(3,0..16)   → 33 edges
Row 4: H(4,0..15)               → 16 edges
                                   148 total
```

**Stride permutation**: `bit[i] → natural[(i * 119) % 148]`

The stride 119 is coprime to 148, creating a bijection that ensures:
- Every edge slot is assigned exactly one bit position
- Active bits spread evenly across all 8 spatial quadrants (4 col × 2 row)
- For a typical 11-char message: ~36% fill per row-band, 50/50 left-right split

### Multi-Panel Support

For text longer than 23 characters:
- Split into 23-character chunks
- Each chunk becomes one 17x5 panel with its own header
- Panels stack vertically in one SVG, separated by `PANEL_GAP`
- ViewBox height extends: `panels * VB_H + (panels - 1) * PANEL_GAP`

### Checksum

3-bit XOR checksum: XOR all character codes together, mask with `& 0x7`.

## Aesthetic Solver

Adds decorative diagonal edges to fill visual space. Three constraints:
1. **No cycles** — Union-Find tracks connectivity; diagonals only bridge separate components (prevents closed/enclosed areas)
2. **Max degree 4** — no node gets more than 4 total edges
3. **No triangles** — a straight-line diagonal is rejected if its two endpoints share a common H/V neighbor (would create a tight enclosed triangle with a tiny empty hole). Arcs are exempt (they curve outward, filling the interior). The check also applies during random H/V fill — new H/V edges are rejected if they would complete a triangle with an existing diagonal.

Both passes use `dataSeed` (derived from character codes) and `variant` in the hash, so different input text produces different aesthetic patterns.

### Pass 1: L-Corner Arcs (quadrant-adaptive)

Scans all nodes with 2+ H/V neighbors forming a right angle. Arcs skip the cycle check (both endpoints are already connected through the bend node). Base keep-rate ~30%, boosted up to ~60% in sparse quadrants (tracks per-quadrant edge weight vs average).

### Pass 2: Fill Diagonals (sparsity-sorted, ~5% of 2×2 cells)

Collects all unfilled 2×2 cells, sorts by quadrant sparsity (sparsest first), then by hash. Fills up to `5%` of cells. Type is arc if surrounding H/V edges ≥ 2, else straight line. Subject to cycle and degree constraints.

### Encoding Order

1. Load data-only edges from bit array
2. Run AestheticSolver (arcs at data corners, fill diags)
3. Adaptive random H/V fill (see below)

This ensures arcs only form at real data-edge corners, and random fill only targets truly empty slots.

## Random H/V Fill (Adaptive, Quadrant-Balanced)

After data + aesthetics, remaining empty H/V slots receive variant-dependent random noise.

### 2D Quadrant Balancing

The grid is split into 8 zones (4 columns × 2 rows). For each zone:
1. Count existing H/V edges + diagonals as total visual edges
2. Compute `totalNeeded = max(0, 58 - totalVisual)` — 58 is the target visual edge count (~44% pixel coverage)
3. Select `2 × totalNeeded / 8` slots per zone (2× compensates for ~50% variant fill rate)
4. Sparse zones get extra: `round(basePerQ + deficit * 2)` where deficit = avgExisting - zoneExisting
5. Sort empty slots by `hash(r, c, dataSeed, 0)` for deterministic selection
6. Extract fill bit per variant from 3-bit pattern

### Character-Dependent Randomness

Hash inputs use `dataSeed` (derived from XOR-combined character codes) + grid position `(r, c)`. Different text produces different fill patterns. H edges use seed `dataSeed + 99`, V edges use `dataSeed + 199`.

### 3-Bit Pattern Scheme

For each selected empty slot, a pattern from {001..110} (never 111) is deterministically assigned:
- Pattern = `(hash % 6) + 1` → values 1-6
- Each variant extracts its bit: `(pattern >> (2 - variant)) & 1`
- Since pattern ≠ 7 (111), ANDing all 3 variants always gives 0 for noise bits
- Data edges are 1 in all variants → AND gives 1

### Target Coverage

Average pixel coverage of **~44-50%**, matching the reference Vector (Stroke) SVGs (~44%). Short inputs (1-2 chars) get heavy random fill to reach ~44%, while long inputs (23 chars) are inherently denser at ~52% from data edges alone. Target visual edge count: 58.

### 3-Variant Output

Each encode produces 3 visual variants. The `variant` parameter (0, 1, 2) affects:
1. **Random H/V fill** — which empty slots get noise edges
2. **Diagonal aesthetics** — which cells get decorative arcs/diagonals

All 3 variants encode the same data. Decoding requires AND-intersecting all 3 to separate data from noise. Download exports all 3 SVG files.

### Determinism

The `hash(r, c, seed, variant)` function provides deterministic pseudo-random decisions from grid position, character data, and variant index, ensuring same input text + variant always produces the same pattern.

## SVG Rendering

### Polyline Chaining

1. Build adjacency graph from all edges (H, V, diagonal)
2. Start chains from degree-1 nodes, then remaining nodes
3. Extend chains through degree-2 nodes
4. Each chain becomes one `<path>` element

### Path Commands

| Edge Type | SVG Command | Example |
|---|---|---|
| Horizontal | `H{x}` | `H253.154` |
| Vertical | `V{y}` | `V142.013` |
| Diagonal line | `L{x} {y}` | `L364.295 142.013` |
| Quarter-circle arc | `C{cp1x} {cp1y} {cp2x} {cp2y} {x} {y}` | Cubic bezier |

Consecutive same-direction H or V segments are merged into a single command.

### Arc Formula

Quarter-circle cubic bezier from `(px, py)` to `(tx, ty)`:
```
dx = tx - px, dy = ty - py
CP1 = (px + dx * K, py)        // horizontal departure
CP2 = (tx, ty - dy * K)        // vertical arrival
```

### Stroke Attributes

```xml
stroke="white" stroke-width="61.745" stroke-linecap="round" stroke-linejoin="round"
```

## Decoding Algorithm

Requires all 3 variant SVGs. Uses `PatternDecoder.decode3(svgStrings[3])`.

1. For each of the 3 SVG variants:
   a. Parse SVG, extract all `<path>` elements
   b. Determine panel count from viewBox height
   c. For each panel: parse paths, snap to grid, extract H/V edges → 148-bit array
2. For each panel, AND-intersect the 3 bit arrays: `bit[i] = v0[i] & v1[i] & v2[i]`
   - Edges in all 3 = data bit 1; edges differing = random fill (treated as 0)
3. Decode each panel's intersected bits:
   a. Read header (5-bit length + 3-bit checksum)
   b. Read character codes (6 bits each)
   c. Verify checksum
4. Concatenate text from all panels

### Y-Range Filtering (Multi-Panel)

Each panel only accepts edges whose raw Y coordinates fall within:
```
yMin = yOff + PAD - CELL * 0.5
yMax = yOff + PAD + (ROWS - 1) * CELL + CELL * 0.5
```
This prevents cross-panel contamination during decoding.

## Reference Files

`Reference/` contains 8 SVG files showing the target visual style:
- `Group 438.svg` — stroke-mode paths (stroke-width: 102, older thicker style)
- `Group 439.svg` — simplified subset (top rows only)
- `Vector (Stroke)*.svg` — fill-mode outlines (the current reference for dimensions)

## Self-Tests

On page load, 10 tests run automatically and display in the "Self-Test Results" panel:
- Basic text, numbers, single char, punctuation — 3-variant AND decode
- Max single panel (23 chars) — 3-variant decode
- Multi-panel (50 chars) — 3-variant decode
- All special characters — 3-variant decode
- Determinism (same input + variant → same SVG)
- Variant diversity (3 variants produce 3 distinct SVGs)
- Single-variant decode fails (confirms random fill makes individual SVGs undecodable)
