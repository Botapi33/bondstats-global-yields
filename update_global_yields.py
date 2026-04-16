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
        "frequency_hint": "Daily",
        "primary_source": "fred"
    },
    "euro_area": {
        "label": "Euro Area",
        "series_id": None,
        "frequency_hint": "Daily",
        "primary_source": "ecb"
    },
    "germany": {
        "label": "Germany",
        "series_id": "IRLTLT01DEM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "united_kingdom": {
    "label": "United Kingdom",
    "series_id": "IRLTLT01GBM156N",
    "frequency_hint": "Daily",
    "fallback_frequency_hint": "Monthly",
    "primary_source": "boe",
    "fallback_source": "fred"
},
    },
    "japan": {
        "label": "Japan",
        "series_id": "IRLTLT01JPM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "france": {
        "label": "France",
        "series_id": "IRLTLT01FRM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "italy": {
        "label": "Italy",
        "series_id": "IRLTLT01ITM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "spain": {
        "label": "Spain",
        "series_id": "IRLTLT01ESM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "netherlands": {
        "label": "Netherlands",
        "series_id": "IRLTLT01NLM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "canada": {
        "label": "Canada",
        "series_id": "IRLTLT01CAM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "australia": {
        "label": "Australia",
        "series_id": "IRLTLT01AUM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "switzerland": {
        "label": "Switzerland",
        "series_id": "IRLTLT01CHM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "sweden": {
        "label": "Sweden",
        "series_id": "IRLTLT01SEM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "belgium": {
        "label": "Belgium",
        "series_id": "IRLTLT01BEM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "austria": {
        "label": "Austria",
        "series_id": "IRLTLT01ATM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "portugal": {
        "label": "Portugal",
        "series_id": "IRLTLT01PTM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "finland": {
        "label": "Finland",
        "series_id": "IRLTLT01FIM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "ireland": {
        "label": "Ireland",
        "series_id": "IRLTLT01IEM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "denmark": {
        "label": "Denmark",
        "series_id": "IRLTLT01DKM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "norway": {
        "label": "Norway",
        "series_id": "IRLTLT01NOM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "india": {
        "label": "India",
        "series_id": "INDIRLTLT01STM",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "south_korea": {
        "label": "South Korea",
        "series_id": "IRLTLT01KRM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "new_zealand": {
        "label": "New Zealand",
        "series_id": "IRLTLT01NZM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "greece": {
        "label": "Greece",
        "series_id": "IRLTLT01GRM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "israel": {
        "label": "Israel",
        "series_id": "IRLTLT01ILM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "mexico": {
        "label": "Mexico",
        "series_id": "IRLTLT01MXM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "poland": {
        "label": "Poland",
        "series_id": "IRLTLT01PLM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "czech_republic": {
        "label": "Czech Republic",
        "series_id": "IRLTLT01CZM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "hungary": {
        "label": "Hungary",
        "series_id": "IRLTLT01HUM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "slovakia": {
        "label": "Slovakia",
        "series_id": "IRLTLT01SKM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "slovenia": {
        "label": "Slovenia",
        "series_id": "IRLTLT01SIM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "lithuania": {
        "label": "Lithuania",
        "series_id": "LTUIRLTLT01STM",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "chile": {
        "label": "Chile",
        "series_id": "IRLTLT01CLM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    },
    "south_africa": {
        "label": "South Africa",
        "series_id": "IRLTLT01ZAM156N",
        "frequency_hint": "Monthly",
        "primary_source": "fred"
    }
}


def safe_float(value):
    if value in (None, "", ".", "NA", "N/A"):
        return None
    try:
        return float(value)
    except Exception:
        return None


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
        raise RuntimeError(f"No valid FRED observations found for {series_id}")

    latest = valid[0]
    previous = valid[1] if len(valid) > 1 else None

    latest_value = safe_float(latest["value"])
    previous_value = safe_float(previous["value"]) if previous else None
    change = latest_value - previous_value if previous_value is not None else None

    return {
        "date": latest["date"],
        "value": latest_value,
        "previousDate": previous["date"] if previous else None,
        "previousValue": previous_value,
        "change": change
    }


def fetch_boe_10y_observation():
    url = (
        "https://www.bankofengland.co.uk/boeapps/database/"
        "FromShowColumns.asp?csv.x=yes&Datefrom=01/Jan/2024&Dateto=now"
        "&SeriesCodes=IUMAJNB&UsingCodes=Y&VPD=Y"
    )

    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req) as response:
        raw = response.read().decode("utf-8", errors="ignore")

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    parsed = []

    for line in lines:
        parts = [p.strip().strip('"') for p in line.split(",")]
        if len(parts) < 2:
            continue

        date_str = parts[0]
        value_str = parts[1]

        if not any(ch.isdigit() for ch in date_str):
            continue

        value = safe_float(value_str)
        if value is None:
            continue

        parsed.append((date_str, value))

    if not parsed:
        raise RuntimeError("No valid BoE observations found")

    latest = parsed[-1]
    previous = parsed[-2] if len(parsed) > 1 else None

    return {
        "date": latest[0],
        "value": latest[1],
        "previousDate": previous[0] if previous else None,
        "previousValue": previous[1] if previous else None,
        "change": (latest[1] - previous[1]) if previous else None
    }


def fetch_ecb_euro_area_10y_observation():
    url = (
        "https://data-api.ecb.europa.eu/service/data/"
        "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?format=jsondata"
    )

    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req) as response:
        data = json.loads(response.read().decode("utf-8"))

    data_sets = data.get("dataSets", [])
    if not data_sets:
        raise RuntimeError("No ECB dataSets found")

    series_map = data_sets[0].get("series", {})
    if not series_map:
        raise RuntimeError("No ECB series found")

    first_series = next(iter(series_map.values()))
    observations = first_series.get("observations", {})
    if not observations:
        raise RuntimeError("No ECB observations found")

    keys = sorted(observations.keys(), key=lambda x: int(x))
    latest_key = keys[-1]
    previous_key = keys[-2] if len(keys) > 1 else None

    latest_value = safe_float(observations[latest_key][0])
    previous_value = safe_float(observations[previous_key][0]) if previous_key else None
    change = latest_value - previous_value if previous_value is not None else None

    observation_dimension = data["structure"]["dimensions"]["observation"][0]["values"]
    latest_date = observation_dimension[int(latest_key)]["id"]
    previous_date = observation_dimension[int(previous_key)]["id"] if previous_key else None

    return {
        "date": latest_date,
        "value": latest_value,
        "previousDate": previous_date,
        "previousValue": previous_value,
        "change": change
    }


