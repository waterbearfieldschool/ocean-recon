# Radio + sensor setup checklist (do this the night before)

One Heltec V4 + GPS module + one I2C sensor per team, plus one radio for the
base station laptop. All commands use the Meshtastic CLI from this repo's venv:

```bash
alias mt='.venv/bin/meshtastic'
```

Plug in one radio at a time (the CLI auto-detects the serial port).

## 1. Per-radio basics

```bash
mt --set lora.region US
mt --set-owner-short SEAL        # unique 4-char name per radio: SEAL, OSPR, BASS, BASE...
```

The short name is how the radio appears in the base station log — make it match
`basestation/nodes.json` (or edit that file to match your names).

## 2. Shared private channel (keeps camp traffic off the public mesh)

On the FIRST radio:

```bash
mt --ch-set name OceanRecon --ch-set psk random --ch-index 0
mt --info          # copy the "Complete URL" it prints
```

On EVERY OTHER radio:

```bash
mt --seturl 'https://meshtastic.org/e/#...'   # the URL from above
```

## 3. GPS + MGRS display

```bash
mt --set position.gps_mode ENABLED
mt --set display.gps_format MGRS
mt --set position.position_broadcast_secs 60
mt --set position.position_broadcast_smart_enabled true
```

- The Heltec GPS module goes on its dedicated connector. If `--info` /the
  screen never shows satellites, the UART pins need setting explicitly
  (`gps.rx_pin` / `gps.tx_pin` for your module wiring) — but the standard
  Heltec module should be plug-and-play.
- **Take each radio outside and confirm a GPS lock** (satellite count on the
  GPS screen) before calling it done. First lock can take a few minutes.
- Once locked, the position screen shows e.g. `19T CG 01362 28411` — that's
  the MGRS readout the kids use.

## 4. Environment sensor (one I2C sensor per radio)

Wire the sensor to the I2C pins (SDA/SCL + 3.3 V/GND). Meshtastic auto-detects
common sensors at boot: BME280/BMP280, SHT31/40/41, AHT10/20, INA219/260, etc.

```bash
mt --set telemetry.environment_measurement_enabled true
mt --set telemetry.environment_screen_enabled true
mt --set telemetry.environment_update_interval 60
```

Reboot the radio (power cycle) after wiring so the I2C scan runs. The display
carousel should now include an environment screen with the live reading, and
readings broadcast over the mesh every ~60 s.

## 5. Base station

- One configured radio stays ashore, plugged into the laptop via USB.
- Run: `.venv/bin/python basestation/log_mesh.py`
- Open `basestation/coverage.html` in a browser; refresh to see coverage fill in.
- `Ctrl-C` at mission end prints per-team scores.
- Dry-run without hardware anytime: `... log_mesh.py --test`

## 6. Field prep

- [ ] Every radio: GPS lock verified outdoors, MGRS shows on screen
- [ ] Every radio: sensor screen shows a plausible reading
- [ ] Send a test message between radios on the OceanRecon channel
- [ ] Base station logs a position from each radio (check the CSV)
- [ ] Ziplock / dry bag + lanyard per radio (screen readable through the bag)
- [ ] USB power bank + cable per boat
- [ ] Screen timeout long enough to read (`mt --set display.screen_on_secs 300`)
- [ ] Printed team maps (`maps/*.pdf`) + pencils + data sheets
