# KFWQ AWOS relay

Rostraver's (KFWQ) Mesotech AWOS-3PT publishes METAR and SPECI reports on its
[AWOS Live page](https://kfwq.awos.live/home), but they aren't yet disseminated
to the FAA, so they don't appear on aviationweather.gov or in ForeFlight.

A GitHub Actions job runs every 5 minutes, reads the page in headless Chromium,
and commits the latest report here whenever a new one appears.

| File | Contents |
|---|---|
| [`docs/kfwq.json`](docs/kfwq.json) | Latest report as a one-item array, same shape as `aviationweather.gov/api/data/metar?format=json` |
| [`docs/kfwq.txt`](docs/kfwq.txt) | Latest raw report |
| [`docs/kfwq-history.json`](docs/kfwq-history.json) | Every report shown on the page, newest first |

Raw URL for devices:
`https://raw.githubusercontent.com/hartman39/kfwq-wx-relay/main/docs/kfwq.json`

Expect up to roughly 10–20 minutes from observation to relay: GitHub's
scheduler often runs late, and raw.githubusercontent.com caches for about 5 minutes.

> **Unofficial and advisory only.** This data is not disseminated by the FAA and
> must not be used for flight planning or operations. Use the AWOS on 118.475 or
> (724) 379-5815.

Run the parser tests with `python -m pytest tests`.
