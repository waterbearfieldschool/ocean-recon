# Ocean Recon mission firmware (modified stock MeshCore)

A small patch against upstream <https://github.com/meshcore-dev/MeshCore>
(commit `bbb58cc`, 2026-07-07) that turns the stock Heltec V4 companion
firmware into the mission radio. Four changes, ~230 patch lines total:

1. **MGRS on the GPS page.** Stock shows decimal degrees; patched shows the
   full reference and the map pair:
   ```
   gps on          fix
   sat               9
   mgrs  19TCG0136228411
   grid       013-284
   ```
2. **Private `edgewood` channel, pre-provisioned.** Created at boot as
   channel 1 (alongside the default Public at 0), so every radio flashed with
   this firmware shares the mission channel with zero app setup.
3. **RECON page — one-button grid report.** A new home-screen page shows the
   current grid square in large text; long-press sends
   `grid 013-284 41.782712,-71.390298` **on the edgewood channel** (not
   Public — nothing lands on the public mesh). Shows "Report sent!" /
   "No GPS fix yet".
4. **Auto-advert on boot.** ~25 s after power-up each radio sends one advert
   (its signed public key + name), so all nodes and the base station learn
   each other's credentials without anyone pressing anything. The stock
   ADVERT page (long-press to re-advertise) is still there too.

Files:

- `MGRS.h` — self-contained WGS84→MGRS conversion (~70 lines, no deps,
  sub-meter accurate; validated against the Python `mgrs` library on 9 points
  across both hemispheres and even/odd zones — exact match on all).
- `ocean-recon-mission.patch` — all four changes (touches `MyMesh.h/.cpp` and
  `ui-new/UITask.cpp`, adds `ui-new/MGRS.h`).
- `heltec_v4_companion_radio_usb_recon.bin` — prebuilt from that commit +
  patch (PlatformIO build verified: SUCCESS). Application-only image (USB
  connection mode): flash at `0x10000` over a device that already has a
  MeshCore bootloader/partition table. **On-screen and on-air behavior not
  yet tested on hardware** — try one radio first, and confirm a report from a
  second radio reaches `basestation/log_meshcore.py`.

## SECURITY NOTE — the channel key is in a public repo

The `edgewood` PSK is hardcoded in the patch (`EDGEWOOD_GROUP_PSK` in
`MyMesh.cpp`), and this repo is public — so treat the channel as
"not-cluttering-Public" rather than cryptographically private. To make it
actually private, generate a fresh key and rebuild:

```bash
python3 -c "import base64,os; print(base64.b64encode(os.urandom(16)).decode())"
# paste the output into EDGEWOOD_GROUP_PSK before building
```

## Build and flash

```bash
git clone https://github.com/meshcore-dev/MeshCore.git
cd MeshCore
git apply ../ocean-recon-mission.patch
pip install platformio esptool
pio run -e heltec_v4_companion_radio_usb        # or _ble
python -m esptool --chip esp32s3 write_flash 0x10000 \
    .pio/build/heltec_v4_companion_radio_usb/firmware.bin
```

Flash the **base station radio with the same firmware** so it has the
edgewood channel and can decrypt the reports.

## Why not the dt267 fork for this?

The dt267 low-power fork's Quick Send is hardwired to the Public channel,
and the fork **publishes no source code** (its repo is documentation +
binary releases only), so it can't be patched. If you want the fork's power
optimizations *and* a private-channel Quick Send, file a feature request
there — until then, this modified stock build is the private-channel path.
For a 1–2 hour on-the-water mission, stock power draw is a non-issue; the
fork's low-power work matters for multi-day idle deployments.

Field procedure on this firmware: short-press cycles pages → RECON page shows
your square big → hold the button → "Report sent!" → square lights up at
mission control.
