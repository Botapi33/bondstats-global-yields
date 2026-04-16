import json
import os
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import urlopen, Request

API_KEY = os.environ.get("FRED_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing FRED_API_KEY environment variable.")

OUTPUT_FILE = "global_yields.json"

SERIES = {
    "united_states": {
        "label": "United States",
        "series_id": "DGS10",
        "frequency_hint": "Daily"
    },
    "germany": {
        "label": "Germany",
        "series_id": "IRLTLT01DEM156N",
        "frequency_hint": "Monthly"
    },
    "united_kingdom": {
        "label": "United Kingdom",
        "series_id": "IRLTLT01GBM156N",
        "frequency_hint": "Daily",
        "source": "boe"
    },
    "japan": {
        "label": "Japan",
        "series_id": "IRLTLT01JPM156N",
        "frequency_hint": "Monthly"
    },
    "france": {
        "label": "France",
        "series_id": "IRLTLT01FRM156N",
        "frequency_hint": "Monthly"
    },
    "italy": {
        "label": "Italy",
        "series_id": "IRLTLT01ITM156N",
        "frequency_hint": "Monthly"
    },
    "spain": {
        "label": "Spain",
        "series_id": "IRLTLT01ESM156N",
        "frequency_hint": "Monthly"
    },
    "netherlands": {
        "label": "Netherlands",
        "series_id": "IRLTLT01NLM156N",
        "frequency_hint": "Monthly"
    },
    "canada": {
        "label": "Canada",
        "series_id": "IRLTLT01CAM156N",
        "frequency_hint": "Monthly"
    },
    "australia": {
        "label": "Australia",
        "series_id": "IRLTLT01AUM156N",
        "frequency_hint": "Monthly"
    },
    "switzerland": {
        "label": "Switzerland",
        "series_id": "IRLTLT01CHM156N",
        "frequency_hint": "Monthly"
    },
    "sweden": {
        "label": "Sweden",
        "series_id": "IRLTLT01SEM156N",
        "frequency_hint": "Monthly"
    },
    "belgium": {
        "label": "Belgium",
        "series_id": "IRLTLT01BEM156N",
        "frequency_hint": "Monthly"
    },
    "austria": {
        "label": "Austria",
        "series_id": "IRLTLT01ATM156N",
        "frequency_hint": "Monthly"
    },
    "portugal": {
        "label": "Portugal",
        "series_id": "IRLTLT01PTM156N",
        "frequency_hint": "Monthly"
    },
    "finland": {
        "label": "Finland",
        "series_id": "IRLTLT01FIM156N",
        "frequency_hint": "Monthly"
    },
    "ireland": {
        "label": "Ireland",
        "series_id": "IRLTLT01IEM156N",
        "frequency_hint": "Monthly"
    },
    "denmark": {
        "label": "Denmark",
        "series_id": "IRLTLT01DKM156N",
        "frequency_hint": "Monthly"
    },
    "norway": {
        "label": "Norway",
        "series_id": "IRLTLT01NOM156N",
        "frequency_hint": "Monthly"
    },
    "india": {
        "label": "India",
        "series_id": "INDIRLTLT01STM",
        "frequency_hint": "Monthly"
    },
    "south_korea": {
        "label": "South Korea",
        "series_id": "IRLTLT01KRM156N",
        "frequency_hint": "Monthly"
    },
    "new_zealand": {
        "label": "New Zealand",
        "series_id": "IRLTLT01NZM156N",
        "frequency_hint": "Monthly"
    },
    "greece": {
        "label": "Greece",
        "series_id": "IRLTLT01GRM156N",
        "frequency_hint": "Monthly"
    },
    "israel": {
        "label": "Israel",
        "series_id": "IRLTLT01ILM156N",
        "frequency_hint": "Monthly"
    },
    "mexico": {
        "label": "Mexico",
        "series_id": "IRLTLT01MXM156N",
        "frequency_hint": "Monthly"
    },
    "poland": {
        "label": "Poland",
        "series_id": "IRLTLT01PLM156N",
        "frequency_hint": "Monthly"
    },
    "czech_republic": {
        "label": "Czech Republic",
        "series_id": "IRLTLT01CZM156N",
        "frequency_hint": "Monthly"
    },
    "hungary": {
        "label": "Hungary",
        "series_id": "IRLTLT01HUM156N",
        "frequency_hint": "Monthly"
    },
    "slovakia": {
        "label": "Slovakia",
        "series_id": "IRLTLT01SKM156N",
        "frequency_hint": "Monthly"
    },
    "slovenia": {
        "label": "Slovenia",
        "series_id": "IRLTLT01SIM156N",
        "frequency_hint": "Monthly"
    },
    "lithuania": {
        "label": "Lithuania",
        "series_id": "LTUIRLTLT01STM",
        "frequency_hint": "Monthly"
    },
    "chile": {
        "label": "Chile",
        "series_id": "IRLTLT01CLM156N",
        "frequency_hint": "Monthly"
    },
    "south_africa": {
        "label": "South Africa",
        "series_id": "IRLTLT01ZAM156N",
        "frequency_hint": "Monthly"
    }
}

