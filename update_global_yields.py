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

# ---------------- SAFE HTTP ----------------

def fetch_json(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_text(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8")

# ---------------- SERIES CONFIG ----------------
# Wichtig:
# - frequency_hint bleibt die gewünschte / bekannte Hauptfrequenz
# - fallback_frequency wird genutzt, wenn auf FRED-Fallback gewechselt wird

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
        "fallback_source": "fred",
        "fallback_series_id": "IRLTLT01GBM156N",
        "fallback_frequency": "Monthly"
    },
    "canada": {
        "label": "Canada",
        "series_id": "V39055",
        "frequency_hint": "Daily",
        "primary_source": "boc",
        "fallback_source": "fred",
        "fallback_series_id": "IRLTLT01CAM156N",
        "fallback_frequency": "Monthly"
    },
    "australia": {
        "label": "Australia",
        "series_id": "F2",
        "frequency_hint": "Daily",
        "primary_source": "rba",
        "fallback_source": "fred",
        "fallback_series_id": "IRLTLT01AUM156N",
        "fallback_frequency": "Monthly"
    },

    # FRED countries
    "germany": {"label": "Germany", "series_id": "IRLTLT01DEM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "france": {"label": "France", "series_id": "IRLTLT01FRM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "italy": {"label": "Italy", "series_id": "IRLTLT01ITM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "spain": {"label": "Spain", "series_id": "IRLTLT01ESM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "netherlands": {"label": "Netherlands", "series_id": "IRLTLT01NLM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "switzerland": {"label": "Switzerland", "series_id": "IRLTLT01CHM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "sweden": {"label": "Sweden", "series_id": "IRLTLT01SEM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "belgium": {"label": "Belgium", "series_id": "IRLTLT01BEM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "austria": {"label": "Austria", "series_id": "IRLTLT01ATM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "portugal": {"label": "Portugal", "series_id": "IRLTLT01PTM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "finland": {"label": "Finland", "series_id": "IRLTLT01FIM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "ireland": {"label": "Ireland", "series_id": "IRLTLT01IEM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "denmark": {"label": "Denmark", "series_id": "IRLTLT01DKM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "norway": {"label": "Norway", "series_id": "IRLTLT01NOM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "india": {"label": "India", "series_id": "INDIRLTLT01STM", "frequency_hint": "Monthly", "primary_source": "fred"},
    "south_korea": {"label": "South Korea", "series_id": "IRLTLT01KRM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "new_zealand": {"label": "New Zealand", "series_id": "IRLTLT01NZM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "greece": {"label": "Greece", "series_id": "IRLTLT01GRM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "israel": {"label": "Israel", "series_id": "IRLTLT01ILM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "mexico": {"label": "Mexico", "series_id": "IRLTLT01MXM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "poland": {"label": "Poland", "series_id": "IRLTLT01PLM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "czech_republic": {"label": "Czech Republic", "series_id": "IRLTLT01CZM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "hungary": {"label": "Hungary", "series_id": "IRLTLT01HUM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "slovakia": {"label": "Slovakia", "series_id": "IRLTLT01SKM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "slovenia": {"label": "Slovenia", "series_id": "IRLTLT01SIM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "lithuania": {"label": "Lithuania", "series_id": "LTUIRLTLT01STM", "frequency_hint": "Monthly", "primary_source": "fred"},
    "chile": {"label": "Chile", "series_id": "IRLTLT01CLM156N", "frequency_hint": "Monthly", "primary_source": "fred"},
    "south_africa": {"label": "South Africa", "series_id": "IRLTLT01ZAM156N", "frequency_hint": "Monthly", "primary_source": "fred"}
}

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
    data = fetch_json(url)

    observations = data.get("observations", [])
    obs = [o for o in observations if o.get("value") not in (None, ".", "")]

    if not obs:
        raise RuntimeError(f"No valid FRED observations for {series_id}")

    latest = obs[0]
    prev = obs[1] if len(obs) > 1 else None

    latest_value = float(latest["value"])
    prev_value = float(prev["value"]) if prev else None

    return {
        "date": latest["date"],
        "value": latest_value,
        "previousDate": prev["date"] if prev else None,
        "previousValue": prev_value,
        "change": (latest_value - prev_value) if prev_value is not None else None
    }

# ---------------- ECB ----------------

def fetch_ecb():
    url = "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?format=jsondata"
    data = fetch_json(url)

    series_map = data["dataSets"][0]["series"]
    if not series_map:
        raise RuntimeError("ECB series map empty")

    series = next(iter(series_map.values()))
    obs = series["observations"]
    keys = sorted(obs.keys(), key=lambda x: int(x))

    if len(keys) < 2:
        raise RuntimeError("ECB returned fewer than 2 observations")

    latest_key = keys[-1]
    prev_key = keys[-2]
    time_index = data["structure"]["dimensions"]["observation"][0]["values"]

    latest_value = float(obs[latest_key][0])
    prev_value = float(obs[prev_key][0])

    return {
        "date": time_index[int(latest_key)]["id"],
        "value": latest_value,
        "previousDate": time_index[int(prev_key)]["id"],
        "previousValue": prev_value,
        "change": latest_value - prev_value
    }

# ---------------- BOE ----------------

def fetch_boe():
    try:
        url = (
            "https://api.allorigins.win/raw?url="
            "https://www.bankofengland.co.uk/boeapps/database/FromShowColumns.asp?csv.x=yes&SeriesCodes=IUMAJNB"
        )
        raw = fetch_text(url)

        lines = [line.strip() for line in raw.splitlines() if "/" in line]
        parsed = []

        for line in lines:
            parts = line.split(",")
            if len(parts) < 2:
                continue
            try:
                parsed.append((parts[0].strip(), float(parts[1].strip())))
            except:
                continue

        if len(parsed) < 2:
            return None

        parsed.sort(key=lambda x: datetime.strptime(x[0], "%d/%m/%Y"))

        latest = parsed[-1]
        prev = parsed[-2]

        return {
            "date": latest[0],
            "value": latest[1],
            "previousDate": prev[0],
            "previousValue": prev[1],
            "change": latest[1] - prev[1]
        }
    except Exception as e:
        print(f"BOE failed: {e}")
        return None

# ---------------- BOC ----------------

def fetch_boc(series_id):
    try:
        url = f"https://www.bankofcanada.ca/valet/observations?seriesName={series_id}&recent=2"
        data = fetch_json(url)

        observations = data.get("observations", [])
        parsed = []

        for o in observations:
            date = o.get("d")
            series_obj = o.get(series_id)

            if not date or not isinstance(series_obj, dict):
                continue

            val = series_obj.get("v")
            if val in (None, "", "null"):
                continue

            parsed.append((date, float(val)))

        if not parsed:
            return None

        parsed.sort(key=lambda x: x[0])

        latest = parsed[-1]
        prev = parsed[-2] if len(parsed) > 1 else None

        return {
            "date": latest[0],
            "value": latest[1],
            "previousDate": prev[0] if prev else None,
            "previousValue": prev[1] if prev else None,
            "change": (latest[1] - prev[1]) if prev else None
        }
    except Exception as e:
        print(f"BOC failed: {e}")
        return None

# ---------------- RBA ----------------

def fetch_rba(series_id):
    try:
        url = f"https://api.rba.gov.au/statistics/timeseries/{series_id}?format=json"
        data = fetch_json(url)

        series = data.get("series", {})
        observations = series.get("observations", [])
        parsed = []

        for o in observations:
            date = o.get("date")
            value = o.get("value")
            if date and value not in (None, ""):
                parsed.append((date, float(value)))

        if not parsed:
            return None

        parsed.sort(key=lambda x: x[0])

        latest = parsed[-1]
        prev = parsed[-2] if len(parsed) > 1 else None

        return {
            "date": latest[0],
            "value": latest[1],
            "previousDate": prev[0] if prev else None,
            "previousValue": prev[1] if prev else None,
            "change": (latest[1] - prev[1]) if prev else None
        }
    except Exception as e:
        print(f"RBA failed: {e}")
        return None

# ---------------- ROUTER ----------------

def fetch_data(info):
    primary = info.get("primary_source", "fred")

    # Primary sources
    if primary == "fred":
        obs = fetch_fred(info["series_id"])
        return obs, "fred", info.get("frequency_hint", "Monthly")

    if primary == "ecb":
        obs = fetch_ecb()
        return obs, "ecb", "Daily"

    if primary == "boe":
        obs = fetch_boe()
        if obs:
            return obs, "boe", "Daily"

    if primary == "boc":
        obs = fetch_boc(info["series_id"])
        if obs:
            return obs, "boc", "Daily"

    if primary == "rba":
        obs = fetch_rba(info["series_id"])
        if obs:
            return obs, "rba", "Daily"

    # Fallback
    fallback_source = info.get("fallback_source")
    fallback_series_id = info.get("fallback_series_id")

    if fallback_source == "fred" and fallback_series_id:
        obs = fetch_fred(fallback_series_id)
        return obs, "fred", info.get("fallback_frequency", "Monthly")

    raise RuntimeError("All sources failed")

# ---------------- MAIN ----------------

def main():
    countries = {}
    errors = {}

    for slug, info in SERIES.items():
        try:
            obs, source, frequency = fetch_data(info)

            countries[slug] = {
                "label": info["label"],
                "seriesId": info.get("series_id"),
                "source": source,
                "frequency": frequency,
                "date": obs["date"],
                "value": obs["value"],
                "previousDate": obs["previousDate"],
                "previousValue": obs["previousValue"],
                "change": obs["change"]
            }

            print(f"{info['label']} updated via {source} ({frequency})")

        except Exception as e:
            errors[slug] = str(e)
            print(f"Error: {info['label']} → {e}")

    output = {
        "meta": {
            "title": "BondStats Global Yields",
            "source": "FRED + ECB + BoE + BoC + RBA",
            "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%d")
        },
        "countries": countries,
        "errors": errors
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

if __name__ == "__main__":
    main()
