"""Relay KFWQ's AWOS reports from the public AWOS Live page into static JSON files.

Loads https://kfwq.awos.live/home in headless Chromium, reads the METAR/SPECI
lines the page displays, and writes:

  docs/kfwq.json          latest report, same shape as aviationweather.gov's metar API
  docs/kfwq.txt           latest raw report
  docs/kfwq-history.json  every report shown on the page, newest first

Files are rewritten only when a new report appears, so the repo only changes on
new observations. UNOFFICIAL, advisory only: these reports are not disseminated
to the FAA and must not be used for flight planning.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).parent))
import metar  # noqa: E402

STATION = "KFWQ"
URL = "https://kfwq.awos.live/home"
LAT, LON, ELEV_M, NAME = 40.2097, -79.8314, 374, "Rostraver"
SOURCE = "KFWQ AWOS Live (Mesotech). UNOFFICIAL: not FAA-disseminated, advisory only."
OUT = Path(__file__).resolve().parent.parent / "docs"
RE_REPORT = re.compile(rf"^(?:METAR|SPECI) {STATION} \d{{6}}Z .*$", re.M)


async def page_text() -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
            # Reports arrive over the page's live feed a few seconds after load.
            await page.wait_for_function(
                f"/(METAR|SPECI) {STATION} \\d{{6}}Z/.test(document.body.innerText)",
                timeout=60_000,
            )
            await page.wait_for_timeout(2_000)
            return await page.evaluate("document.body.innerText")
        finally:
            await browser.close()


def main() -> int:
    text = ""
    for attempt in range(3):
        try:
            text = asyncio.run(page_text())
            break
        except Exception as e:  # noqa: BLE001
            print(f"attempt {attempt + 1} failed: {e}", file=sys.stderr)
    reports = [" ".join(r.split()) for r in RE_REPORT.findall(text)]
    if not reports:
        print("no reports found on page", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    parsed = [metar.parse(r, lat=LAT, lon=LON, elev_m=ELEV_M, name=NAME, now=now) for r in reports]
    parsed.sort(key=lambda o: o["obsTime"], reverse=True)
    latest = parsed[0]

    OUT.mkdir(exist_ok=True)
    cur = OUT / "kfwq.txt"
    if cur.exists() and cur.read_text().strip() == latest["rawOb"]:
        print("no new report:", latest["rawOb"])
        return 0

    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    for o in parsed:
        o["source"] = SOURCE
    latest["relayTime"] = stamp
    (OUT / "kfwq.json").write_text(json.dumps([latest], separators=(",", ":")) + "\n")
    (OUT / "kfwq-history.json").write_text(json.dumps(parsed, separators=(",", ":")) + "\n")
    cur.write_text(latest["rawOb"] + "\n")
    print("new report:", latest["rawOb"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