def fetch_latest_fred_observation(series_id: str):
    params = urlencode({
        "series_id": series_id,
        "api_key": API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 12
    })
    url = f"https://api.stlouisfed.org/fred/series/observations?{params}"

    with urlopen(url) as response:
        data = json.loads(response.read().decode("utf-8"))

    observations = data.get("observations", [])
    valid = [o for o in observations if o.get("value") not in (None, ".", "")]

    if not valid:
        raise RuntimeError(f"No valid observations found for {series_id}")

    latest = valid[0]
    previous = valid[1] if len(valid) > 1 else None

    latest_value = float(latest["value"])
    previous_value = float(previous["value"]) if previous else None
    change = latest_value - previous_value if previous_value is not None else None

    return {
        "date": latest["date"],
        "value": latest_value,
        "previousDate": previous["date"] if previous else None,
        "previousValue": previous_value,
        "change": change
    }

def fetch_boe_10y_observation():
    url = "https://www.bankofengland.co.uk/boeapps/database/FromShowColumns.asp?csv.x=yes&Datefrom=01/Jan/2020&Dateto=now&SeriesCodes=IUMAJNB&UsingCodes=Y&VPD=Y"

    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req) as response:
        raw = response.read().decode("utf-8", errors="ignore")

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    data_lines = [line for line in lines if "/" in line and "," in line]

    parsed = []
    for line in data_lines:
        parts = [p.strip().strip('"') for p in line.split(",")]
        if len(parts) >= 2:
            try:
                parsed.append((parts[0], float(parts[1])))
            except:
                continue

    if not parsed:
        raise RuntimeError("No BoE data")

    latest = parsed[-1]
    previous = parsed[-2] if len(parsed) > 1 else None

    return {
        "date": latest[0],
        "value": latest[1],
        "previousDate": previous[0] if previous else None,
        "previousValue": previous[1] if previous else None,
        "change": (latest[1] - previous[1]) if previous else None
    }

def fetch_observation(info):
    source = info.get("source", "fred")

    if source == "fred":
        return fetch_latest_fred_observation(info["series_id"])
    elif source == "boe":
        return fetch_boe_10y_observation()
    else:
        raise RuntimeError(f"Unknown source: {source}")

def main():
    countries = {}
    errors = {}

    for slug, info in SERIES.items():
        try:
            obs = fetch_observation(info)

            countries[slug] = {
                "label": info["label"],
                "seriesId": info["series_id"],
                "source": info.get("source", "fred"),
                "frequency": info["frequency_hint"],
                "date": obs["date"],
                "value": obs["value"],
                "previousDate": obs["previousDate"],
                "previousValue": obs["previousValue"],
                "change": obs["change"]
            }

            print(f"Updated {info['label']}: {obs['value']} ({obs['date']})")

        except Exception as e:
            errors[slug] = str(e)
            print(f"Error updating {info['label']}: {e}")

    output = {
        "meta": {
            "title": "BondStats Global Yields",
            "source": "FRED + BoE",
            "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "note": "Some country series update monthly depending on source frequency."
        },
        "countries": countries,
        "errors": errors
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("global_yields.json updated successfully.")

if __name__ == "__main__":
    main()
