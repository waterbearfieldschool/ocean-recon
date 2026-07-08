# Ocean Recon

Sailing-camp STEM mission at Edgewood (Providence River, Cranston RI): kids on
sailboats carry Heltec V4 MeshCore radios with GPS, collect readings across
MGRS 100 m grid squares (by hand for now — onboard sensors later), and Quick
Send messages carry each position over the mesh to a shore-side mission
control laptop.

The radios run the [dt267 low-power MeshCore
fork](https://github.com/dt267/MeshCore-Low-Power-Firmware-For-Heltec-V3-V4),
whose **Pos. Format → MGRS** setting puts the grid reference right on the
screen (stock MeshCore only shows decimal degrees). Kids read
`19TCG0136228411`, split the 10 digits in half (`01362` | `28411`), take the
first 3 of each, and find square `013-284` on their printed map.

> Alternatives: `firmware/` holds a **minimal MGRS patch for stock MeshCore**
> (a ~100-line diff that puts the full reference plus the `013-284` pair on
> the stock GPS page) — see `firmware/README.md` for the trade-offs. And
> stock **Meshtastic** firmware displays MGRS natively
> (`display.gps_format MGRS`); `basestation/log_mesh.py` supports that path.

## Rationale

The original design brief, in brief: we have mesh radios with displays,
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
- `basestation/log_meshcore.py` — mission control (MeshCore): logs messages and
  their attached positions to CSV, live coverage map (`coverage.html`),
  per-team scoring on Ctrl-C
- `basestation/log_mesh.py` — same idea for the Meshtastic firmware path
- `basestation/nodes.json` — radio name → team
- `docs/radio-setup.md` — night-before flashing + configuration checklist
- `firmware/` — alternative: minimal patch adding MGRS display to stock
  MeshCore (`MGRS.h` + `mgrs-display.patch` + build instructions)
- `docs/mission-plan.md` — lesson outline, briefing script, rules, data sheet
- `index.html` — shareable project explainer (web + print in one file)
- `docs/ocean-recon-explainer.pdf` — the same explainer, rendered for printing
- `maps/` — the printable grid maps (regenerate with `gridmap/make_map.py`)

## Sharing the explainer

`index.html` is self-contained (its map image lives in `docs/assets/`) and
doubles as the source for the PDF:

- **Web**: enable GitHub Pages (repo Settings → Pages → deploy from branch
  `main`, folder `/ (root)`) and the explainer appears at
  `https://<user>.github.io/ocean-recon/`. Or just open the file locally.
- **PDF**: `.venv/bin/weasyprint index.html docs/ocean-recon-explainer.pdf`
  (weasyprint is in `requirements.txt`); the print stylesheet paginates it to
  three letter-size pages.

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# generate maps (needs internet for basemap tiles)
.venv/bin/python gridmap/make_map.py --size ledger

# mission control (MeshCore radio on USB), or --test for a dry run
.venv/bin/python basestation/log_meshcore.py --port /dev/ttyUSB0
```
