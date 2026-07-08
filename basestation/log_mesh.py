#!/usr/bin/env python3
"""Ocean Recon mission control: log mesh traffic and track grid coverage.

Connects to a Heltec over USB serial via the meshtastic library, logs every
position and telemetry packet to CSV, and rewrites a live coverage map
(coverage.html — open it in a browser and refresh) showing which 100 m MGRS
squares have data. Ctrl-C prints the end-of-mission score.

Usage:
    python log_mesh.py                      # auto-detect serial port
    python log_mesh.py --port /dev/ttyUSB0
    python log_mesh.py --test               # synthetic packets, no radio needed

Team scoring: gridmap/teams.json defines priority squares. Optionally map
radios to teams in nodes.json: {"SHORTNAME_OR_ID": "Harbor Seals", ...}
(short name = the 4-char name shown on the radio / in the app).
"""

import argparse
import csv
import json
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import folium
import mgrs
from pyproj import Transformer

HERE = Path(__file__).parent
_MGRS = mgrs.MGRS()
TO_LL = Transformer.from_crs("EPSG:32619", "EPSG:4326", always_xy=True)

CSV_FIELDS = ["time_utc", "node_id", "node_name", "team", "kind", "lat", "lon",
              "square", "temperature_c", "relative_humidity", "barometric_pressure",
              "voltage", "battery_level"]

TEAM_COLORS = {}  # filled from teams.json


class Mission:
    def __init__(self, csv_path, html_path, teams_path, nodes_path):
        self.csv_path = Path(csv_path)
        self.html_path = Path(html_path)
        self.last_pos = {}       # node_id -> (lat, lon, square)
        self.node_names = {}     # node_id -> short name
        self.node_team = {}      # node_id/shortname -> team name (from nodes.json)
        self.covered = {}        # square -> {"teams": set, "nodes": set, "readings": [..]}
        self.teams = []
        if Path(teams_path).exists():
            data = json.loads(Path(teams_path).read_text())
            self.teams = data["teams"]
            for t in self.teams:
                TEAM_COLORS[t["name"]] = t.get("color", "#e53935")
        if Path(nodes_path).exists():
            self.node_team = json.loads(Path(nodes_path).read_text())

        new_file = not self.csv_path.exists()
        self.csv_file = open(self.csv_path, "a", newline="")
        self.writer = csv.DictWriter(self.csv_file, fieldnames=CSV_FIELDS,
                                     extrasaction="ignore")
        if new_file:
            self.writer.writeheader()

    # ---- helpers -------------------------------------------------------
    def square_of(self, lat, lon):
        """'013-284' style square name (100 m MGRS), or None outside 19T CG."""
        ref = _MGRS.toMGRS(lat, lon, MGRSPrecision=3)  # e.g. '19TCG013284'
        if not ref.startswith("19TCG"):
            return None
        return f"{ref[5:8]}-{ref[8:11]}"

    def team_of(self, node_id):
        name = self.node_names.get(node_id, "")
        return self.node_team.get(node_id) or self.node_team.get(name) or ""

    def note_name(self, node_id, packet, interface):
        if node_id in self.node_names:
            return
        try:
            node = (interface.nodes or {}).get(node_id, {})
            self.node_names[node_id] = node.get("user", {}).get("shortName", node_id)
        except Exception:
            self.node_names[node_id] = node_id

    # ---- packet handling ----------------------------------------------
    def on_packet(self, packet, interface=None):
        decoded = packet.get("decoded", {})
        port = decoded.get("portnum", "")
        node_id = packet.get("fromId") or f"!{packet.get('from', 0):08x}"
        if interface is not None:
            self.note_name(node_id, packet, interface)
        row = {
            "time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "node_id": node_id,
            "node_name": self.node_names.get(node_id, node_id),
            "team": self.team_of(node_id),
        }

        if port == "POSITION_APP":
            pos = decoded.get("position", {})
            lat, lon = pos.get("latitude"), pos.get("longitude")
            if not lat and not lon:  # no GPS lock yet
                return
            square = self.square_of(lat, lon)
            self.last_pos[node_id] = (lat, lon, square)
            row.update(kind="position", lat=f"{lat:.6f}", lon=f"{lon:.6f}",
                       square=square or "")
            self.record(square, node_id, row)

        elif port == "TELEMETRY_APP":
            tele = decoded.get("telemetry", {})
            env = tele.get("environmentMetrics", {})
            dev = tele.get("deviceMetrics", {})
            if not env and not dev:
                return
            lat, lon, square = self.last_pos.get(node_id, (None, None, None))
            row.update(
                kind="telemetry",
                lat=f"{lat:.6f}" if lat else "", lon=f"{lon:.6f}" if lon else "",
                square=square or "",
                temperature_c=env.get("temperature", ""),
                relative_humidity=env.get("relativeHumidity", ""),
                barometric_pressure=env.get("barometricPressure", ""),
                voltage=env.get("voltage", dev.get("voltage", "")),
                battery_level=dev.get("batteryLevel", ""),
            )
            self.record(square, node_id, row, reading=env)
        else:
            return

        self.writer.writerow(row)
        self.csv_file.flush()
        print(f"{row['time_utc']} {row['node_name']:>6} {row['kind']:<9} "
              f"square={row.get('square', '') or '?'} "
              f"T={row.get('temperature_c', '')}")

    def record(self, square, node_id, row, reading=None):
        if not square:
            return
        entry = self.covered.setdefault(square, {"teams": set(), "nodes": set(),
                                                 "latest": {}})
        entry["nodes"].add(self.node_names.get(node_id, node_id))
        team = self.team_of(node_id)
        if team:
            entry["teams"].add(team)
        if reading:
            entry["latest"] = {k: v for k, v in reading.items() if v is not None}
        self.write_html()

    # ---- outputs -------------------------------------------------------
    def write_html(self):
        m = folium.Map(location=[41.781, -71.380], zoom_start=14)
        # priority squares (hollow outlines)
        for t in self.teams:
            for sq in t["priority_squares"]:
                folium.Polygon(self.square_corners(sq), color=t.get("color"),
                               weight=3, fill=False,
                               tooltip=f"{t['name']} priority {sq}").add_to(m)
        # covered squares (filled)
        for sq, entry in self.covered.items():
            teams = entry["teams"]
            color = TEAM_COLORS.get(next(iter(teams)), "#1976d2") if teams else "#1976d2"
            label = f"<b>{sq}</b><br>nodes: {', '.join(sorted(entry['nodes']))}"
            if entry["latest"]:
                label += "<br>" + "<br>".join(f"{k}: {v}" for k, v in entry["latest"].items())
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


