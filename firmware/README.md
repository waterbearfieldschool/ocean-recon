# Firmware options for MGRS on the display

Two ways to get the grid reference onto the Heltec V4's screen. Both work with
the same maps, base station, and mission plan.

## Option A — dt267 low-power fork (what we're using for the mission)

<https://github.com/dt267/MeshCore-Low-Power-Firmware-For-Heltec-V3-V4>

Prebuilt, community-tested, and feature-rich: Settings → **Pos. Format →
MGRS** puts `19TCG0136228411` on the GPS page and Quick Send status bar, plus
deep power optimization (multi-day battery), Quick Send presets, the full
on-device companion UI, config backup portal, and QuickLink I2C sensor
support. Zero firmware development risk — flash and go. See
`docs/radio-setup.md`.

Trade-offs: you're tracking a third-party fork (its release cadence, its
choices), and the whole firmware differs from upstream in many ways at once —
harder to audit, and behavior can differ from stock documentation.

## Option B — minimal patch on stock MeshCore (this directory)

A ~100-line patch against upstream <https://github.com/meshcore-dev/MeshCore>
that changes exactly one thing: the companion GPS page. Stock already shows
`pos 41.7827 -71.3903` (decimal degrees); the patch replaces the `pos`/`alt`
rows with:

```
gps on          fix
sat              9
mgrs  19TCG0136228411     <- full MGRS reference
grid       013-284        <- the pair the kids match to the map
```

Files:

- `MGRS.h` — self-contained WGS84→MGRS conversion (~70 lines, no
  dependencies, sub-meter accurate; validated against the Python `mgrs`
  library on 9 points across both hemispheres, even/odd zones, and high
  latitudes — exact match on all).
- `mgrs-display.patch` — adds `MGRS.h` to the companion UI and swaps the two
  display rows. Generated against upstream commit `bbb58cc` (2026-07-07).
- `heltec_v4_companion_radio_usb_mgrs.bin` — prebuilt from that commit +
  patch (PlatformIO build verified: SUCCESS, RAM 5.5% / flash 10.3%). This is
  an application-only image (USB connection mode): flash at `0x10000` over a
  device that already has a MeshCore bootloader/partition table. **Display
  behavior not yet tested on hardware** — try it on one radio first.

Build and flash:

```bash
git clone https://github.com/meshcore-dev/MeshCore.git
cd MeshCore
git apply ../mgrs-display.patch      # or: patch -p1 < .../mgrs-display.patch
pip install platformio
pio run -e heltec_v4_companion_radio_usb     # or _ble
python -m esptool --chip esp32s3 write_flash 0x10000 \
    .pio/build/heltec_v4_companion_radio_usb/firmware.bin
```

Trade-offs: you build it yourself and re-apply the patch when you pull
upstream updates; you don't get the fork's power optimization, on-device
Quick Send/Settings UI, or presets (stock's on-device UI is much more
minimal — messages are sent from the phone app). GPS page navigation on
stock: short-press the user button to cycle home-screen pages.

## Which is better?

**For the mission: Option A.** It's ready now, battery-optimized for a day on
the water, and the kids can Quick Send from the device without phones.

**As a direction: Option B is worth keeping alive.** It's a tiny, auditable
diff you control, it tracks upstream, and it's upstreamable — a
`Pos. Format`-style setting or this exact GPS-page change would make a good
pull request to meshcore-dev/MeshCore, after which no fork or patch would be
needed at all. It's also a great STEM artifact in itself: "we patched the
radio's firmware to speak the search-and-rescue grid" is one more layer of
the lesson.
