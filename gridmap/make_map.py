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


def draw_map(bounds, out_stem, size, title, team=None, provider=None):
    x0, x1, y0, y1 = snap_bounds(bounds)
    fig_w, fig_h = PAPER[size]
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")

    provider = provider or ctx.providers.OpenStreetMap.Mapnik
    ctx.add_basemap(ax, crs=UTM_CRS, source=provider, attribution_size=4)

    # --- grid lines ---
    for x in range(x0, x1 + 1, GRID_M):
        bold = x % BOLD_M == 0
        ax.axvline(x, color="#1a237e", lw=1.2 if bold else 0.35,
                   alpha=0.9 if bold else 0.55, zorder=3)
    for y in range(y0, y1 + 1, GRID_M):
        bold = y % BOLD_M == 0
        ax.axhline(y, color="#1a237e", lw=1.2 if bold else 0.35,
                   alpha=0.9 if bold else 0.55, zorder=3)

    # --- edge labels: 3-digit MGRS values on every line, bigger on bold ---
    for x in range(x0, x1 + 1, GRID_M):
        bold = x % BOLD_M == 0
        for y_edge, va, dy in [(y0, "top", -12), (y1, "bottom", 12)]:
            ax.annotate(grid_label(x), (x, y_edge), xytext=(0, dy),
                        textcoords="offset points", ha="center", va=va,
                        fontsize=8 if bold else 4.5,
                        fontweight="bold" if bold else "normal", color="#1a237e")
    for y in range(y0, y1 + 1, GRID_M):
        bold = y % BOLD_M == 0
        for x_edge, ha, dx in [(x0, "right", -4), (x1, "left", 4)]:
            ax.annotate(grid_label(y), (x_edge, y), xytext=(dx, 0),
                        textcoords="offset points", ha=ha, va="center",
                        fontsize=8 if bold else 4.5,
                        fontweight="bold" if bold else "normal", color="#1a237e")

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
    ax.plot(dx, dy, marker="*", color="#b71c1c", markersize=18,
            markeredgecolor="white", zorder=5)
    ax.annotate("LAUNCH", (dx, dy), xytext=(8, 8), textcoords="offset points",
                fontsize=9, fontweight="bold", color="#b71c1c",
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
    ax.set_title(title, fontsize=15, fontweight="bold", pad=28)
    fig.text(0.5, 0.955,
             "Radio shows:  19TCG0136228411   →   split the 10 digits:  01362 | 28411   →   first 3 of each   →   square 013-284",
             ha="center", fontsize=10, family="monospace")
    fig.text(0.99, 0.01,
             f"MGRS zone 19T, square CG · 100 m grid · "
             f"Ham radio Maidenhead locator: {maidenhead(clat, clon)} "
             f"(hams worldwide log contacts by grid square!)",
             ha="right", fontsize=7, style="italic")

    ax.set_xticks([])
    ax.set_yticks([])
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
    args = p.parse_args()

    bounds = DEFAULT_BOUNDS
    if args.bounds:
        s, w, n, e = args.bounds
        bounds = {"south": s, "west": w, "north": n, "east": e}

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    draw_map(bounds, out / f"master-{args.size}", args.size,
             "OCEAN RECON — Edgewood Mission Grid")

    teams_path = Path(args.teams)
    if teams_path.exists():
        teams = json.loads(teams_path.read_text())["teams"]
        for team in teams:
            slug = team["name"].lower().replace(" ", "-")
            draw_map(bounds, out / f"{slug}-{args.size}", args.size,
                     f"OCEAN RECON — Team {team['name']}", team=team)
    else:
        print(f"(no {teams_path} — master map only)")


if __name__ == "__main__":
    main()
