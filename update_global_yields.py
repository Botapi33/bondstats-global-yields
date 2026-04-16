import json
import os
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.parse import urlencode

API_KEY = os.environ.get("FRED_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing FRED_API_KEY")

OUTPUT_FILE = "global_yields.json"

# ================= ECB COUNTRIES =================

ECB_COUNTRIES = {
    "euro_area": "U2",
    "germany": "DE",
    "france": "FR",
    "italy": "IT",
    "spain": "ES",
    "netherlands": "NL",
    "belgium": "BE",
    "austria": "AT"
}

# ================= FRED FALLBACK =================

FRED_SERIES = {
    "united_states": "DGS10",
    "united_kingdom": "IRLTLT01GBM156N",
    "canada": "IRLTLT01CAM156N",
    "japan": "IRLTLT01JPM156N",
    "australia": "IRLTLT01AUM156N"
}

# ================= HELPERS =================

def safe_float(x):
    try:
        return float(x)
    except:
        return None

# ================= ECB FETCH =================

def fetch_ecb(country, maturity):
    try:
        url = f"https://data-api.ecb.europa.eu/service/data/YC/B.{country}.EUR.4F.G_N_A.SV_C_YM.SR_{maturity}?format=jsondata"
        data = json.loads(urlopen(Request(url)).read().decode())

        series = next(iter(data["dataSets"][0]["series"].values()))
        obs = series["observations"]
        keys = sorted(obs.keys(), key=lambda x: int(x))

        latest = keys[-1]
        prev = keys[-2]

        time = data["structure"]["dimensions"]["observation"][0]["values"]

        return {
            "date": time[int(latest)]["id"],
            "value": float(obs[latest][0]),
            "prev": float(obs[prev][0])
        }
    except:
        return None

# ================= FRED FETCH =================

def fetch_fred(series_id):
    params = urlencode({
        "series_id": series_id,
        "api_key": API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 12
    })

    url = f"https://api.stlouisfed.org/fred/series/observations?{params}"

    data = json.loads(urlopen(url).read().decode())

    obs = [o for o in data["observations"] if o["value"] not in (".", None)]
    latest = obs[0]
    prev = obs[1] if len(obs) > 1 else None

    return {
        "date": latest["date"],
        "value": safe_float(latest["value"]),
        "prev": safe_float(prev["value"]) if prev else None
    }

# ================= BOE FETCH =================

def fetch_boe():
    try:
        url = "https://api.allorigins.win/raw?url=https://www.bankofengland.co.uk/boeapps/database/FromShowColumns.asp?csv.x=yes&SeriesCodes=IUMAJNB"
        raw = urlopen(url).read().decode()

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
            "prev": prev[1]
        }
    except:
        return None

# ================= MAIN =================

def main():
    countries = {}
    errors = {}

    # ===== ECB DATA (EU DAILY) =====
    for slug, code in ECB_COUNTRIES.items():
        try:
            y10 = fetch_ecb(code, "10Y")
            y2 = fetch_ecb(code, "2Y")

            if not y10 or not y2:
                raise RuntimeError("ECB failed")

            spread = y10["value"] - y2["value"]

            countries[slug] = {
                "label": slug.replace("_", " ").title(),
                "source": "ecb",
                "date": y10["date"],
                "yields": {
                    "10Y": y10["value"],
                    "2Y": y2["value"],
                    "spread": spread
                },
                "change": y10["value"] - y10["prev"]
            }

        except Exception as e:
            errors[slug] = str(e)

    # ===== UK (BOE PRIMARY) =====
    try:
        uk = fetch_boe()

        if uk:
            countries["united_kingdom"] = {
                "label": "United Kingdom",
                "source": "boe",
                "date": uk["date"],
                "yields": {
                    "10Y": uk["value"]
                },
                "change": uk["value"] - uk["prev"]
            }
        else:
            raise RuntimeError("BoE failed")

    except:
        try:
            fred = fetch_fred(FRED_SERIES["united_kingdom"])
            countries["united_kingdom"] = {
                "label": "United Kingdom",
                "source": "fred",
                "date": fred["date"],
                "yields": {
                    "10Y": fred["value"]
                },
                "change": fred["value"] - fred["prev"]
            }
        except Exception as e:
            errors["united_kingdom"] = str(e)

    # ===== FRED OTHER COUNTRIES =====
    for slug, series in FRED_SERIES.items():
        if slug == "united_kingdom":
            continue

        try:
            f = fetch_fred(series)

            countries[slug] = {
                "label": slug.replace("_", " ").title(),
                "source": "fred",
                "date": f["date"],
                "yields": {
                    "10Y": f["value"]
                },
                "change": f["value"] - f["prev"]
            }

        except Exception as e:
            errors[slug] = str(e)

    # ===== OUTPUT =====

    output = {
        "meta": {
            "title": "BondStats Global Yield Engine",
            "sources": ["ECB", "BoE", "FRED"],
            "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%d")
        },
        "countries": countries,
        "errors": errors
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print("JSON updated successfully")

if __name__ == "__main__":
    main()
