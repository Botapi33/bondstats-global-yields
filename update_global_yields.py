import json
import os
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import urlopen, Request

API_KEY = os.environ.get("FRED_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing FRED_API_KEY")

OUTPUT_FILE = "global_yields.json"
TIMEOUT = 10
FRESHNESS_MAX_DAYS = 5

# ---------------- HTTP ----------------

def fetch_json(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_text(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8")

# ---------------- UTILS ----------------

def parse_date(date_str):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    return None

def staleness_days(date_str):
    d = parse_date(date_str)
    if not d:
        return 9999
    return (datetime.now(timezone.utc).replace(tzinfo=None) - d).days

def is_fresh(date_str):
    return staleness_days(date_str) <= FRESHNESS_MAX_DAYS

def calc_tier(days, freq):
    if freq == "Monthly":
        return "monthly"
    if days <= 1:
        return "daily"
    if days <= 7:
        return "delayed"
    return "monthly"

def r(v):
    return round(v, 4) if v is not None else None

# ---------------- SERIES ----------------

SERIES = {
    "united_states": {"label":"United States","series_id":"DGS10","primary_source":"fred","frequency_hint":"Daily"},
    "germany":{"label":"Germany","series_id":"IRLTLT01DEM156N","primary_source":"fred"},
    "france":{"label":"France","series_id":"IRLTLT01FRM156N","primary_source":"fred"},
    "italy":{"label":"Italy","series_id":"IRLTLT01ITM156N","primary_source":"fred"},
    "spain":{"label":"Spain","series_id":"IRLTLT01ESM156N","primary_source":"fred"},
    "netherlands":{"label":"Netherlands","series_id":"IRLTLT01NLM156N","primary_source":"fred"},
    "switzerland":{"label":"Switzerland","series_id":"IRLTLT01CHM156N","primary_source":"fred"},
    "poland":{"label":"Poland","series_id":"IRLTLT01PLM156N","primary_source":"fred"},
    "hungary":{"label":"Hungary","series_id":"IRLTLT01HUM156N","primary_source":"fred"},
    "south_africa":{"label":"South Africa","series_id":"IRLTLT01ZAM156N","primary_source":"fred"}
}

# ---------------- FETCHERS ----------------

def fetch_fred(series_id):
    url = f"https://api.stlouisfed.org/fred/series/observations?{urlencode({'series_id':series_id,'api_key':API_KEY,'file_type':'json','sort_order':'desc','limit':5})}"
    data = fetch_json(url)

    obs = [o for o in data["observations"] if o["value"] not in (".","")]
    latest, prev = obs[0], obs[1]

    return {
        "date": latest["date"],
        "value": r(float(latest["value"])),
        "previousDate": prev["date"],
        "previousValue": r(float(prev["value"])),
        "change": r(float(latest["value"]) - float(prev["value"]))
    }

# ---------------- BIS ----------------

def fetch_bis(country_code):
    try:
        url = f"https://stats.bis.org/api/v1/data/WS_LONG_RATES/D.{country_code}.LONG_TERM.GOVT.YIELD?format=json"
        data = fetch_json(url)

        obs = data["dataSets"][0]["observations"]
        times = data["structure"]["dimensions"]["observation"][0]["values"]

        keys = sorted(obs.keys(), key=lambda x: int(x.split(":")[0]))

        last = keys[-1]
        prev = keys[-2]

        val = obs[last][0]
        prev_val = obs[prev][0]

        date_idx = int(last.split(":")[0])
        prev_idx = int(prev.split(":")[0])

        return {
            "date": times[date_idx]["id"],
            "value": r(float(val)),
            "previousDate": times[prev_idx]["id"],
            "previousValue": r(float(prev_val)),
            "change": r(float(val) - float(prev_val))
        }

    except:
        return None

# ---------------- ROUTER ----------------

def fetch_data(info):
    if info["primary_source"] == "fred":
        return fetch_fred(info["series_id"]), "fred", "Daily", False
    raise RuntimeError("No valid source")

# ---------------- MAIN ----------------

def main():
    countries = {}
    errors = {}

    # NORMAL DATA
    for slug, info in SERIES.items():
        try:
            obs, source, freq, fb = fetch_data(info)

            stale = staleness_days(obs["date"])
            tier = calc_tier(stale, freq)

            countries[slug] = {
                "label": info["label"],
                "source": source,
                "frequency": freq,
                "date": obs["date"],
                "value": obs["value"],
                "previousDate": obs["previousDate"],
                "previousValue": obs["previousValue"],
                "change": obs["change"],
                "stalenessDays": stale,
                "tier": tier,
                "isFallback": fb
            }

        except Exception as e:
            errors[slug] = str(e)

    # BIS ADD
    BIS = {
        "china": "CN",
        "brazil": "BR",
        "turkey": "TR"
    }

    for slug, code in BIS.items():
        try:
            obs = fetch_bis(code)
            if not obs:
                continue

            stale = staleness_days(obs["date"])
            tier = calc_tier(stale, "Daily")

            countries[slug] = {
                "label": slug.title(),
                "source": "bis",
                "frequency": "Daily",
                "date": obs["date"],
                "value": obs["value"],
                "previousDate": obs["previousDate"],
                "previousValue": obs["previousValue"],
                "change": obs["change"],
                "stalenessDays": stale,
                "tier": tier,
                "isFallback": False
            }

        except Exception as e:
            errors[slug] = str(e)

    json.dump({
        "meta": {
            "title": "BondStats Global Yields",
            "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%d")
        },
        "countries": countries,
        "errors": errors
    }, open(OUTPUT_FILE, "w"), indent=2)


if __name__ == "__main__":
    main()
