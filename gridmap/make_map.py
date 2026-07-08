#!/usr/bin/env python3
"""Generate printable MGRS 100 m grid maps of the Edgewood sailing area.

Produces a master map plus one map per team (with that team's priority
squares highlighted) as PDF and PNG, sized for letter or ledger paper.

Grid squares are named by the first three digits of the MGRS easting and
northing groups, e.g. "013-284" — the same digits the kids read off a
MeshCore display with Settings -> Pos. Format set to MGRS (shown
concatenated, e.g. 19TCG0136228411).

Usage:
    python make_map.py                      # master + all teams from teams.json
    python make_map.py --size ledger
    python make_map.py --teams teams.json --out ../maps
"""

import argparse
import json
import math
from pathlib import Path

import contextily as ctx
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrow, Rectangle
from pyproj import Transformer

UTM_CRS = "EPSG:32619"  # UTM zone 19N — Edgewood / Providence River
WGS84 = "EPSG:4326"
GRID_M = 100            # grid cell size in meters
BOLD_M = 500            # bold line spacing in meters

TO_UTM = Transformer.from_crs(WGS84, UTM_CRS, always_xy=True)
TO_LL = Transformer.from_crs(UTM_CRS, WGS84, always_xy=True)

PAPER = {  # landscape (width, height) inches
    "letter": (11.0, 8.5),
    "ledger": (17.0, 11.0),
}

# Default extent: Providence River off Edgewood Yacht Club (lat/lon)
DEFAULT_BOUNDS = {"south": 41.765, "west": -71.397, "north": 41.797, "east": -71.363}
EYC_DOCK = (41.7827, -71.3903)  # launch point marker


def maidenhead(lat, lon):
    """6-character Maidenhead locator, e.g. FN41hs."""
    lon += 180.0
    lat += 90.0
    field = chr(ord("A") + int(lon // 20)) + chr(ord("A") + int(lat // 10))
    square = str(int(lon % 20 // 2)) + str(int(lat % 10 // 1))
    subsq = chr(ord("a") + int(lon % 2 * 12)) + chr(ord("a") + int(lat % 1 * 24))
    return field + square + subsq


def grid_label(coord_m):
    """3-digit MGRS label for a 100 m grid line (UTM meters)."""
    return f"{(int(coord_m) % 100000) // 100:03d}"


def square_to_xy(square):
    """'013-284' -> (easting, northing) of the square's SW corner, within 19T CG."""
    e3, n3 = square.split("-")
    return 300000 + int(e3) * 100, 4600000 + int(n3) * 100


def snap_bounds(bounds):
    """lat/lon bounds -> UTM extent snapped outward to the 100 m grid."""
    xs, ys = [], []
    for lat, lon in [(bounds["south"], bounds["west"]), (bounds["south"], bounds["east"]),
                     (bounds["north"], bounds["west"]), (bounds["north"], bounds["east"])]:
        x, y = TO_UTM.transform(lon, lat)
        xs.append(x)
        ys.append(y)
    x0 = math.floor(min(xs) / GRID_M) * GRID_M
    x1 = math.ceil(max(xs) / GRID_M) * GRID_M
    y0 = math.floor(min(ys) / GRID_M) * GRID_M
    y1 = math.ceil(max(ys) / GRID_M) * GRID_M
    return x0, x1, y0, y1


def draw_graticule(ax, bounds, y0, y1, step=0.005):
    """Dashed lat/lon lines with degree labels, on top of the MGRS grid."""
    lbl_kw = dict(fontsize=6.5, style="italic", color="black", zorder=6,
                  bbox=dict(facecolor="white", alpha=0.75, edgecolor="none", pad=1))
    # lines at round multiples of step
    lats = [round(math.ceil(bounds["south"] / step) * step + i * step, 6)
            for i in range(int((bounds["north"] - bounds["south"]) / step) + 1)]
    lats = [v for v in lats if v <= bounds["north"]]
    lons = [round(math.ceil(bounds["west"] / step) * step + i * step, 6)
            for i in range(int((bounds["east"] - bounds["west"]) / step) + 1)]
    lons = [v for v in lons if v <= bounds["east"]]

    for lat in lats:
        pts = [TO_UTM.transform(bounds["west"] + f * (bounds["east"] - bounds["west"]), lat)
               for f in (0, 0.5, 1)]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], ls=(0, (6, 3)),
                color="black", lw=0.9, alpha=0.85, zorder=3.5, clip_on=True)
        lx, ly = pts[0]
        if ly < y0 + 0.08 * (y1 - y0):  # would collide with the scale bar
            lx, ly = pts[-1]
            ax.annotate(f"{lat:.3f}°N", (lx, ly), xytext=(-6, 3),
                        textcoords="offset points", ha="right", va="bottom", **lbl_kw)
        else:
            ax.annotate(f"{lat:.3f}°N", (lx, ly), xytext=(6, 3),
                        textcoords="offset points", ha="left", va="bottom", **lbl_kw)
    for lon in lons:
        pts = [TO_UTM.transform(lon, bounds["south"] + f * (bounds["north"] - bounds["south"]))
               for f in (0, 0.5, 1)]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], ls=(0, (6, 3)),
                color="black", lw=0.9, alpha=0.85, zorder=3.5, clip_on=True)
        bx, by = pts[0]
        ax.annotate(f"{abs(lon):.3f}°W", (bx, max(by, y0)), xytext=(3, 10),
                    textcoords="offset points", ha="left", va="bottom",
                    rotation=90, **lbl_kw)


