import json
import os
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import urlopen, Request

API_KEY = os.environ.get("FRED_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing FRED_API_KEY environment variable.")

OUTPUT_FILE = "global_yields.json"

# ---------------- SERIES CONFIG ----------------

SERIES = {
    "united_states": {
        "label": "United States",
        "series_id": "DGS10",
        "frequency_hint": "Daily",
        "primary_source": "fred"
    },
    "euro_area": {
        "label": "Euro Area",
        "series_id": None,
        "frequency_hint": "Daily",
        "primary_source": "ecb"
    },
    "united_kingdom": {
        "label": "United Kingdom",
        "series_id": "IRLTLT01GBM156N",
        "frequency_hint": "Daily",
        "primary_source": "boe",
        "fallback_source": "fred"
    },

    # FRED Countries (unchanged)
    "germany": {"label": "Germany", "series_id": "IRLTLT01DEM156N", "frequency_hint": "Monthly"},
    "france": {"label": "France", "series_id": "IRLTLT01FRM156N", "frequency_hint": "Monthly"},
    "italy": {"label": "Italy", "series_id": "IRLTLT01ITM156N", "frequency_hint": "Monthly"},
    "spain": {"label": "Spain", "series_id": "IRLTLT01ESM156N", "frequency_hint": "Monthly"},
    "netherlands": {"label": "Netherlands", "series_id": "IRLTLT01NLM156N", "frequency_hint": "Monthly"},
    "canada": {"label": "Canada", "series_id": "IRLTLT01CAM156N", "frequency_hint": "Monthly"},
    "australia": {"label": "Australia", "series_id": "IRLTLT01AUM156N", "frequency_hint": "Monthly"},
    "switzerland": {"label": "Switzerland", "series_id": "IRLTLT01CHM156N", "frequency_hint": "Monthly"},
    "sweden": {"label": "Sweden", "series_id": "IRLTLT01SEM156N", "frequency_hint": "Monthly"},
    "belgium": {"label": "Belgium", "series_id": "IRLTLT01BEM156N", "frequency_hint": "Monthly"},
    "austria": {"label": "Austria", "series_id": "IRLTLT01ATM156N", "frequency_hint": "Monthly"},
    "portugal": {"label": "Portugal", "series_id": "IRLTLT01PTM156N", "frequency_hint": "Monthly"},
    "finland": {"label": "Finland", "series_id": "IRLTLT01FIM156N", "frequency_hint": "Monthly"},
    "ireland": {"label": "Ireland", "series_id": "IRLTLT01IEM156N", "frequency_hint": "Monthly"},
    "denmark": {"label": "Denmark", "series_id": "IRLTLT01DKM156N", "frequency_hint": "Monthly"},
    "norway": {"label": "Norway", "series_id": "IRLTLT01NOM156N", "frequency_hint": "Monthly"},
    "india": {"label": "India", "series_id": "INDIRLTLT01STM", "frequency_hint": "Monthly"},
    "south_korea": {"label": "South Korea", "series_id": "IRLTLT01KRM156N", "frequency_hint": "Monthly"},
    "new_zealand": {"label": "New Zealand", "series_id": "IRLTLT01NZM156N", "frequency_hint": "Monthly"},
    "greece": {"label": "Greece", "series_id": "IRLTLT01GRM156N", "frequency_hint": "Monthly"},
    "israel": {"label": "Israel", "series_id": "IRLTLT01ILM156N", "frequency_hint": "Monthly"},
    "mexico": {"label": "Mexico", "series_id": "IRLTLT01MXM156N", "frequency_hint": "Monthly"},
    "poland": {"label": "Poland", "series_id": "IRLTLT01PLM156N", "frequency_hint": "Monthly"},
    "czech_republic": {"label": "Czech Republic", "series_id": "IRLTLT01CZM156N", "frequency_hint": "Monthly"},
    "hungary": {"label": "Hungary", "series_id": "IRLTLT01HUM156N", "frequency_hint": "Monthly"},
    "slovakia": {"label": "Slovakia", "series_id": "IRLTLT01SKM156N", "frequency_hint": "Monthly"},
    "slovenia": {"label": "Slovenia", "series_id": "IRLTLT01SIM156N", "frequency_hint": "Monthly"},
    "lithuania": {"label": "Lithuania", "series_id": "LTUIRLTLT01STM", "frequency_hint": "Monthly"},
    "chile": {"label": "Chile", "series_id": "IRLTLT01CLM156N", "frequency_hint": "Monthly"},
    "south_africa": {"label": "South Africa", "series_id": "IRLTLT01ZAM156N", "frequency_hint": "Monthly"}
}

