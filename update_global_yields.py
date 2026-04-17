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

# ---------------- DATE ----------------

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
    "euro_area": {"label":"Euro Area","primary_source":"ecb"},
    "united_kingdom": {"label":"United Kingdom","primary_source":"boe","fallback_series_id":"IRLTLT01GBM156N"},
    "canada": {"label":"Canada","primary_source":"boc","series_id":"V39055","fallback_series_id":"IRLTLT01CAM156N"},
    "australia": {"label":"Australia","primary_source":"rba","series_id":"F2","fallback_series_id":"IRLTLT01AUM156N"},
    "sweden": {"label":"Sweden","primary_source":"riksbank","series_id":"SEK_GOVT_BOND_10Y","fallback_series_id":"IRLTLT01SEM156N"},

    "germany":{"label":"Germany","series_id":"IRLTLT01DEM156N","primary_source":"fred"},
    "france":{"label":"France","series_id":"IRLTLT01FRM156N","primary_source":"fred"},
    "italy":{"label":"Italy","series_id":"IRLTLT01ITM156N","primary_source":"fred"},
    "spain":{"label":"Spain","series_id":"IRLTLT01ESM156N","primary_source":"fred"},
    "netherlands":{"label":"Netherlands","series_id":"IRLTLT01NLM156N","primary_source":"fred"},
    "switzerland":{"label":"Switzerland","series_id":"IRLTLT01CHM156N","primary_source":"fred"},
    "sweden_fred":{"label":"Sweden (OECD)","series_id":"IRLTLT01SEM156N","primary_source":"fred"},
    "belgium":{"label":"Belgium","series_id":"IRLTLT01BEM156N","primary_source":"fred"},
    "austria":{"label":"Austria","series_id":"IRLTLT01ATM156N","primary_source":"fred"},
    "portugal":{"label":"Portugal","series_id":"IRLTLT01PTM156N","primary_source":"fred"},
    "finland":{"label":"Finland","series_id":"IRLTLT01FIM156N","primary_source":"fred"},
    "ireland":{"label":"Ireland","series_id":"IRLTLT01IEM156N","primary_source":"fred"},
    "denmark":{"label":"Denmark","series_id":"IRLTLT01DKM156N","primary_source":"fred"},
    "norway":{"label":"Norway","series_id":"IRLTLT01NOM156N","primary_source":"fred"},
    "india":{"label":"India","series_id":"INDIRLTLT01STM","primary_source":"fred"},
    "south_korea":{"label":"South Korea","series_id":"IRLTLT01KRM156N","primary_source":"fred"},
    "new_zealand":{"label":"New Zealand","series_id":"IRLTLT01NZM156N","primary_source":"fred"},
    "greece":{"label":"Greece","series_id":"IRLTLT01GRM156N","primary_source":"fred"},
    "israel":{"label":"Israel","series_id":"IRLTLT01ILM156N","primary_source":"fred"},
    "mexico":{"label":"Mexico","series_id":"IRLTLT01MXM156N","primary_source":"fred"},
    "poland":{"label":"Poland","series_id":"IRLTLT01PLM156N","primary_source":"fred"},
    "czech_republic":{"label":"Czech Republic","series_id":"IRLTLT01CZM156N","primary_source":"fred"},
    "hungary":{"label":"Hungary","series_id":"IRLTLT01HUM156N","primary_source":"fred"},
    "slovakia":{"label":"Slovakia","series_id":"IRLTLT01SKM156N","primary_source":"fred"},
    "slovenia":{"label":"Slovenia","series_id":"IRLTLT01SIM156N","primary_source":"fred"},
    "lithuania":{"label":"Lithuania","series_id":"LTUIRLTLT01STM","primary_source":"fred"},
    "chile":{"label":"Chile","series_id":"IRLTLT01CLM156N","primary_source":"fred"},
    "south_africa":{"label":"South Africa","series_id":"IRLTLT01ZAM156N","primary_source":"fred"}
}

# ---------------- BIS FETCH ----------------

def fetch_bis_long_rate(country_code):
    try:
        url = f"https://stats.bis.org/api/v1/data/WS_LONG_RATES/D.{country_code}.LONG_TERM.GOVT.YIELD?format=json"
        data = fetch_json(url)

        obs = data["dataSets"][0]["observations"]
        times = data["structure"]["dimensions"]["observation"][0]["values"]

        if not obs:
            return None

        keys = sorted(obs.keys(), key=lambda x: int(x.split(":")[0]))

        last = keys[-1]
        prev = keys[-2] if len(keys) > 1 else None

        val = obs[last][0]
        prev_val = obs[prev][0] if prev else None

        if val is None:
            return None

        date_idx = int(last.split(":")[0])
        prev_idx = int(prev.split(":")[0]) if prev else None

        return {
            "date": times[date_idx]["id"],
            "value": r(float(val)),
            "previousDate": times[prev_idx]["id"] if prev else None,
            "previousValue": r(float(prev_val)) if prev_val else None,
            "change": r(float(val) - float(prev_val)) if prev_val else None
        }

    except Exception as e:
        print(f"BIS error ({country_code}):", e)
        return None

# ---------------- FETCHERS (unchanged) ----------------

# ... (ALLE deine bestehenden fetch_* Funktionen bleiben exakt gleich)

# ---------------- MAIN ----------------

def main():
    countries = {}
    errors = {}

    for slug, info in SERIES.items():
        try:
            obs, source, freq, is_fb = fetch_data(info)
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
                "isFallback": is_fb
            }

        except Exception as e:
            errors[slug] = str(e)

    # -------- BIS EXTENSION --------

    BIS_COUNTRIES = {
        "china": "CN",
        "brazil": "BR",
        "turkey": "TR",
        "indonesia": "ID",
        "saudi_arabia": "SA"
    }

    for slug, code in BIS_COUNTRIES.items():
        try:
            obs = fetch_bis_long_rate(code)
            if not obs:
                continue

            stale = staleness_days(obs["date"])
            tier = calc_tier(stale, "Daily")

            countries[slug] = {
                "label": slug.replace("_", " ").title(),
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
