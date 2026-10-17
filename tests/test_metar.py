import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))
import metar  # noqa: E402

NOW = datetime(2026, 10, 17, 13, 50, tzinfo=timezone.utc)
KW = dict(lat=40.2097, lon=-79.8314, elev_m=374, name="Rostraver", now=NOW)


def p(raw):
    return metar.parse(raw, **KW)


def test_basic():
    o = p("METAR KFWQ 171255Z AUTO VRB06KT 10SM SCT018 SCT029 BKN049 07/05 A3029 RMK AO2 T00660047")
    assert o["icaoId"] == "KFWQ" and o["metarType"] == "METAR"
    assert o["obsTime"] == int(datetime(2026, 10, 17, 12, 55, tzinfo=timezone.utc).timestamp())
    assert o["wdir"] == "VRB" and o["wspd"] == 6 and o["wgst"] is None
    assert o["visib"] == "10+"
    assert o["temp"] == 6.6 and o["dewp"] == 4.7
    assert [c["base"] for c in o["clouds"]] == [1800, 2900, 4900]
    assert o["fltCat"] == "VFR"
    assert abs(o["altim"] - 1025.6) < 0.2


def test_gust_rain_mist_mvfr():
    o = p("SPECI KFWQ 170341Z AUTO 34009G15KT 310V020 6SM -RA BR FEW017 BKN022 09/09 A3003 RMK AO2 P0011 T00950091")
    assert o["metarType"] == "SPECI"
    assert (o["wdir"], o["wspd"], o["wgst"]) == (340, 9, 15)
    assert o["visib"] == 6 and o["wxString"] == "-RA BR"
    assert o["fltCat"] == "MVFR"          # BKN022


def test_ifr_vis():
    o = p("SPECI KFWQ 170319Z AUTO 33007KT 300V010 3SM RA BR BKN016 10/10 A3002 RMK AO2 P0009 T00980097")
    assert o["visib"] == 3 and o["fltCat"] == "MVFR"
    o = p("METAR KFWQ 170319Z AUTO 33007KT 1 1/2SM RA BR OVC006 10/10 A3002")
    assert o["visib"] == 1.5 and o["fltCat"] == "IFR"
    o = p("METAR KFWQ 170319Z AUTO 00000KT M1/4SM FG VV002 10/10 A3002")
    assert o["visib"] == 0.25 and o["clouds"] == [{"cover": "OVX", "base": 200}] and o["fltCat"] == "LIFR"


def test_clear_and_negative_temps():
    o = p("METAR KFWQ 171055Z AUTO VRB04KT 10SM CLR M02/M05 A3022 RMK AO2 T10221048")
    assert o["cover"] == "CLR" and o["clouds"] == []
    assert o["temp"] == -2.2 and o["dewp"] == -4.8


def test_previous_month():
    o = metar.parse("METAR KFWQ 302355Z AUTO 00000KT 10SM CLR 05/01 A3000",
                    **{**KW, "now": datetime(2026, 11, 1, 0, 10, tzinfo=timezone.utc)})
    assert datetime.fromtimestamp(o["obsTime"], timezone.utc) == datetime(2026, 10, 30, 23, 55, tzinfo=timezone.utc)
