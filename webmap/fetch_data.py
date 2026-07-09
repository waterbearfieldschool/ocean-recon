#!/usr/bin/env python3
"""Snapshot the bayou feed history to data.json for the static replay page.

Usage:
    python3 fetch_data.py            # writes data.json next to this script
    python3 fetch_data.py out.json
"""
import json
import sys
import urllib.request
from pathlib import Path

FEED = "https://bayou.pvos.org/data/995ywq4zg2iq/json/"


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        Path(__file__).parent / "data.json"
    with urllib.request.urlopen(FEED, timeout=30) as r:
        feed = json.load(r)
    out.write_text(json.dumps(feed) + "\n")
    n = len(feed.get("data", []))
    stamps = [d["timestamp"] for d in feed.get("data", [])]
    span = f" ({min(stamps)} → {max(stamps)})" if stamps else ""
    print(f"wrote {out}: {n} records{span}")


if __name__ == "__main__":
    main()
