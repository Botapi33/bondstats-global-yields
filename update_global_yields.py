import json
import os
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import urlopen, Request

API_KEY = os.environ.get("FRED_API_KEY")
OUTPUT_FILE = "global_yields.json"
TIMEOUT = 10

# ---------------- SAFE FETCH ----------------

def fetch_json(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))

# ---------------- SERIES CONFIG ----------------

SERIES = {
    "united_states": {"label": "United States","series_id": "DGS10","primary_source": "fred"},
    "euro_area": {"label": "Euro Area","primary_source": "ecb"},
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
    },

    # ALL FRED COUNTRIES BACK
    "germany": {"label": "Germany","series_id": "IRLTLT01DEM156N"},
    "france": {"label": "France","series_id": "IRLTLT01FRM156N"},
    "italy": {"label": "Italy","series_id": "IRLTLT01ITM156N"},
    "spain": {"label": "Spain","series_id": "IRLTLT01ESM156N"},
    "netherlands": {"label": "Netherlands","series_id": "IRLTLT01NLM156N"},
    "switzerland": {"label": "Switzerland","series_id": "IRLTLT01CHM156N"},
    "sweden": {"label": "Sweden","series_id": "IRLTLT01SEM156N"},
    "belgium": {"label": "Belgium","series_id": "IRLTLT01BEM156N"},
    "austria": {"label": "Austria","series_id": "IRLTLT01ATM156N"},
    "portugal": {"label": "Portugal","series_id": "IRLTLT01PTM156N"},
    "finland": {"label": "Finland","series_id": "IRLTLT01FIM156N"},
    "ireland": {"label": "Ireland","series_id": "IRLTLT01IEM156N"},
    "denmark": {"label": "Denmark","series_id": "IRLTLT01DKM156N"},
    "norway": {"label": "Norway","series_id": "IRLTLT01NOM156N"},
    "india": {"label": "India","series_id": "INDIRLTLT01STM"},
    "south_korea": {"label": "South Korea","series_id": "IRLTLT01KRM156N"},
    "new_zealand": {"label": "New Zealand","series_id": "IRLTLT01NZM156N"},
    "greece": {"label": "Greece","series_id": "IRLTLT01GRM156N"},
    "israel": {"label": "Israel","series_id": "IRLTLT01ILM156N"},
    "mexico": {"label": "Mexico","series_id": "IRLTLT01MXM156N"},
    "poland": {"label": "Poland","series_id": "IRLTLT01PLM156N"},
    "czech_republic": {"label": "Czech Republic","series_id": "IRLTLT01CZM156N"},
    "hungary": {"label": "Hungary","series_id": "IRLTLT01HUM156N"},
    "slovakia": {"label": "Slovakia","series_id": "IRLTLT01SKM156N"},
    "slovenia": {"label": "Slovenia","series_id": "IRLTLT01SIM156N"},
    "lithuania": {"label": "Lithuania","series_id": "LTUIRLTLT01STM"},
    "chile": {"label": "Chile","series_id": "IRLTLT01CLM156N"},
    "south_africa": {"label": "South Africa","series_id": "IRLTLT01ZAM156N"}
}

# ---------------- FETCHERS ----------------

def fetch_fred(series_id):
    url = f"https://api.stlouisfed.org/fred/series/observations?{urlencode({'series_id':series_id,'api_key':API_KEY,'file_type':'json','sort_order':'desc','limit':12})}"
    data = fetch_json(url)

    obs = [o for o in data["observations"] if o["value"] not in (".","")]
    latest = obs[0]
    prev = obs[1] if len(obs) > 1 else None

    return {
        "date": latest["date"],
        "value": float(latest["value"]),
        "previousDate": prev["date"] if prev else None,
        "previousValue": float(prev["value"]) if prev else None,
        "change": float(latest["value"]) - float(prev["value"]) if prev else None
    }, "Monthly"