def run_test(mission):
    """Feed synthetic packets: three nodes sail through their sectors."""
    tracks = {
        "!0000a001": ("SEAL", [(41.7830, -71.3860), (41.7822, -71.3838), (41.7815, -71.3810)]),
        "!0000a002": ("OSPR", [(41.7778, -71.3852), (41.7770, -71.3830), (41.7762, -71.3812)]),
        "!0000a003": ("BASS", [(41.7726, -71.3846), (41.7712, -71.3828), (41.7690, -71.3820)]),
    }
    for step in range(3):
        for node_id, (name, pts) in tracks.items():
            mission.node_names[node_id] = name
            lat, lon = pts[step]
            mission.on_packet({"fromId": node_id, "decoded": {
                "portnum": "POSITION_APP",
                "position": {"latitude": lat, "longitude": lon}}})
            mission.on_packet({"fromId": node_id, "decoded": {
                "portnum": "TELEMETRY_APP",
                "telemetry": {"environmentMetrics": {
                    "temperature": 21.5 + step, "relativeHumidity": 60 + step,
                    "barometricPressure": 1013.2}}}})
    mission.summary()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", help="serial port (default: auto-detect)")
    p.add_argument("--csv", default=str(HERE / "mission_log.csv"))
    p.add_argument("--html", default=str(HERE / "coverage.html"))
    p.add_argument("--teams", default=str(HERE.parent / "gridmap" / "teams.json"))
    p.add_argument("--nodes", default=str(HERE / "nodes.json"),
                   help="JSON mapping node short name/id -> team name")
    p.add_argument("--test", action="store_true",
                   help="run with synthetic packets (no radio)")
    args = p.parse_args()

    mission = Mission(args.csv, args.html, args.teams, args.nodes)

    if args.test:
        run_test(mission)
        return

    import meshtastic.serial_interface
    from pubsub import pub

    pub.subscribe(lambda packet, interface: mission.on_packet(packet, interface),
                  "meshtastic.receive")
    iface = meshtastic.serial_interface.SerialInterface(devPath=args.port)
    print(f"mission control listening (log: {args.csv}). Ctrl-C for summary.")

    def stop(*_):
        mission.summary()
        iface.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
