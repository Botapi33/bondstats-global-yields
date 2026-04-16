import json
import os
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import urlopen, Request

API_KEY = os.environ.get("FRED_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing FRED_API_KEY environment variable.")

OUTPUT_FILE = "global_yields.json"

TIMEOUT = 10

# ---------------- SAFE FETCH ----------------

def fetch_json(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))

# ---------------- SERIES ----------------

SERIES = {
    "united_states": {
        "label": "United States",
        "series_id": "DGS10",
        "primary_source": "fred"
    },
    "euro_area": {
        "label": "Euro Area",
        "primary_source": "ecb"
    },
    "united_kingdom": {
        "label": "United Kingdom",
        "primary_source": "boe",
        "fallback_series_id": "IRLTLT01GBM156N"
    },
    "canada": {
        "label": "Canada",
        "primary_source": "boc",
        "series_id": "V39055",
        "fallback_series_id": "IRLTLT01CAM156N"
    },
    "australia": {
        "label": "Australia",
        "primary_source": "rba",
        "series_id": "F2",
        "fallback_series_id": "IRLTLT01AUM156N"
    }
}

# ---------------- FRED ----------------

def fetch_fred(series_id):
    url = f"https://api.stlouisfed.org/fred/series/observations?{urlencode({'series_id': series_id,'api_key': API_KEY,'file_type':'json','sort_order':'desc','limit':12})}"
    data = fetch_json(url)

    obs = [o for o in data["observations"] if o["value"] not in (".", "", None)]
    latest = obs[0]
    prev = obs[1] if len(obs) > 1 else None

    return {
        "date": latest["date"],
        "value": float(latest["value"]),
        "previousDate": prev["date"] if prev else None,
        "previousValue": float(prev["value"]) if prev else None,
        "change": float(latest["value"]) - float(prev["value"]) if prev else None
    }, "Monthly"

# ---------------- ECB ----------------

def fetch_ecb():
    url = "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?format=jsondata"
    data = fetch_json(url)

    series = next(iter(data["dataSets"][0]["series"].values()))
    obs = series["observations"]
    keys = sorted(obs.keys(), key=lambda x: int(x))

    latest_key = keys[-1]
    prev_key = keys[-2]

    time_index = data["structure"]["dimensions"]["observation"][0]["values"]

    return {
        "date": time_index[int(latest_key)]["id"],
        "value": float(obs[latest_key][0]),
        "previousDate": time_index[int(prev_key)]["id"],
        "previousValue": float(obs[prev_key][0]),
        "change": float(obs[latest_key][0]) - float(obs[prev_key][0])
    }, "Daily"

# ---------------- BOE ----------------

def fetch_boe():
    try:
        url = "https://api.allorigins.win/raw?url=https://www.bankofengland.co.uk/boeapps/database/FromShowColumns.asp?csv.x=yes&SeriesCodes=IUMAJNB"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urlopen(req, timeout=TIMEOUT).read().decode("utf-8")

        lines = [l for l in raw.splitlines() if "/" in l]
        parsed = []

        for l in lines:
            p = l.split(",")
            try:
                parsed.append((p[0], float(p[1])))
            except:
                continue

        parsed.sort(key=lambda x: datetime.strptime(x[0], "%d/%m/%Y"))

        latest = parsed[-1]
        prev = parsed[-2]

        return {
            "date": latest[0],
            "value": latest[1],
            "previousDate": prev[0],
            "previousValue": prev[1],
            "change": latest[1] - prev[1]
        }, "Daily"

    except Exception as e:
        print("BOE failed:", e)
        return None

# ---------------- BOC ----------------

def fetch_boc(series_id):
    try:
        url = f"https://www.bankofcanada.ca/valet/observations?seriesName={series_id}&recent=2"
        data = fetch_json(url)

        obs = data["observations"]
        parsed = [(o["d"], float(o[series_id]["v"])) for o in obs if o.get(series_id)]

        parsed.sort(key=lambda x: x[0])

        latest = parsed[-1]
        prev = parsed[-2] if len(parsed) > 1 else None

        return {
            "date": latest[0],
            "value": latest[1],
            "previousDate": prev[0] if prev else None,
            "previousValue": prev[1] if prev else None,
            "change": latest[1] - prev[1] if prev else None
        }, "Daily"

    except Exception as e:
        print("BOC failed:", e)
        return None

# ---------------- RBA ----------------

def fetch_rba(series_id):
    try:
        url = f"https://api.rba.gov.au/statistics/timeseries/{series_id}?format=json"
        data = fetch_json(url)

        obs = data["series"]["observations"]
        parsed = [(o["date"], float(o["value"])) for o in obs if o["value"]]

        parsed.sort(key=lambda x: x[0])

        latest = parsed[-1]
        prev = parsed[-2] if len(parsed) > 1 else None

        return {
            "date": latest[0],
            "value": latest[1],
            "previousDate": prev[0] if prev else None,
            "previousValue": prev[1] if prev else None,
            "change": latest[1] - prev[1] if prev else None
        }, "Daily"

    except Exception as e:
        print("RBA failed:", e)
        return None

# ---------------- ROUTER ----------------

def fetch_data(info):
    primary = info["primary_source"]

    if primary == "fred":
        return fetch_fred(info["series_id"])

    if primary == "ecb":
        return fetch_ecb()

    if primary == "boe":
        data = fetch_boe()
        if data:
            return data

    if primary == "boc":
        data = fetch_boc(info["series_id"])
        if data:
            return data

    if primary == "rba":
        data = fetch_rba(info["series_id"])
        if data:
            return data

    # FALLBACK → FRED
    if info.get("fallback_series_id"):
        return fetch_fred(info["fallback_series_id"])

    raise RuntimeError("All sources failed")

# ---------------- MAIN ----------------

def main():
    countries = {}
    errors = {}

    for slug, info in SERIES.items():
        try:
            obs, freq = fetch_data(info)

            countries[slug] = {
                "label": info["label"],
                "source": info["primary_source"],
                "frequency": freq,
                "date": obs["date"],
                "value": obs["value"],
                "previousDate": obs["previousDate"],
                "previousValue": obs["previousValue"],
                "change": obs["change"]
            }

            print(f"{info['label']} OK ({freq})")

        except Exception as e:
            errors[slug] = str(e)
            print(f"{info['label']} FAILED:", e)

    output = {
        "meta": {
            "title": "BondStats Global Yields",
            "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%d")
        },
        "countries": countries,
        "errors": errors
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

if __name__ == "__main__":
    main()
