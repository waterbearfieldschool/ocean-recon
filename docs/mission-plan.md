# Ocean Recon — mission plan (sailing camp STEM lesson)

**The mission:** Edgewood's waters need an environmental survey. Each boat is a
recon vessel carrying a MeshCore mesh radio with GPS, plus a handheld
instrument. Sail to your team's priority grid squares, hold position, record
the reading — then press Quick Send, and the mesh network carries your
position back to mission control on shore.

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
- **Reading the radio**: the screen shows `19TCG0136228411`. Everything here is
  inside zone `19TCG`, so ignore that part; split the 10 remaining digits in
  half — `01362` | `28411` — and take the **first 3 of each half**: square
  **013-284**. Find column 013 and row 284 on your map — that's where you are.
- **Ham radio connection**: amateur radio operators do the same thing with the
  *Maidenhead* grid — we're in square **FN41hs** — and log contacts around the
  world by grid square.
- **Mesh networking**: no cell towers out there. Your radios relay each other's
  messages — a reading from the far end of the survey area may hop through
  another boat to reach shore. More boats = stronger network.

## Rules of the game

1. Each team has **5 priority squares** (shaded on your map) worth **3 points**;
   any other new square your team logs is worth **1 point**.
2. A square counts when you're **inside it on the radio screen**, you've
   **written the reading on your data sheet** (square, time, value), and you've
   pressed **Quick Send → "Reading taken"** so shore hears it.
3. The shore station logs every Quick Send with its position — your paper sheet
   is checked against it at debrief, like real scientists validating data.
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