def draw_map(bounds, out_stem, size, title, team=None, provider=None, bw=False,
             latlon=False, howto=True, footer=True, posterize=0,
             invert_water=False, web=False):
    x0, x1, y0, y1 = snap_bounds(bounds)
    if web:
        # edge-to-edge render: image pixels map linearly onto the UTM extent
        fig_h = 10.0
        fig_w = fig_h * (x1 - x0) / (y1 - y0)
        fig = plt.figure(figsize=(fig_w, fig_h))
        ax = fig.add_axes([0, 0, 1, 1])
    else:
        fig_w, fig_h = PAPER[size]
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        ax.set_aspect("equal")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)

    provider = provider or ctx.providers.OpenStreetMap.Mapnik
    ctx.add_basemap(ax, crs=UTM_CRS, source=provider, attribution_size=4)

    if bw:
        # grayscale + percentile contrast stretch so water/land/streets
        # stay distinct on a black-and-white printer
        im = ax.images[0]
        arr = np.asarray(im.get_array(), dtype=float)
        rgb = arr[..., :3]
        if rgb.max() > 1:
            rgb = rgb / 255.0
        gray = rgb @ np.array([0.299, 0.587, 0.114])
        if np.median(gray) < 0.5:  # dark basemap (e.g. DarkMatter): print light
            gray = 1.0 - gray
        lo, hi = np.percentile(gray, 2), np.percentile(gray, 98)
        gray = np.clip((gray - lo) / max(hi - lo, 1e-6), 0, 1)
        gray = gray ** 0.78  # lighten midtones (water) so black grid pops in print
        if posterize:  # flatten to N gray levels for a crisp toner-style print
            levels = np.round(gray * (posterize - 1))
            if invert_water:  # swap the two lightest levels: water white, land gray
                top, second = posterize - 1, posterize - 2
                levels = np.where(levels == top, -1, levels)
                levels = np.where(levels == second, top, levels)
                levels = np.where(levels == -1, second, levels)
            gray = levels / (posterize - 1)
        im.set_array(gray)
        im.set_cmap("gray")
        im.set_clim(0, 1)

    ink = "black" if bw else "#1a237e"
    launch_color = "black" if bw else "#b71c1c"

    # --- grid lines ---
    for x in range(x0, x1 + 1, GRID_M):
        bold = x % BOLD_M == 0
        ax.axvline(x, color=ink, lw=1.2 if bold else 0.35,
                   alpha=0.9 if bold else 0.55, zorder=3)
    for y in range(y0, y1 + 1, GRID_M):
        bold = y % BOLD_M == 0
        ax.axhline(y, color=ink, lw=1.2 if bold else 0.35,
                   alpha=0.9 if bold else 0.55, zorder=3)

    # --- edge labels: 3-digit MGRS values on every line, bigger on bold ---
    lbl_bbox = dict(facecolor="white", alpha=0.7, edgecolor="none", pad=0.5) \
        if web else None
    x_edges = [(y0, "bottom", 5), (y1, "top", -5)] if web \
        else [(y0, "top", -12), (y1, "bottom", 12)]
    y_edges = [(x0, "left", 4), (x1, "right", -4)] if web \
        else [(x0, "right", -4), (x1, "left", 4)]
    for x in range(x0, x1 + 1, GRID_M):
        bold = x % BOLD_M == 0
        for y_edge, va, dy in x_edges:
            ax.annotate(grid_label(x), (x, y_edge), xytext=(0, dy),
                        textcoords="offset points", ha="center", va=va,
                        fontsize=8 if bold else 4.5,
                        fontweight="bold" if bold else "normal", color=ink,
                        bbox=lbl_bbox)
    for y in range(y0, y1 + 1, GRID_M):
        bold = y % BOLD_M == 0
        for x_edge, ha, dx in y_edges:
            ax.annotate(grid_label(y), (x_edge, y), xytext=(dx, 0),
                        textcoords="offset points", ha=ha, va="center",
                        fontsize=8 if bold else 4.5,
                        fontweight="bold" if bold else "normal", color=ink,
                        bbox=lbl_bbox)

    # --- lat/lon graticule ---
    if latlon:
        draw_graticule(ax, bounds, y0, y1)

    # --- team priority squares ---
    if team:
        color = team.get("color", "#e53935")
        for sq in team["priority_squares"]:
            sx, sy = square_to_xy(sq)
            ax.add_patch(Rectangle((sx, sy), GRID_M, GRID_M, facecolor=color,
                                   edgecolor=color, alpha=0.35, lw=2, zorder=4))
        ax.plot([], [], "s", color=color, alpha=0.5, markersize=12,
                label=f"{team['name']} priority squares")
        ax.legend(loc="lower right", fontsize=9, framealpha=0.9)

    # --- launch point ---
    dx, dy = TO_UTM.transform(EYC_DOCK[1], EYC_DOCK[0])
    ax.plot(dx, dy, marker="*", color=launch_color, markersize=18,
            markeredgecolor="white", zorder=5)
    ax.annotate("LAUNCH", (dx, dy), xytext=(8, 8), textcoords="offset points",
                fontsize=9, fontweight="bold", color=launch_color,
                path_effects=None, zorder=5)

    # --- north arrow ---
    ax_len = (y1 - y0) * 0.06
    nx, ny = x0 + (x1 - x0) * 0.045, y1 - (y1 - y0) * 0.14
    ax.add_patch(FancyArrow(nx, ny, 0, ax_len, width=ax_len * 0.12,
                            head_width=ax_len * 0.4, head_length=ax_len * 0.35,
                            fc="black", ec="white", zorder=5))
    ax.text(nx, ny + ax_len * 1.6, "N", ha="center", fontsize=14,
            fontweight="bold", zorder=5)

    # --- scale bar (500 m) ---
    sb_x, sb_y = x0 + (x1 - x0) * 0.03, y0 + (y1 - y0) * 0.04
    ax.add_patch(Rectangle((sb_x, sb_y), 500, (y1 - y0) * 0.008,
                           facecolor="black", edgecolor="white", zorder=5))
    ax.text(sb_x + 250, sb_y + (y1 - y0) * 0.018, "500 m  (5 squares)",
            ha="center", fontsize=8, fontweight="bold", zorder=5,
            bbox=dict(facecolor="white", alpha=0.7, edgecolor="none", pad=1))

    # --- title + how-to-read + ham sidebar ---
    clat = (bounds["south"] + bounds["north"]) / 2
    clon = (bounds["west"] + bounds["east"]) / 2
    if not web:
        ax.set_title(title, fontsize=15, fontweight="bold", pad=28)
    if howto and not web:
        fig.text(0.5, 0.955,
                 "Radio shows:  19TCG0136228411   →   split the 10 digits:  01362 | 28411   →   first 3 of each   →   square 013-284",
                 ha="center", fontsize=10, family="monospace")
    if footer and not web:
        fig.text(0.99, 0.01,
                 f"MGRS zone 19T, square CG · 100 m grid · "
                 f"Ham radio Maidenhead locator: {maidenhead(clat, clon)} "
                 f"(hams worldwide log contacts by grid square!)",
                 ha="right", fontsize=7, style="italic")

    ax.set_xticks([])
    ax.set_yticks([])
    if web:
        dpi = 200
        fig.savefig(f"{out_stem}.png", dpi=dpi)
        meta = {"epsg": 32619, "x0": x0, "x1": x1, "y0": y0, "y1": y1,
                "width_px": int(round(fig_w * dpi)),
                "height_px": int(round(fig_h * dpi)),
                "utm_zone": "19T", "square_100km": "CG"}
        Path(f"{out_stem}.json").write_text(json.dumps(meta, indent=2) + "\n")
        plt.close(fig)
        print(f"wrote {out_stem}.png / .json (web, extent-exact)")
        return
    fig.tight_layout(rect=[0, 0.015, 1, 0.97])
    for ext in ("pdf", "png"):
        fig.savefig(f"{out_stem}.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_stem}.pdf / .png")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--teams", default=str(Path(__file__).parent / "teams.json"),
                   help="JSON file of teams and priority squares")
    p.add_argument("--out", default=str(Path(__file__).parent.parent / "maps"),
                   help="output directory")
    p.add_argument("--size", choices=PAPER, default="letter")
    p.add_argument("--bounds", nargs=4, type=float, metavar=("S", "W", "N", "E"),
                   help="map bounds: south west north east (decimal degrees)")
    p.add_argument("--bw", action="store_true",
                   help="high-contrast black-and-white basemap and markings")
    p.add_argument("--latlon", action="store_true",
                   help="overlay dashed lat/lon graticule with degree labels")
    p.add_argument("--no-howto", action="store_true",
                   help="omit the 'Radio shows: ...' how-to-read line at the top")
    p.add_argument("--no-footer", action="store_true",
                   help="omit the 'MGRS zone 19T ...' line at the bottom")
    p.add_argument("--name", help="output file stem (default: master-<size>)")
    p.add_argument("--title", default="OCEAN RECON — Edgewood Mission Grid",
                   help="map title")
    p.add_argument("--provider", help="contextily tile provider, dotted path "
                   "into ctx.providers (e.g. CartoDB.Positron)")
    p.add_argument("--posterize", type=int, default=0, metavar="N",
                   help="with --bw: flatten basemap to N gray levels")
    p.add_argument("--invert-water", action="store_true",
                   help="with --posterize: swap the two lightest levels so "
                   "water prints white and land gray")
    p.add_argument("--web", action="store_true",
                   help="render edge-to-edge PNG + JSON extent sidecar for "
                   "the live web map (no title/margins, labels inside)")
    p.add_argument("--master-only", action="store_true",
                   help="skip per-team maps")
    args = p.parse_args()

    bounds = DEFAULT_BOUNDS
    if args.bounds:
        s, w, n, e = args.bounds
        bounds = {"south": s, "west": w, "north": n, "east": e}

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    provider = None
    if args.provider:
        provider = ctx.providers
        for part in args.provider.split("."):
            provider = provider[part]

    stem = args.name or f"master-{args.size}"
    draw_map(bounds, out / stem, args.size, args.title,
             bw=args.bw, latlon=args.latlon, provider=provider,
             howto=not args.no_howto, footer=not args.no_footer,
             posterize=args.posterize, invert_water=args.invert_water,
             web=args.web)

    teams_path = Path(args.teams)
    if args.master_only:
        pass
    elif teams_path.exists():
        teams = json.loads(teams_path.read_text())["teams"]
        for team in teams:
            slug = team["name"].lower().replace(" ", "-")
            draw_map(bounds, out / f"{slug}-{args.size}", args.size,
                     f"OCEAN RECON — Team {team['name']}", team=team, bw=args.bw)
    else:
        print(f"(no {teams_path} — master map only)")


if __name__ == "__main__":
    main()
