# Ocean Recon

Sailing-camp STEM mission at Edgewood (Providence River, Cranston RI): kids on
sailboats carry Heltec V4 Meshtastic radios with GPS and environmental sensors,
collect readings across MGRS 100 m grid squares, and the mesh relays everything
to a shore-side mission control laptop.

The radios' displays are set to MGRS (`display.gps_format MGRS`), so the whole
activity runs on stock Meshtastic firmware — kids read `19T CG 01362 28411` off
the screen, take the first 3 digits of each number group, and find square
`013-284` on their printed map.

## Rationale

The original design brief, in brief: we have Meshtastic radios with displays,
GPS, and room for a sensor on each board. Give every crew one radio and one
instrument, divide the waters around Edgewood into grid squares, and hand each
team a printed map with priority squares to cover. The radio's screen tells a
crew what they're measuring and which square they're in; the map and their own
orientation tell them where to go next. The mission is simply to make sure
enough squares have data before they sail home — while every reading streams
back over the mesh to shore.

Two requirements shaped the design. First, the coordinate system had to be
*legible*: raw GPS latitude/longitude means little to most people, so the map
needed a grid you can read at a glance — with the ham-radio grid-square
tradition as inspiration and a STEM touchstone. Second, it had to be
*printable*: a grid you can overlay on a real map of Edgewood, hand to a kid
in a boat, and navigate by. The USNG/MGRS grid below is where those two
requirements met.

## Background

### Why this mission

The activity packs three real practices into one afternoon of sailing: reading
a position off an instrument and plotting it on a gridded map, making a careful
environmental measurement and writing it down, and moving data over an
independent radio network when there's no infrastructure on the water. Each
team's map, radio, and sensor are the same tools — at kid scale — that
professionals use for the same jobs.

### The grid: USNG / MGRS, the search-and-rescue standard

The map grid is **USNG (US National Grid)**, the civilian twin of the military
MGRS — the coordinate system actually used by search and rescue teams, FEMA,
and the National Guard in the US. It's UTM-based, so squares are true squares
in meters, and it works at whatever resolution you want: 1000 m, 100 m, or
10 m squares, just by truncating digits. A position reads like
`19T CG 1234 5678`, but within a small local area kids only need the last few
digits — effectively "grid 34, 78." It's legible, and it's real-world: this is
the grid printed on official SAR maps, which makes it a great resilience-
curriculum tie-in. (Ham radio operators use a cousin of this idea, the
Maidenhead locator — Edgewood is in `FN41hs` — to log contacts worldwide;
it's noted on each printed map.)

### Ships as weather stations: an old tradition, still alive

Boats recording ocean and weather observations is one of the oldest citizen-
science traditions there is. In the age of sail, navies and merchant captains
kept meticulous logs of winds, currents, and temperatures; in the 1840s–50s
Matthew Fontaine Maury collected thousands of those logbooks into the first
wind and current charts, cutting weeks off major passages and helping launch
the international system of standardized marine weather observation. That
system never stopped: today thousands of commercial vessels in the WMO's
Voluntary Observing Ship program still radio in weather reports, while Argo
floats and uncrewed sail drones sweep the oceans for temperature and salinity
data that feeds weather forecasts and climate models. A sailboat crossing a
grid square and reporting the conditions there is exactly this tradition —
the kids are the newest crew in a data-collecting fleet that's been underway
for almost two centuries.

## Layout

- `gridmap/make_map.py` — printable grid maps (PDF/PNG, letter or ledger); one
  master map plus one per team with priority squares highlighted
- `gridmap/teams.json` — teams, colors, priority squares
- `basestation/log_mesh.py` — mission control: logs mesh position/telemetry to
  CSV, live coverage map (`coverage.html`), per-team scoring on Ctrl-C
- `basestation/nodes.json` — radio short name → team
- `docs/radio-setup.md` — night-before radio/sensor configuration checklist
- `docs/mission-plan.md` — lesson outline, briefing script, rules, data sheet
- `maps/` — generated output (not committed)

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# generate maps (needs internet for basemap tiles)
.venv/bin/python gridmap/make_map.py --size ledger

# mission control (Heltec on USB), or --test for a dry run
.venv/bin/python basestation/log_mesh.py
```
