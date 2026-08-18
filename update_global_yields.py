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

# ---------------- FETCHERS ----------------

def fetch_fred(series_id):
    url = f"https://api.stlouisfed.org/fred/series/observations?{urlencode({'series_id':series_id,'api_key':API_KEY,'file_type':'json','sort_order':'desc','limit':12})}"
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

def fetch_ecb():
    data = fetch_json("https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?format=jsondata")
    s = next(iter(data["dataSets"][0]["series"].values()))
    obs = s["observations"]
    keys = sorted(obs.keys(), key=lambda x: int(x))
    t = data["structure"]["dimensions"]["observation"][0]["values"]

    return {
        "date": t[int(keys[-1])]["id"],
        "value": r(float(obs[keys[-1]][0])),
        "previousDate": t[int(keys[-2])]["id"],
        "previousValue": r(float(obs[keys[-2]][0])),
        "change": r(float(obs[keys[-1]][0]) - float(obs[keys[-2]][0]))
    }

def fetch_boe():
    try:
        raw = fetch_text("https://api.allorigins.win/raw?url=https://www.bankofengland.co.uk/boeapps/database/FromShowColumns.asp?csv.x=yes&SeriesCodes=IUMAJNB")
        parsed=[]
        for l in raw.splitlines():
            if "/" in l:
                p=l.split(",")
                try: parsed.append((p[0],float(p[1])))
                except: pass
        parsed.sort(key=lambda x: parse_date(x[0]))
        latest, prev = parsed[-1], parsed[-2]
        return {"date":latest[0],"value":r(latest[1]),"previousDate":prev[0],"previousValue":r(prev[1]),"change":r(latest[1]-prev[1])}
    except:
        return None

def fetch_boc(series_id):
    try:
        data = fetch_json(f"https://www.bankofcanada.ca/valet/observations?seriesName={series_id}&recent=5")
        parsed=[(o["d"],float(o[series_id]["v"])) for o in data["observations"] if o.get(series_id)]
        parsed.sort()
        latest, prev = parsed[-1], parsed[-2]
        return {"date":latest[0],"value":r(latest[1]),"previousDate":prev[0],"previousValue":r(prev[1]),"change":r(latest[1]-prev[1])}
    except:
        return None

def fetch_rba(series_id):
    try:
        data = fetch_json(f"https://api.rba.gov.au/statistics/timeseries/{series_id}?format=json")
        parsed=[(o["date"],float(o["value"])) for o in data["series"]["observations"] if o["value"]]
        parsed.sort()
        latest, prev = parsed[-1], parsed[-2]
        return {"date":latest[0],"value":r(latest[1]),"previousDate":prev[0],"previousValue":r(prev[1]),"change":r(latest[1]-prev[1])}
    except:
        return None

def fetch_riksbank(series_id):
    try:
        data = fetch_json(f"https://api.riksbank.se/swea/v1/Observations/{series_id}")
        parsed=[(o["date"],float(o["value"])) for o in data["observations"] if o.get("value")]
        parsed.sort()
        latest, prev = parsed[-1], parsed[-2]
        return {"date":latest[0],"value":r(latest[1]),"previousDate":prev[0],"previousValue":r(prev[1]),"change":r(latest[1]-prev[1])}
    except:
        return None

# ---------------- ROUTER ----------------

def fetch_data(info):
    primary = info["primary_source"]

    # Primary
    if primary == "fred":
        return fetch_fred(info["series_id"]), "fred", info.get("frequency_hint","Monthly"), False

    if primary == "ecb":
        d = fetch_ecb()
        if is_fresh(d["date"]):
            return d,"ecb","Daily",False

    if primary == "boe":
        d = fetch_boe()
        if d and is_fresh(d["date"]):
            return d,"boe","Daily",False

    if primary == "boc":
        d = fetch_boc(info["series_id"])
        if d and is_fresh(d["date"]):
            return d,"boc","Daily",False

    if primary == "rba":
        d = fetch_rba(info["series_id"])
        if d and is_fresh(d["date"]):
            return d,"rba","Daily",False

    if primary == "riksbank":
        d = fetch_riksbank(info["series_id"])
        if d and is_fresh(d["date"]):
            return d,"riksbank","Daily",False

    # fallback
    if info.get("fallback_series_id"):
        return fetch_fred(info["fallback_series_id"]), "fred", "Monthly", True

    raise RuntimeError("All sources failed")

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

            print(f"{info['label']} → {source} | {tier} | fallback={is_fb}")

        except Exception as e:
            errors[slug] = str(e)
            print(f"ERROR {info['label']}: {e}")

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
