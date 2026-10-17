"""Minimal METAR parser that emits the same JSON shape as the aviationweather.gov
Data API (api/data/metar?format=json), so existing clients can read it unchanged.

Only the fields our displays use are produced. Unofficial, advisory-only data.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

WX_CODES = {
    "MI", "PR", "BC", "DR", "BL", "SH", "TS", "FZ",
    "DZ", "RA", "SN", "SG", "IC", "PL", "GR", "GS", "UP",
    "BR", "FG", "FU", "VA", "DU", "SA", "HZ", "PY", "PO", "SQ", "FC", "SS", "DS",
}

RE_TIME = re.compile(r"^(\d{2})(\d{2})(\d{2})Z$")
RE_WIND = re.compile(r"^(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?KT$")
RE_WIND_VAR = re.compile(r"^\d{3}V\d{3}$")
RE_VIS = re.compile(r"^(M)?(\d+)?(?:(\d)/(\d{1,2}))?SM$")
RE_CLOUD = re.compile(r"^(FEW|SCT|BKN|OVC|VV)(\d{3}|///)(CB|TCU)?$")
RE_TEMP = re.compile(r"^(M?\d{2})/(M?\d{2})?$")
RE_ALT = re.compile(r"^A(\d{4})$")
RE_TGROUP = re.compile(r"^T([01])(\d{3})([01])(\d{3})$")


def _obs_epoch(dd: int, hh: int, mm: int, now: datetime) -> int:
    """Turn a ddhhmmZ group into epoch seconds, picking the month that puts it nearest 'now'."""
    best = None
    for months_back in (0, 1):
        y, m = now.year, now.month - months_back
        if m < 1:
            y, m = y - 1, 12
        try:
            t = datetime(y, m, dd, hh, mm, tzinfo=timezone.utc)
        except ValueError:
            continue
        if t <= now + timedelta(hours=2) and (best is None or t > best):
            best = t
    return int(best.timestamp()) if best else 0


def _is_wx(tok: str) -> bool:
    core = tok
    if core.startswith(("+", "-")):
        core = core[1:]
    elif core.startswith("VC"):
        core = core[2:]
    if not core or len(core) % 2:
        return False
    return all(core[i:i + 2] in WX_CODES for i in range(0, len(core), 2))


def _temp(s: str) -> float:
    return -float(s[1:]) if s.startswith("M") else float(s)


def flight_category(ceiling: int | None, vis: float | None) -> str:
    def by_cig(c):
        if c is None:
            return 0
        return 3 if c < 500 else 2 if c < 1000 else 1 if c <= 3000 else 0

    def by_vis(v):
        if v is None:
            return 0
        return 3 if v < 1 else 2 if v < 3 else 1 if v <= 5 else 0

    return ["VFR", "MVFR", "IFR", "LIFR"][max(by_cig(ceiling), by_vis(vis))]


def parse(raw: str, *, lat: float, lon: float, elev_m: int, name: str,
          now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    raw = " ".join(raw.split())
    toks = raw.split(" ")
    out: dict = {
        "icaoId": "", "obsTime": 0, "metarType": "METAR", "rawOb": raw,
        "lat": lat, "lon": lon, "elev": elev_m, "name": name,
        "wdir": None, "wspd": None, "wgst": None, "visib": None,
        "temp": None, "dewp": None, "altim": None,
        "wxString": "", "cover": "CLR", "clouds": [], "fltCat": None,
    }
    i = 0
    if toks and toks[0] in ("METAR", "SPECI", "OMO"):
        out["metarType"] = toks[0]
        out["rawOb"] = " ".join(toks[1:])        # AWC's rawOb has no METAR/SPECI prefix
        i = 1
    if i < len(toks):
        out["icaoId"] = toks[i]
        i += 1

    wx, vis, ceiling = [], None, None
    in_rmk = False
    j = i
    while j < len(toks):
        t = toks[j]
        if t == "RMK":
            in_rmk = True
            j += 1
            continue
        if in_rmk:
            m = RE_TGROUP.match(t)
            if m:
                out["temp"] = (-1 if m[1] == "1" else 1) * int(m[2]) / 10
                out["dewp"] = (-1 if m[3] == "1" else 1) * int(m[4]) / 10
            j += 1
            continue

        if (m := RE_TIME.match(t)):
            out["obsTime"] = _obs_epoch(int(m[1]), int(m[2]), int(m[3]), now)
        elif t in ("AUTO", "COR") or RE_WIND_VAR.match(t):
            pass
        elif (m := RE_WIND.match(t)):
            out["wdir"] = "VRB" if m[1] == "VRB" else int(m[1])
            out["wspd"] = int(m[2])
            out["wgst"] = int(m[3]) if m[3] else None
        elif t.isdigit() and len(t) == 1 and j + 1 < len(toks) and RE_VIS.match(toks[j + 1]) and "/" in toks[j + 1]:
            m = RE_VIS.match(toks[j + 1])          # "1 1/2SM"
            vis = int(t) + int(m[3]) / int(m[4])
            j += 1
        elif (m := RE_VIS.match(t)):
            whole = int(m[2]) if m[2] else 0
            frac = int(m[3]) / int(m[4]) if m[3] else 0
            vis = whole + frac
        elif t in ("CLR", "SKC", "NCD", "NSC", "CAVOK"):
            out["cover"] = "CLR" if t != "SKC" else "SKC"
            if t == "CAVOK":
                vis = 10.0
        elif (m := RE_CLOUD.match(t)):
            if m[2] != "///":
                cover = "OVX" if m[1] == "VV" else m[1]
                base = int(m[2]) * 100
                out["clouds"].append({"cover": cover, "base": base})
                out["cover"] = cover
                if cover in ("BKN", "OVC", "OVX") and (ceiling is None or base < ceiling):
                    ceiling = base
        elif (m := RE_TEMP.match(t)):
            if out["temp"] is None:
                out["temp"] = _temp(m[1])
            if m[2] and out["dewp"] is None:
                out["dewp"] = _temp(m[2])
        elif (m := RE_ALT.match(t)):
            out["altim"] = round(int(m[1]) / 100 * 33.8639, 1)   # hPa, like the AWC API
        elif _is_wx(t):
            wx.append(t)
        j += 1

    out["wxString"] = " ".join(wx)
    if vis is not None:
        out["visib"] = "10+" if vis >= 10 else (int(vis) if float(vis).is_integer() else round(vis, 2))
    out["fltCat"] = flight_category(ceiling, vis)
    return out