def fetch_ecb():
    url = "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?format=jsondata"
    data = fetch_json(url)

    series = next(iter(data["dataSets"][0]["series"].values()))
    obs = series["observations"]
    keys = sorted(obs.keys(), key=lambda x: int(x))

    time_index = data["structure"]["dimensions"]["observation"][0]["values"]

    return {
        "date": time_index[int(keys[-1])]["id"],
        "value": float(obs[keys[-1]][0]),
        "previousDate": time_index[int(keys[-2])]["id"],
        "previousValue": float(obs[keys[-2]][0]),
        "change": float(obs[keys[-1]][0]) - float(obs[keys[-2]][0])
    }, "Daily"

def fetch_boe():
    try:
        url = "https://api.allorigins.win/raw?url=https://www.bankofengland.co.uk/boeapps/database/FromShowColumns.asp?csv.x=yes&SeriesCodes=IUMAJNB"
        raw = urlopen(Request(url), timeout=TIMEOUT).read().decode("utf-8")

        lines = [l for l in raw.splitlines() if "/" in l]
        parsed = [(l.split(",")[0], float(l.split(",")[1])) for l in lines if "," in l]

        parsed.sort(key=lambda x: datetime.strptime(x[0], "%d/%m/%Y"))

        return {
            "date": parsed[-1][0],
            "value": parsed[-1][1],
            "previousDate": parsed[-2][0],
            "previousValue": parsed[-2][1],
            "change": parsed[-1][1] - parsed[-2][1]
        }, "Daily"

    except:
        return None

def fetch_boc(series_id):
    try:
        data = fetch_json(f"https://www.bankofcanada.ca/valet/observations?seriesName={series_id}&recent=2")
        obs = data["observations"]

        parsed = [(o["d"], float(o[series_id]["v"])) for o in obs if o.get(series_id)]
        parsed.sort()

        return {
            "date": parsed[-1][0],
            "value": parsed[-1][1],
            "previousDate": parsed[-2][0],
            "previousValue": parsed[-2][1],
            "change": parsed[-1][1] - parsed[-2][1]
        }, "Daily"

    except:
        return None

def fetch_rba(series_id):
    try:
        data = fetch_json(f"https://api.rba.gov.au/statistics/timeseries/{series_id}?format=json")
        obs = data["series"]["observations"]

        parsed = [(o["date"], float(o["value"])) for o in obs if o["value"]]
        parsed.sort()

        return {
            "date": parsed[-1][0],
            "value": parsed[-1][1],
            "previousDate": parsed[-2][0],
            "previousValue": parsed[-2][1],
            "change": parsed[-1][1] - parsed[-2][1]
        }, "Daily"

    except:
        return None

# ---------------- ROUTER ----------------

def fetch_data(info):
    try:
        if info.get("primary_source") == "ecb":
            return fetch_ecb()

        if info.get("primary_source") == "boe":
            r = fetch_boe()
            if r: return r

        if info.get("primary_source") == "boc":
            r = fetch_boc(info["series_id"])
            if r: return r

        if info.get("primary_source") == "rba":
            r = fetch_rba(info["series_id"])
            if r: return r

        if info.get("series_id"):
            return fetch_fred(info["series_id"])

    except:
        pass

    # fallback always FRED
    if info.get("fallback_series_id"):
        return fetch_fred(info["fallback_series_id"])

    raise RuntimeError("fail")

# ---------------- MAIN ----------------

def main():
    countries = {}
    errors = {}

    for k, v in SERIES.items():
        try:
            obs, freq = fetch_data(v)

            countries[k] = {
                "label": v["label"],
                "source": v.get("primary_source","fred"),
                "frequency": freq,
                "date": obs["date"],
                "value": obs["value"],
                "previousDate": obs["previousDate"],
                "previousValue": obs["previousValue"],
                "change": obs["change"]
            }

        except Exception as e:
            errors[k] = str(e)

    json.dump({
        "meta":{
            "title":"BondStats Global Yields",
            "lastUpdated":datetime.now(timezone.utc).strftime("%Y-%m-%d")
        },
        "countries":countries,
        "errors":errors
    }, open(OUTPUT_FILE,"w"), indent=2)

if __name__ == "__main__":
    main()
