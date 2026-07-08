# Radio setup checklist — MeshCore on Heltec V4 (do this the night before)

The radios run the **dt267 low-power MeshCore fork**, which adds the one
feature this mission depends on: on-screen coordinates in **MGRS** format
(stock MeshCore only shows decimal degrees, and only this fork has the
Pos. Format setting).

Firmware: <https://github.com/dt267/MeshCore-Low-Power-Firmware-For-Heltec-V3-V4>

## 1. Flash each radio

Download the latest **Heltec V4 companion** `_merged.bin` from the repo's
Releases page, then flash it at address `0x0` (full install):

```bash
.venv/bin/pip install esptool          # once
python -m esptool --chip esp32s3 write_flash 0x0 Heltec_v4_companion_radio_*_merged.bin
```

The companion build is unified — BLE, USB serial, and WiFi in one image, and
it auto-detects the OLED. For later firmware updates, flash the plain `.bin`
at `0x10000` instead (settings survive).

## 2. On-device settings (via the screen's Settings page)

Navigate with the user button (short press = next, long press = select):

- **Pos. Format → MGRS** ← the whole mission. The GPS page, GPS Trace, and
  Quick Send status bar now show e.g. `19TCG0136228411`.
- **GPS Privacy → off** — so Quick Send messages carry coordinates to shore.
- **Connection Mode**: leave BLE on the kids' radios; set **USB** on the base
  station radio so the laptop can talk to it over serial.

## 3. CLI settings (TerminalCLI over USB, or via the MeshCore app)

```
set gps.interval 10        # fix every 10 s (default; 0 = always on)
set gps.mode 4             # GPS + BeiDou + GLONASS (default, most robust fix)
set quick.0 Reading taken  # Quick Send preset the kids will use
set quick.1 Priority square done
set quick.2 Returning to dock
```

Give each radio a recognizable name in the MeshCore app (SEAL, OSPR, BASS,
BASE...) and make it match `basestation/nodes.json`.

Quick Send always transmits on the **Public channel**, which is what the base
station listens to — no channel setup needed for the mission itself.

## 4. How a crew reads its square

The screen shows: `19TCG0136228411`

- `19TCG` — the zone; same for the whole sailing area, ignore it.
- The 10 digits split in half: `01362` | `28411`.
- First 3 of each half: **013** and **284** → **square 013-284** on the map.

(Every printed map repeats this recipe in its top margin.)

## 5. Field procedure (this replaces automatic telemetry)

MeshCore doesn't broadcast positions continuously the way Meshtastic does —
positions travel with messages. So the drill in each square is:

1. Read your square off the GPS page.
2. Take the measurement, write square + time + value on the data sheet.
3. **Quick Send → "Reading taken"** — the message (with coordinates attached)
   hops through the mesh to shore, and the square lights up at mission control.

## 6. Sensors — deferred (collect by hand for now)

Readings are taken with handheld instruments and recorded on paper this time.
When we're ready: this fork supports environment sensors on the Heltec V4's
QuickLink I2C port (BME280-family auto-detected at 0x76/0x77), so the same
boards can grow into sensor nodes later.

## 7. Base station

- The USB-mode radio stays ashore, plugged into the laptop.
- Run: `.venv/bin/python basestation/log_meshcore.py --port /dev/ttyUSB0`
- Open `basestation/coverage.html` in a browser; refresh to watch squares fill.
- `Ctrl-C` prints per-team scores.
- **IMPORTANT: test with real radios before mission day** — the logger is
  written against meshcore_py's documented API but hasn't touched hardware
  yet. Send a Quick Send from a second radio and confirm a CSV row appears
  with a square. (The raw payload is logged in the last column, so even if
  coordinate parsing needs a tweak, no data is lost.)
- Dry-run without hardware anytime: `... log_meshcore.py --test`

## 8. Field prep

- [ ] Every radio: GPS lock verified outdoors, MGRS string on the GPS page
- [ ] Every radio: GPS Privacy off; Quick Send test heard by base station
- [ ] Base station: CSV row with correct square from each radio
- [ ] Ziplock / dry bag + lanyard per radio (screen readable through the bag)
- [ ] USB power bank + cable per boat
- [ ] Printed team maps (`maps/*.pdf`) + pencils + data sheets + handheld
      thermometers (or whichever instruments each team carries)
