#!/usr/bin/env python3
"""Ocean Recon mission control — MeshCore edition.

Connects to a MeshCore companion radio over USB serial (dt267 low-power
firmware or stock), logs incoming channel/direct messages and node adverts to
CSV, computes the MGRS 100 m grid square for any coordinates found, and
rewrites a live coverage map (coverage.html).

MeshCore is message-centric: there are no periodic position broadcasts like
Meshtastic. Positions arrive when a crew sends a Quick Send message (with GPS
sharing on, coordinates ride along) or when a node advertises. So the field
procedure is: sail into a square, take your reading, press Quick Send.

Usage:
    python log_meshcore.py --port /dev/ttyUSB0
    python log_meshcore.py --test        # synthetic packets, no radio needed

NOTE: written against meshcore_py's documented API but not yet exercised
against real hardware — run with a radio plugged in before mission day and
check that rows appear in the CSV. Raw event payloads are logged in the last
CSV column so no data is lost even if coordinate parsing needs adjusting.
"""

import argparse
import asyncio
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import folium
import mgrs
from pyproj import Transformer

HERE = Path(__file__).parent
_MGRS = mgrs.MGRS()
TO_LL = Transformer.from_crs("EPSG:32619", "EPSG:4326", always_xy=True)

CSV_FIELDS = ["time_utc", "sender", "team", "kind", "lat", "lon", "square",
              "text", "raw"]

LATLON_RE = re.compile(r"(-?\d{1,2}\.\d{3,})\s*[, ]\s*(-?\d{1,3}\.\d{3,})")


def find_coords(obj):
    """Best-effort lat/lon extraction from an event payload dict."""
    if isinstance(obj, dict):
        for lat_key, lon_key in (("lat", "lon"), ("latitude", "longitude"),
                                 ("adv_lat", "adv_lon")):
            lat, lon = obj.get(lat_key), obj.get(lon_key)
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) \
                    and (lat or lon) and abs(lat) <= 90 and abs(lon) <= 180:
                return float(lat), float(lon)
        for v in obj.values():
            got = find_coords(v)
            if got:
                return got
    elif isinstance(obj, str):
        m = LATLON_RE.search(obj)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
            if abs(lat) <= 90 and abs(lon) <= 180 and (lat or lon):
                return lat, lon
    return None


class Mission:
    def __init__(self, csv_path, html_path, teams_path, nodes_path):
        self.csv_path = Path(csv_path)
        self.html_path = Path(html_path)
        self.covered = {}      # square -> {"teams": set, "nodes": set, "notes": []}
        self.team_colors = {}
        self.teams = []
        self.node_team = {}
        if Path(teams_path).exists():
            self.teams = json.loads(Path(teams_path).read_text())["teams"]
            for t in self.teams:
                self.team_colors[t["name"]] = t.get("color", "#e53935")
        if Path(nodes_path).exists():
            self.node_team = json.loads(Path(nodes_path).read_text())

        new_file = not self.csv_path.exists()
        self.csv_file = open(self.csv_path, "a", newline="")
        self.writer = csv.DictWriter(self.csv_file, fieldnames=CSV_FIELDS,
                                     extrasaction="ignore")
        if new_file:
            self.writer.writeheader()

    def square_of(self, lat, lon):
        ref = _MGRS.toMGRS(lat, lon, MGRSPrecision=3)
        return f"{ref[5:8]}-{ref[8:11]}" if ref.startswith("19TCG") else None

    def team_of(self, sender):
        for key, team in self.node_team.items():
            if key.startswith("_"):
                continue
            if key.lower() in str(sender).lower():
                return team
        return ""

    def log_event(self, kind, sender, text, payload):
        coords = find_coords(payload) or (find_coords(text) if text else None)
        lat, lon = coords if coords else (None, None)
        square = self.square_of(lat, lon) if coords else None
        row = {
            "time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sender": sender, "team": self.team_of(sender), "kind": kind,
            "lat": f"{lat:.6f}" if lat is not None else "",
            "lon": f"{lon:.6f}" if lon is not None else "",
            "square": square or "", "text": text or "",
            "raw": json.dumps(payload, default=str)[:500],
        }
        self.writer.writerow(row)
        self.csv_file.flush()
        print(f"{row['time_utc']} {str(sender):>10} {kind:<8} "
              f"square={square or '?'} {text or ''}")
        if square:
            entry = self.covered.setdefault(square, {"teams": set(),
                                                     "nodes": set(), "notes": []})
            entry["nodes"].add(str(sender))
            if row["team"]:
                entry["teams"].add(row["team"])
            if text:
                entry["notes"].append(text)
            self.write_html()

    def write_html(self):
        m = folium.Map(location=[41.781, -71.380], zoom_start=14)
        for t in self.teams:
            for sq in t["priority_squares"]:
                folium.Polygon(self.square_corners(sq), color=t.get("color"),
                               weight=3, fill=False,
                               tooltip=f"{t['name']} priority {sq}").add_to(m)
        for sq, entry in self.covered.items():
            teams = entry["teams"]
            color = self.team_colors.get(next(iter(teams)), "#1976d2") if teams else "#1976d2"
            label = f"<b>{sq}</b><br>{', '.join(sorted(entry['nodes']))}"
            if entry["notes"]:
                label += "<br>" + "<br>".join(entry["notes"][-3:])
            folium.Polygon(self.square_corners(sq), color=color, weight=1,
                           fill=True, fill_opacity=0.45,
                           popup=folium.Popup(label, max_width=250)).add_to(m)
        m.save(str(self.html_path))

    @staticmethod
    def square_corners(square):
        e3, n3 = square.split("-")
        x0, y0 = 300000 + int(e3) * 100, 4600000 + int(n3) * 100
        corners = [(x0, y0), (x0 + 100, y0), (x0 + 100, y0 + 100), (x0, y0 + 100)]
        return [(lat, lon) for lon, lat in (TO_LL.transform(x, y) for x, y in corners)]

    def summary(self):
        print("\n" + "=" * 52)
        print("MISSION SUMMARY")
        print("=" * 52)
        print(f"squares with data: {len(self.covered)}")
        by_team = {}
        for sq, entry in self.covered.items():
            for team in entry["teams"] or {"(unassigned)"}:
                by_team.setdefault(team, set()).add(sq)
        for team, squares in sorted(by_team.items()):
            line = f"  {team}: {len(squares)} squares"
            spec = next((t for t in self.teams if t["name"] == team), None)
            if spec:
                hits = squares & set(spec["priority_squares"])
                line += (f", priority {len(hits)}/{len(spec['priority_squares'])}"
                         f" ({', '.join(sorted(hits)) or 'none'})")
            print(line)
        print(f"\nlog: {self.csv_path}\nmap: {self.html_path}")


