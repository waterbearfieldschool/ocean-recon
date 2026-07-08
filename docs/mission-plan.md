# Ocean Recon — mission plan (sailing camp STEM lesson)

**The mission:** Edgewood's waters need an environmental survey. Each boat is a
recon vessel carrying a mesh radio with GPS and a science sensor. Sail to your
team's priority grid squares, hold position, record the reading, and the mesh
network relays your data back to mission control on shore.

## Timeline (~90 min)

| When | What |
|---|---|
| 10 min | Briefing: how it works, how to read the grid |
| 10 min | Hand out radios + maps, radio check from the dock |
| 45–60 min | On the water collecting squares |
| 15 min | Debrief: coverage map reveal + scores |

## Briefing talking points (the STEM content)

- **GPS**: ~30 satellites broadcasting time signals; your radio hears 4+ and
  solves for where it is. That position is a pair of numbers (latitude/longitude)
  — accurate, but hard to say over a radio or plot fast on a chart.
- **Grid squares**: so navigators chop the world into named squares. Ours is
  **MGRS** — the grid used by the military, the Coast Guard, and search-and-rescue
  teams, printed on your map as 100 m squares.
- **Reading the radio**: the screen shows `19T CG 01362 28411`. Everything here
  is inside zone `19T CG`, so you only need the **first 3 digits of each number
  group**: square **013-284**. Find column 013 and row 284 on your map — that's
  where you are.
- **Ham radio connection**: amateur radio operators do the same thing with the
  *Maidenhead* grid — we're in square **FN41hs** — and log contacts around the
  world by grid square.
- **Mesh networking**: no cell towers out there. Your radios relay each other's
  messages — a reading from the far end of the survey area may hop through
  another boat to reach shore. More boats = stronger network.

## Rules of the game

1. Each team has **5 priority squares** (shaded on your map) worth **3 points**;
   any other new square your team logs is worth **1 point**.
2. A square counts when you're **inside it on the radio screen** and you've
   **written the reading on your data sheet** (square, time, value).
3. The shore station is logging everything automatically — your paper sheet is
   checked against it at debrief, like real scientists validating data.
4. Stay west of the channel markers. Safety boat's word is final.

## Data sheet (print a few per team)

| # | Square (e.g. 017-284) | Time | Reading | Notes (waves, boats, birds...) |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| ... | | | | |

## Debrief

1. Open `basestation/coverage.html` on a big screen — watch which squares filled in.
2. `Ctrl-C` the logger for per-team scores (priority hits + total squares).
3. Compare paper sheets to the CSV: did the mesh see what you saw?
4. Science discussion: did temperature differ near shore vs mid-river? Sheltered
   cove vs open water? Why might that matter (fish, sailing wind, weather)?

## Instructor knobs

- Priority squares / team colors: `gridmap/teams.json`, then regenerate maps:
  `.venv/bin/python gridmap/make_map.py --size ledger`
- Radio↔team assignment: `basestation/nodes.json`
- Map area: `--bounds S W N E` flag on `make_map.py`