def fetch_observation(info: dict):
    primary_source = info.get("primary_source", "fred")
    fallback_source = info.get("fallback_source")

    try:
        if primary_source == "fred":
            obs = fetch_latest_fred_observation(info["series_id"])
            return obs, "fred"

        if primary_source == "boe":
            obs = fetch_boe_10y_observation()
            return obs, "boe"

        if primary_source == "ecb":
            obs = fetch_ecb_euro_area_10y_observation()
            return obs, "ecb"

        raise RuntimeError(f"Unknown primary source: {primary_source}")

    except Exception as primary_error:
        if fallback_source == "fred" and info.get("series_id"):
            try:
                obs = fetch_latest_fred_observation(info["series_id"])
                return obs, "fred"
            except Exception as fallback_error:
                raise RuntimeError(
                    f"Primary failed ({primary_source}): {primary_error}; "
                    f"Fallback failed ({fallback_source}): {fallback_error}"
                )

        raise RuntimeError(f"Primary failed ({primary_source}): {primary_error}")


def main():
    countries = {}
    errors = {}

    for slug, info in SERIES.items():
        try:
obs, source_used = fetch_data(info)

            used_frequency = info["frequency_hint"]
            if source_used == "fred" and info.get("primary_source") != "fred":
                used_frequency = info.get("fallback_frequency_hint", "Monthly")

            countries[slug] = {
                "label": info["label"],
                "seriesId": info["series_id"],
                "source": source_used,
                "frequency": used_frequency,
                "date": obs["date"],
                "value": obs["value"],
                "previousDate": obs["previousDate"],
                "previousValue": obs["previousValue"],
                "change": obs["change"]
            }

            print(
                f"Updated {info['label']}: "
                f"{obs['value']} ({obs['date']}) via {source_used}"
            )

        except Exception as e:
            errors[slug] = str(e)
            print(f"Error updating {info['label']}: {e}")

    output = {
        "meta": {
            "title": "BondStats Global Yields",
            "source": "Mixed (FRED + BoE + ECB)",
            "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "note": "Some country series update monthly depending on source frequency. UK uses BoE with FRED fallback. Euro Area uses ECB."
        },
        "countries": countries,
        "errors": errors
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("global_yields.json updated successfully.")
    print(f"Countries updated: {len(countries)}")
    if errors:
        print(f"Countries with errors: {len(errors)}")


if __name__ == "__main__":
    main()