async def run_live(mission, port):
    from meshcore import MeshCore, EventType

    mc = await MeshCore.create_serial(port) if port else await MeshCore.create_serial()

    async def on_channel(event):
        p = event.payload or {}
        mission.log_event("channel", p.get("channel_idx", "ch?"),
                          p.get("text", ""), p)

    async def on_direct(event):
        p = event.payload or {}
        mission.log_event("direct", p.get("pubkey_prefix", "?"),
                          p.get("text", ""), p)

    async def on_advert(event):
        p = event.payload if isinstance(event.payload, dict) else {"payload": event.payload}
        mission.log_event("advert", p.get("name", p.get("pubkey_prefix", "?")),
                          "", p)

    mc.subscribe(EventType.CHANNEL_MSG_RECV, on_channel)
    mc.subscribe(EventType.CONTACT_MSG_RECV, on_direct)
    mc.subscribe(EventType.ADVERTISEMENT, on_advert)
    await mc.start_auto_message_fetching()
    print("mission control listening on MeshCore. Ctrl-C for summary.")
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        mission.summary()


def run_test(mission):
    """Synthetic Quick Send messages with attached DD coordinates."""
    boats = [("SEAL", "Harbor Seals", (41.7830, -71.3860), (41.7822, -71.3838)),
             ("OSPR", "Ospreys", (41.7778, -71.3852), (41.7762, -71.3812)),
             ("BASS", "Striped Bass", (41.7726, -71.3846), (41.7690, -71.3820))]
    for name, _, *points in boats:
        for lat, lon in points:
            mission.log_event("channel", name, "Reading taken",
                              {"channel_idx": 0, "text": "Reading taken",
                               "sender": name, "lat": lat, "lon": lon})
    mission.summary()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", help="serial port, e.g. /dev/ttyUSB0")
    p.add_argument("--csv", default=str(HERE / "mission_log.csv"))
    p.add_argument("--html", default=str(HERE / "coverage.html"))
    p.add_argument("--teams", default=str(HERE.parent / "gridmap" / "teams.json"))
    p.add_argument("--nodes", default=str(HERE / "nodes.json"))
    p.add_argument("--test", action="store_true")
    args = p.parse_args()

    mission = Mission(args.csv, args.html, args.teams, args.nodes)
    if args.test:
        run_test(mission)
    else:
        asyncio.run(run_live(mission, args.port))


if __name__ == "__main__":
    main()