# ---------------- UTIL ----------------

def safe_float(val):
    try:
        return float(val)
    except:
        return None

# ---------------- FRED ----------------

def fetch_fred(series_id):
    params = urlencode({
        "series_id": series_id,
        "api_key": API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 12
    })

    url = f"https://api.stlouisfed.org/fred/series/observations?{params}"

    with urlopen(url) as r:
        data = json.loads(r.read().decode("utf-8"))

    obs = [o for o in data["observations"] if o["value"] not in (None, ".", "")]
    latest = obs[0]
    prev = obs[1] if len(obs) > 1 else None

    return {
        "date": latest["date"],
        "value": safe_float(latest["value"]),
        "previousDate": prev["date"] if prev else None,
        "previousValue": safe_float(prev["value"]) if prev else None,
        "change": safe_float(latest["value"]) - safe_float(prev["value"]) if prev else None
    }

# ---------------- ECB FIX ----------------

def fetch_ecb():
    url = "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?format=jsondata"

    data = json.loads(urlopen(Request(url)).read().decode("utf-8"))

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
    }

# ---------------- BOE FIX ----------------

def fetch_boe():
    try:
        url = "https://api.allorigins.win/raw?url=https://www.bankofengland.co.uk/boeapps/database/FromShowColumns.asp?csv.x=yes&SeriesCodes=IUMAJNB"
        raw = urlopen(url).read().decode("utf-8")

        lines = [l for l in raw.splitlines() if "/" in l]
        parsed = []

        for l in lines:
            p = l.split(",")
            try:
                parsed.append((p[0], float(p[1])))
            except:
                continue

        latest = parsed[-1]
        prev = parsed[-2]

        return {
            "date": latest[0],
            "value": latest[1],
            "previousDate": prev[0],
            "previousValue": prev[1],
            "change": latest[1] - prev[1]
        }

    except:
        return None

# ---------------- FETCH ROUTER ----------------

def fetch_data(info):
    primary = info.get("primary_source", "fred")

    try:
        if primary == "boe":
            data = fetch_boe()
            if data:
                return data, "boe"

        if primary == "ecb":
            data = fetch_ecb()
            if data:
                return data, "ecb"

        if info.get("series_id"):
            return fetch_fred(info["series_id"]), "fred"

    except:
        pass

    raise RuntimeError("All sources failed")

# ---------------- MAIN ----------------

def main():
    countries = {}
    errors = {}

    for slug, info in SERIES.items():
        try:
            obs, source = fetch_data(info)

            countries[slug] = {
                "label": info["label"],
                "seriesId": info.get("series_id"),
                "source": source,
                "frequency": info["frequency_hint"],
                "date": obs["date"],
                "value": obs["value"],
                "previousDate": obs["previousDate"],
                "previousValue": obs["previousValue"],
                "change": obs["change"]
            }

            print(f"{info['label']} updated via {source}")

        except Exception as e:
            errors[slug] = str(e)
            print(f"Error: {info['label']} → {e}")

    output = {
        "meta": {
            "title": "BondStats Global Yields",
            "source": "FRED + ECB + BoE",
            "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%d")
        },
        "countries": countries,
        "errors": errors
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

if __name__ == "__main__":
    main()
