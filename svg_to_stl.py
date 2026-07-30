#!/usr/bin/env python3
"""Convert SVG circuit patterns to 3D-printable STL files.

Usage:
    python svg_to_stl.py circuit-pattern-v1.svg
    python svg_to_stl.py circuit-pattern-v1.svg -o output.stl
    python svg_to_stl.py circuit-pattern-v1.svg --stroke-width 4 --height 8

Dependencies:
    pip install shapely trimesh numpy scipy mapbox-earcut
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET

import numpy as np
from shapely.geometry import LineString, MultiPolygon
from shapely.ops import unary_union
import trimesh


SVG_NS = "http://www.w3.org/2000/svg"
SVG_STROKE_WIDTH = 61.745  # original SVG stroke-width


def parse_path_d(d: str) -> list[list[tuple[float, float]]]:
    """Parse an SVG path `d` attribute into a list of polylines."""
    tokens = re.findall(r'[MLHVCSQTAZmlhvcsqtaz][^MLHVCSQTAZmlhvcsqtaz]*', d)
    polylines: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    cx, cy = 0.0, 0.0

    for token in tokens:
        cmd = token[0]
        nums = [float(v) for v in re.findall(r'-?[0-9]*\.?[0-9]+(?:[eE][+-]?[0-9]+)?', token[1:])]

        if cmd == 'M':
            if current:
                polylines.append(current)
            cx, cy = nums[0], nums[1]
            current = [(cx, cy)]
        elif cmd == 'H':
            cx = nums[0]
            current.append((cx, cy))
        elif cmd == 'V':
            cy = nums[0]
            current.append((cx, cy))
        elif cmd == 'L':
            cx, cy = nums[0], nums[1]
            current.append((cx, cy))
        elif cmd == 'C':
            # Cubic bezier: 6 params (cp1x cp1y cp2x cp2y x y)
            p0 = (cx, cy)
            p1 = (nums[0], nums[1])
            p2 = (nums[2], nums[3])
            p3 = (nums[4], nums[5])
            for seg in range(1, 21):
                t = seg / 20.0
                t1 = 1.0 - t
                x = t1**3 * p0[0] + 3 * t1**2 * t * p1[0] + 3 * t1 * t**2 * p2[0] + t**3 * p3[0]
                y = t1**3 * p0[1] + 3 * t1**2 * t * p1[1] + 3 * t1 * t**2 * p2[1] + t**3 * p3[1]
                current.append((x, y))
            cx, cy = p3
        elif cmd == 'Z' or cmd == 'z':
            if current:
                current.append(current[0])
                polylines.append(current)
                current = []

    if current and len(current) >= 2:
        polylines.append(current)

    return polylines


def svg_to_polylines(svg_path: str) -> list[list[tuple[float, float]]]:
    """Extract all polylines from an SVG file."""
    tree = ET.parse(svg_path)
    root = tree.getroot()
    polylines: list[list[tuple[float, float]]] = []

    for path_el in root.iter(f'{{{SVG_NS}}}path'):
        d = path_el.get('d')
        if d:
            polylines.extend(parse_path_d(d))

    # Also try without namespace (some SVGs don't use namespaces)
    if not polylines:
        for path_el in root.iter('path'):
            d = path_el.get('d')
            if d:
                polylines.extend(parse_path_d(d))

    return polylines


def polylines_to_2d(polylines: list[list[tuple[float, float]]],
                    scale: float,
                    stroke_radius: float) -> MultiPolygon:
    """Buffer polylines into 2D polygons representing the stroke geometry."""
    buffered = []
    for pl in polylines:
        if len(pl) < 2:
            continue
        line = LineString([(x * scale, y * scale) for x, y in pl])
        buf = line.buffer(stroke_radius, cap_style='round', join_style='round', resolution=16)
        if not buf.is_empty:
            buffered.append(buf)

    if not buffered:
        print("Error: no geometry produced from SVG paths.", file=sys.stderr)
        sys.exit(1)

    merged = unary_union(buffered)
    if isinstance(merged, MultiPolygon):
        return merged
    return MultiPolygon([merged])


def extrude_to_mesh(multipoly: MultiPolygon, height: float) -> trimesh.Trimesh:
    """Extrude a 2D MultiPolygon into a 3D mesh."""
    meshes = []
    for poly in multipoly.geoms:
        if poly.is_empty:
            continue
        try:
            mesh = trimesh.creation.extrude_polygon(poly, height)
            meshes.append(mesh)
        except Exception as e:
            print(f"Warning: skipping polygon during extrusion: {e}", file=sys.stderr)

    if not meshes:
        print("Error: no meshes produced during extrusion.", file=sys.stderr)
        sys.exit(1)

    combined = trimesh.util.concatenate(meshes)
    return combined


def flip_y(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Flip Y axis (SVG Y-down → 3D Y-up) and fix normals."""
    verts = mesh.vertices.copy()
    y_min, y_max = verts[:, 1].min(), verts[:, 1].max()
    verts[:, 1] = y_max + y_min - verts[:, 1]
    mesh.vertices = verts
    mesh.fix_normals()
    return mesh


def main():
    parser = argparse.ArgumentParser(description="Convert SVG circuit pattern to 3D-printable STL")
    parser.add_argument("svg", help="Input SVG file")
    parser.add_argument("-o", "--output", help="Output STL file (default: input name with .stl)")
    parser.add_argument("--stroke-width", type=float, default=3.0,
                        help="Physical stroke width in mm (default: 3.0)")
    parser.add_argument("--height", type=float, default=5.0,
                        help="Extrusion height in mm (default: 5.0)")
    args = parser.parse_args()

    output = args.output
    if not output:
        output = re.sub(r'\.svg$', '.stl', args.svg, flags=re.IGNORECASE)
        if output == args.svg:
            output = args.svg + '.stl'

    scale = args.stroke_width / SVG_STROKE_WIDTH
    stroke_radius = args.stroke_width / 2.0

    print(f"Scale: {scale:.5f} (SVG units → mm)")
    print(f"Stroke width: {args.stroke_width}mm, height: {args.height}mm")

    print("Parsing SVG paths...")
    polylines = svg_to_polylines(args.svg)
    print(f"  Found {len(polylines)} polylines")

    print("Building 2D stroke geometry...")
    multipoly = polylines_to_2d(polylines, scale, stroke_radius)
    print(f"  {len(multipoly.geoms)} polygon(s) after union")

    print("Extruding to 3D...")
    mesh = extrude_to_mesh(multipoly, args.height)
    mesh = flip_y(mesh)

    bounds = mesh.bounds
    size = bounds[1] - bounds[0]
    print(f"  Mesh size: {size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm")
    print(f"  Watertight: {mesh.is_watertight}")

    mesh.export(output)
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()
