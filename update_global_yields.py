import csv
import io
import json
import os

from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from urllib.request import urlopen, Request


# ============================================================
# CONFIG
# ============================================================

API_KEY = os.environ.get("FRED_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "Missing FRED_API_KEY environment variable."
    )


OUTPUT_FILE = "global_yields.json"

TIMEOUT = 25

# Weekend + holidays + publication delay.
FRESHNESS_MAX_DAYS = 7


# ============================================================
# HTTP
# ============================================================

def fetch_bytes(url, accept=None):

    headers = {
        "User-Agent":
            "BondStats Global Yields/3.0"
    }

    if accept:
        headers["Accept"] = accept

    req = Request(
        url,
        headers=headers
    )

    with urlopen(
        req,
        timeout=TIMEOUT
    ) as response:

        return response.read()


def fetch_text(url, accept=None):

    raw = fetch_bytes(
        url,
        accept
    )

    for encoding in (
        "utf-8-sig",
        "utf-8",
        "latin-1"
    ):

        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass

    return raw.decode(
        "utf-8",
        errors="replace"
    )


def fetch_json(url):

    return json.loads(
        fetch_text(
            url,
            "application/json"
        )
    )


# ============================================================
# DATE HELPERS
# ============================================================

def parse_date(value):

    if not value:
        return None

    value = str(value).strip()

    # ISO timestamps
    if "T" in value:
        value = value.split("T")[0]

    formats = (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%d-%m-%Y",
        "%Y/%m/%d"
    )

    for fmt in formats:

        try:
            return datetime.strptime(
                value,
                fmt
            )
        except ValueError:
            pass

    return None


def normalize_date(value):

    d = parse_date(value)

    if not d:
        return None

    return d.strftime(
        "%Y-%m-%d"
    )


def staleness_days(date_str):

    d = parse_date(date_str)

    if not d:
        return 9999

    today = (
        datetime.now(timezone.utc)
        .replace(tzinfo=None)
    )

    return max(
        0,
        (today - d).days
    )


def is_fresh(date_str):

    return (
        staleness_days(date_str)
        <=
        FRESHNESS_MAX_DAYS
    )


def calc_tier(days, frequency):

    if frequency == "Monthly":
        return "monthly"

    if days <= 1:
        return "daily"

    if days <= 7:
        return "delayed"

    return "monthly"


def r(value):

    if value is None:
        return None

    return round(
        float(value),
        4
    )


# ============================================================
# OBSERVATION VALIDATION
# ============================================================

def make_result(
    latest_date,
    latest_value,
    previous_date,
    previous_value
):

    latest_date = normalize_date(
        latest_date
    )

    previous_date = normalize_date(
        previous_date
    )

    if not latest_date:
        raise RuntimeError(
            "Invalid latest observation date."
        )

    if not previous_date:
        raise RuntimeError(
            "Invalid previous observation date."
        )

    latest_value = float(
        latest_value
    )

    previous_value = float(
        previous_value
    )

    # Broad sovereign-yield sanity range.
    if not (
        -5.0
        <
        latest_value
        <
        40.0
    ):
        raise RuntimeError(
            f"Implausible latest yield: "
            f"{latest_value}"
        )

    if not (
        -5.0
        <
        previous_value
        <
        40.0
    ):
        raise RuntimeError(
            f"Implausible previous yield: "
            f"{previous_value}"
        )

    return {

        "date":
            latest_date,

        "value":
            r(latest_value),

        "previousDate":
            previous_date,

        "previousValue":
            r(previous_value),

        "change":
            r(
                latest_value
                -
                previous_value
            )
    }


def valid_daily_result(result):

    if not result:
        return False

    if not is_fresh(
        result.get("date")
    ):
        return False

    value = result.get(
        "value"
    )

    if value is None:
        return False

    if not (
        -5.0
        <
        float(value)
        <
        40.0
    ):
        return False

    return True


# ============================================================
# EXISTING COUNTRY DEFINITIONS
#
# Slugs are intentionally preserved.
# ============================================================

SERIES = {

    "united_states": {
        "label":"United States",
        "series_id":"DGS10",
        "primary_source":"fred",
        "frequency_hint":"Daily"
    },

    "euro_area": {
        "label":"Euro Area",
        "primary_source":"ecb"
    },

    "united_kingdom": {
        "label":"United Kingdom",
        "primary_source":"riksbank",
        "riksbank_series":"GBGVB10Y",
        "fallback_series_id":"IRLTLT01GBM156N"
    },

    "canada": {
        "label":"Canada",
        "primary_source":"boc",
        "series_id":"V39055",
        "fallback_series_id":"IRLTLT01CAM156N"
    },

    "australia": {
        "label":"Australia",
        "primary_source":"rba",
        "fallback_series_id":"IRLTLT01AUM156N"
    },

    "sweden": {
        "label":"Sweden",
        "primary_source":"riksbank",
        "riksbank_series":"SEGVB10YC",
        "fallback_series_id":"IRLTLT01SEM156N"
    },

    "germany": {
        "label":"Germany",
        "primary_source":"riksbank",
        "riksbank_series":"DEGVB10Y",
        "fallback_series_id":"IRLTLT01DEM156N"
    },

    "france": {
        "label":"France",
        "primary_source":"riksbank",
        "riksbank_series":"FRGVB10Y",
        "fallback_series_id":"IRLTLT01FRM156N"
    },

    "italy": {
        "label":"Italy",
        "series_id":"IRLTLT01ITM156N",
        "primary_source":"market"
    },

    "spain": {
        "label":"Spain",
        "series_id":"IRLTLT01ESM156N",
        "primary_source":"market"
    },

    "netherlands": {
        "label":"Netherlands",
        "primary_source":"riksbank",
        "riksbank_series":"NLGVB10Y",
        "fallback_series_id":"IRLTLT01NLM156N"
    },

    "switzerland": {
        "label":"Switzerland",
        "series_id":"IRLTLT01CHM156N",
        "primary_source":"market"
    },

    "sweden_fred": {
        "label":"Sweden (OECD)",
        "series_id":"IRLTLT01SEM156N",
        "primary_source":"fred"
    },

    "belgium": {
        "label":"Belgium",
        "series_id":"IRLTLT01BEM156N",
        "primary_source":"market"
    },

    "austria": {
        "label":"Austria",
        "series_id":"IRLTLT01ATM156N",
        "primary_source":"market"
    },

    "portugal": {
        "label":"Portugal",
        "series_id":"IRLTLT01PTM156N",
        "primary_source":"market"
    },

    "finland": {
        "label":"Finland",
        "primary_source":"riksbank",
        "riksbank_series":"FIGVB10Y",
        "fallback_series_id":"IRLTLT01FIM156N"
    },

    "ireland": {
        "label":"Ireland",
        "series_id":"IRLTLT01IEM156N",
        "primary_source":"market"
    },

    "denmark": {
        "label":"Denmark",
        "primary_source":"riksbank",
        "riksbank_series":"DKGVB10Y",
        "fallback_series_id":"IRLTLT01DKM156N"
    },

    "norway": {
        "label":"Norway",
        "primary_source":"riksbank",
        "riksbank_series":"NOGVB10Y",
        "fallback_series_id":"IRLTLT01NOM156N"
    },

    "india": {
        "label":"India",
        "series_id":"INDIRLTLT01STM",
        "primary_source":"market"
    },

    "south_korea": {
        "label":"South Korea",
        "series_id":"IRLTLT01KRM156N",
        "primary_source":"market"
    },

    "new_zealand": {
        "label":"New Zealand",
        "series_id":"IRLTLT01NZM156N",
        "primary_source":"market"
    },

    "greece": {
        "label":"Greece",
        "series_id":"IRLTLT01GRM156N",
        "primary_source":"market"
    },

    "israel": {
        "label":"Israel",
        "series_id":"IRLTLT01ILM156N",
        "primary_source":"market"
    },

    "mexico": {
        "label":"Mexico",
        "series_id":"IRLTLT01MXM156N",
        "primary_source":"market"
    },

    "poland": {
        "label":"Poland",
        "series_id":"IRLTLT01PLM156N",
        "primary_source":"market"
    },

    "czech_republic": {
        "label":"Czech Republic",
        "series_id":"IRLTLT01CZM156N",
        "primary_source":"market"
    },

    "hungary": {
        "label":"Hungary",
        "series_id":"IRLTLT01HUM156N",
        "primary_source":"market"
    },

    "slovakia": {
        "label":"Slovakia",
        "series_id":"IRLTLT01SKM156N",
        "primary_source":"market"
    },

    "slovenia": {
        "label":"Slovenia",
        "series_id":"IRLTLT01SIM156N",
        "primary_source":"market"
    },

    "lithuania": {
        "label":"Lithuania",
        "series_id":"LTUIRLTLT01STM",
        "primary_source":"market"
    },

    "chile": {
        "label":"Chile",
        "series_id":"IRLTLT01CLM156N",
        "primary_source":"market"
    },

    "south_africa": {
        "label":"South Africa",
        "series_id":"IRLTLT01ZAM156N",
        "primary_source":"market"
    }
}


# ============================================================
# STOOQ SYMBOLS
#
# Public daily market-data feed.
# Invalid / stale symbols are automatically rejected.
# ============================================================

STOOQ_SYMBOLS = {

    "united_kingdom":
        "10YGBY.B",

    "canada":
        "10YCAY.B",

    "australia":
        "10YAUY.B",

    "sweden":
        "10YSEY.B",

    "germany":
        "10YDEY.B",

    "france":
        "10YFRY.B",

    "italy":
        "10YITY.B",

    "spain":
        "10YESY.B",

    "netherlands":
        "10YNLY.B",

    "switzerland":
        "10YCHY.B",

    "belgium":
        "10YBEY.B",

    "austria":
        "10YATY.B",

    "portugal":
        "10YPTY.B",

    "finland":
        "10YFIY.B",

    "ireland":
        "10YIEY.B",

    "denmark":
        "10YDKY.B",

    "norway":
        "10YNOY.B",

    "india":
        "10YINY.B",

    "south_korea":
        "10YKRY.B",

    "new_zealand":
        "10YNZY.B",

    "greece":
        "10YGRY.B",

    "israel":
        "10YILY.B",

    "mexico":
        "10YMXY.B",

    "poland":
        "10YPLY.B",

    "czech_republic":
        "10YCZY.B",

    "hungary":
        "10YHUY.B",

    "slovakia":
        "10YSKY.B",

    "slovenia":
        "10YSIY.B",

    "lithuania":
        "10YLTY.B",

    "chile":
        "10YCLY.B",

    "south_africa":
        "10YZAY.B"
}


# ============================================================
# FRED
# ============================================================

def fetch_fred(series_id):

    url = (
        "https://api.stlouisfed.org/"
        "fred/series/observations?"
        +
        urlencode({
            "series_id":
                series_id,

            "api_key":
                API_KEY,

            "file_type":
                "json",

            "sort_order":
                "desc",

            "limit":
                12
        })
    )

    data = fetch_json(url)

    observations = [

        item

        for item in
        data.get(
            "observations",
            []
        )

        if item.get("value")
        not in (
            ".",
            "",
            None
        )
    ]

    if len(observations) < 2:

        raise RuntimeError(
            f"FRED insufficient data "
            f"for {series_id}"
        )

    latest = observations[0]
    previous = observations[1]

    return make_result(

        latest["date"],
        latest["value"],

        previous["date"],
        previous["value"]
    )


# ============================================================
# ECB
# ============================================================

def fetch_ecb():

    url = (
        "https://data-api.ecb.europa.eu/"
        "service/data/YC/"
        "B.U2.EUR.4F.G_N_A."
        "SV_C_YM.SR_10Y"
        "?format=jsondata"
    )

    data = fetch_json(url)

    series = next(
        iter(
            data[
                "dataSets"
            ][0][
                "series"
            ].values()
        )
    )

    observations = (
        series[
            "observations"
        ]
    )

    keys = sorted(
        observations.keys(),
        key=lambda x:
            int(x)
    )

    times = (
        data[
            "structure"
        ][
            "dimensions"
        ][
            "observation"
        ][0][
            "values"
        ]
    )

    latest_key = keys[-1]
    previous_key = keys[-2]

    return make_result(

        times[
            int(latest_key)
        ]["id"],

        observations[
            latest_key
        ][0],

        times[
            int(previous_key)
        ]["id"],

        observations[
            previous_key
        ][0]
    )


# ============================================================
# RIKSBANK
#
# One official public API now supplies:
#
# Sweden
# Germany
# France
# Netherlands
# UK
# Norway
# Denmark
# Finland
# ============================================================

def fetch_riksbank(series_id):

    url = (
        "https://api.riksbank.se/"
        "swea/v1/Observations/"
        +
        series_id
    )

    data = fetch_json(url)

    if isinstance(data, dict):

        observations = (
            data.get("observations")
            or
            data.get("Observations")
            or
            data.get("value")
            or
            []
        )

    elif isinstance(data, list):

        observations = data

    else:

        observations = []


    parsed = []


    for item in observations:

        if not isinstance(
            item,
            dict
        ):
            continue

        date = (

            item.get("date")
            or
            item.get("Date")
            or
            item.get("dateValue")
            or
            item.get(
                "observationDate"
            )
        )

        value = (

            item.get("value")
            or
            item.get("Value")
            or
            item.get(
                "observationValue"
            )
        )

        if (
            not date
            or
            value is None
        ):
            continue

        try:

            parsed.append(
                (
                    normalize_date(
                        date
                    ),
                    float(value)
                )
            )

        except Exception:
            pass


    parsed = [
        item
        for item in parsed
        if item[0]
    ]


    parsed.sort(
        key=lambda item:
            item[0]
    )


    if len(parsed) < 2:

        raise RuntimeError(
            "Riksbank returned "
            "insufficient observations "
            f"for {series_id}"
        )


    latest = parsed[-1]
    previous = parsed[-2]


    return make_result(

        latest[0],
        latest[1],

        previous[0],
        previous[1]
    )


# ============================================================
# BANK OF CANADA
#
# Official Valet API
# ============================================================

def fetch_boc(series_id):

    url = (
        "https://www.bankofcanada.ca/"
        "valet/observations/"
        f"{series_id}/json"
        "?recent=10"
    )

    data = fetch_json(url)

    parsed = []


    for observation in data.get(
        "observations",
        []
    ):

        series = observation.get(
            series_id
        )

        if not series:
            continue

        value = series.get("v")

        date = observation.get("d")

        if (
            value is None
            or
            not date
        ):
            continue

        parsed.append(
            (
                date,
                float(value)
            )
        )


    parsed.sort(
        key=lambda item:
            item[0]
    )


    if len(parsed) < 2:

        raise RuntimeError(
            "Bank of Canada returned "
            "insufficient observations."
        )


    latest = parsed[-1]
    previous = parsed[-2]


    return make_result(

        latest[0],
        latest[1],

        previous[0],
        previous[1]
    )


# ============================================================
# RBA
#
# Official public F2.1 CSV.
# If parsing ever changes, Stooq takes over.
# ============================================================

def fetch_rba():

    url = (
        "https://www.rba.gov.au/"
        "statistics/tables/csv/"
        "f2.1-data.csv"
    )

    text = fetch_text(url)

    rows = list(
        csv.reader(
            io.StringIO(text)
        )
    )

    ten_year_column = None


    for row in rows[:20]:

        for index, cell in enumerate(row):

            normalized = (
                cell.lower()
                .replace("-", " ")
            )

            if (
                "10 year"
                in normalized
                and
                (
                    "government"
                    in normalized
                    or
                    "bond"
                    in normalized
                )
            ):

                ten_year_column = index
                break

        if ten_year_column is not None:
            break


    if ten_year_column is None:

        raise RuntimeError(
            "Could not locate RBA "
            "10Y government-bond column."
        )


    observations = []


    for row in rows:

        if (
            len(row)
            <=
            ten_year_column
        ):
            continue

        date = parse_date(
            row[0]
        )

        if not date:
            continue

        raw_value = (
            row[
                ten_year_column
            ].strip()
        )

        try:
            value = float(
                raw_value
            )
        except ValueError:
            continue

        observations.append(
            (
                date.strftime(
                    "%Y-%m-%d"
                ),
                value
            )
        )


    observations.sort(
        key=lambda item:
            item[0]
    )


    if len(observations) < 2:

        raise RuntimeError(
            "RBA returned insufficient "
            "10Y observations."
        )


    latest = observations[-1]
    previous = observations[-2]


    return make_result(

        latest[0],
        latest[1],

        previous[0],
        previous[1]
    )


# ============================================================
# STOOQ DAILY PUBLIC CSV FEED
# ============================================================

def fetch_stooq(symbol):

    today = datetime.now(
        timezone.utc
    )

    start = (
        today
        -
        timedelta(days=30)
    )


    url = (
        "https://stooq.com/q/d/l/?"
        +
        urlencode({
            "s":
                symbol.lower(),

            "d1":
                start.strftime(
                    "%Y%m%d"
                ),

            "d2":
                today.strftime(
                    "%Y%m%d"
                ),

            "i":
                "d"
        })
    )


    text = fetch_text(
        url,
        "text/csv"
    )


    reader = csv.DictReader(
        io.StringIO(text)
    )


    observations = []


    for row in reader:

        date = (
            row.get("Date")
            or
            row.get("DATE")
            or
            row.get("date")
        )

        close = (
            row.get("Close")
            or
            row.get("CLOSE")
            or
            row.get("close")
        )


        if (
            not date
            or
            close in (
                None,
                "",
                "N/D"
            )
        ):
            continue


        try:

            observations.append(
                (
                    normalize_date(
                        date
                    ),
                    float(close)
                )
            )

        except Exception:
            continue


    observations = [

        item

        for item in observations

        if item[0]
    ]


    observations.sort(
        key=lambda item:
            item[0]
    )


    if len(observations) < 2:

        raise RuntimeError(
            f"Stooq returned insufficient "
            f"data for {symbol}"
        )


    latest = observations[-1]
    previous = observations[-2]


    result = make_result(

        latest[0],
        latest[1],

        previous[0],
        previous[1]
    )


    if not valid_daily_result(
        result
    ):

        raise RuntimeError(
            f"Stooq {symbol} is stale "
            f"or invalid: "
            f"{result['date']}"
        )


    return result


# ============================================================
# MARKET FALLBACK
# ============================================================

def try_market(slug):

    symbol = STOOQ_SYMBOLS.get(
        slug
    )

    if not symbol:

        return None

    try:

        result = fetch_stooq(
            symbol
        )

        print(
            f"Stooq {slug}: "
            f"{result['date']} "
            f"{result['value']}"
        )

        return result

    except Exception as error:

        print(
            f"Stooq failed for "
            f"{slug}: {error}"
        )

        return None


# ============================================================
# ROUTER
#
# OFFICIAL
# ↓
# STOOQ DAILY
# ↓
# FRED/OECD MONTHLY
# ↓
# OLD JSON
# ============================================================

def fetch_data(
    slug,
    info
):

    primary = info[
        "primary_source"
    ]


    # --------------------------------------------------------
    # UNITED STATES
    # --------------------------------------------------------

    if (
        slug ==
        "united_states"
    ):

        result = fetch_fred(
            info["series_id"]
        )

        return (
            result,
            "fred",
            "Daily",
            False
        )


    # --------------------------------------------------------
    # EURO AREA
    # --------------------------------------------------------

    if (
        slug ==
        "euro_area"
    ):

        try:

            result = fetch_ecb()

            if valid_daily_result(
                result
            ):

                return (
                    result,
                    "ecb",
                    "Daily",
                    False
                )

        except Exception as error:

            print(
                "ECB failed:",
                error
            )


    # --------------------------------------------------------
    # RIKSBANK MULTI-COUNTRY
    # --------------------------------------------------------

    if (
        primary ==
        "riksbank"
    ):

        try:

            result = fetch_riksbank(
                info[
                    "riksbank_series"
                ]
            )

            if valid_daily_result(
                result
            ):

                return (
                    result,
                    "riksbank",
                    "Daily",
                    False
                )

        except Exception as error:

            print(
                f"Riksbank failed "
                f"for {slug}: "
                f"{error}"
            )


    # --------------------------------------------------------
    # BANK OF CANADA
    # --------------------------------------------------------

    if primary == "boc":

        try:

            result = fetch_boc(
                info[
                    "series_id"
                ]
            )

            if valid_daily_result(
                result
            ):

                return (
                    result,
                    "boc",
                    "Daily",
                    False
                )

        except Exception as error:

            print(
                "BoC failed:",
                error
            )


    # --------------------------------------------------------
    # RBA
    # --------------------------------------------------------

    if primary == "rba":

        try:

            result = fetch_rba()

            if valid_daily_result(
                result
            ):

                return (
                    result,
                    "rba",
                    "Daily",
                    False
                )

        except Exception as error:

            print(
                "RBA failed:",
                error
            )


    # --------------------------------------------------------
    # DAILY PUBLIC MARKET FEED
    # --------------------------------------------------------

    market = try_market(
        slug
    )


    if market:

        return (
            market,
            "stooq",
            "Daily",
            False
        )


    # --------------------------------------------------------
    # EXISTING FRED/OECD FALLBACK
    # --------------------------------------------------------

    fallback = (

        info.get(
            "fallback_series_id"
        )

        or

        info.get(
            "series_id"
        )
    )


    if fallback:

        result = fetch_fred(
            fallback
        )

        return (
            result,
            "fred",
            (
                info.get(
                    "frequency_hint"
                )
                or
                "Monthly"
            ),
            True
        )


    raise RuntimeError(
        "All data sources failed."
    )


# ============================================================
# LAST KNOWN GOOD JSON
# ============================================================

def load_existing():

    if not os.path.exists(
        OUTPUT_FILE
    ):

        return {
            "countries": {}
        }


    try:

        with open(
            OUTPUT_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception as error:

        print(
            "Existing JSON read failed:",
            error
        )

        return {
            "countries": {}
        }


# ============================================================
# MAIN
# ============================================================

def main():

    existing = load_existing()

    old_countries = (
        existing.get(
            "countries",
            {}
        )
    )


    countries = {}

    errors = {}


    for slug, info in SERIES.items():

        print(
            "\n================================"
        )

        print(
            "Updating:",
            info["label"]
        )


        try:

            (
                observation,
                source,
                frequency,
                is_fallback
            ) = fetch_data(
                slug,
                info
            )


            stale = staleness_days(
                observation[
                    "date"
                ]
            )


            tier = calc_tier(
                stale,
                frequency
            )


            countries[slug] = {

                "label":
                    info["label"],

                "source":
                    source,

                "frequency":
                    frequency,

                "date":
                    observation["date"],

                "value":
                    observation["value"],

                "previousDate":
                    observation[
                        "previousDate"
                    ],

                "previousValue":
                    observation[
                        "previousValue"
                    ],

                "change":
                    observation["change"],

                "stalenessDays":
                    stale,

                "tier":
                    tier,

                "isFallback":
                    is_fallback
            }


            print(
                info["label"],
                "→",
                source,
                "|",
                observation["date"],
                "|",
                observation["value"],
                "|",
                tier
            )


        except Exception as error:

            errors[slug] = str(
                error
            )


            print(
                "ERROR",
                info["label"],
                ":",
                error
            )


            # -----------------------------------------------
            # SAFETY:
            # NEVER DELETE EXISTING WORKING DATA.
            # -----------------------------------------------

            old = old_countries.get(
                slug
            )


            if old:

                countries[slug] = old

                print(
                    "Preserving last "
                    "known good value."
                )


    # ========================================================
    # HARD SAFETY CHECK
    # ========================================================

    if not countries:

        raise RuntimeError(
            "No country data available. "
            "Live JSON will not be replaced."
        )


    for required in (
        "united_states",
        "euro_area"
    ):

        if required not in countries:

            raise RuntimeError(
                f"Critical market "
                f"{required} missing. "
                "Live JSON will not be replaced."
            )


    result = {

        "meta": {

            "title":
                "BondStats Global Yields",

            "lastUpdated":
                datetime.now(
                    timezone.utc
                ).strftime(
                    "%Y-%m-%d"
                )
        },

        "countries":
            countries,

        "errors":
            errors
    }


    # ========================================================
    # ATOMIC WRITE
    # ========================================================

    temp_file = (
        OUTPUT_FILE
        +
        ".tmp"
    )


    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False
        )


    # Validate generated JSON before publishing it.
    with open(
        temp_file,
        "r",
        encoding="utf-8"
    ) as file:

        json.load(file)


    os.replace(
        temp_file,
        OUTPUT_FILE
    )


    # ========================================================
    # SUMMARY
    # ========================================================

    daily = 0
    delayed = 0
    monthly = 0


    for country in countries.values():

        tier = country.get(
            "tier"
        )

        if tier == "daily":
            daily += 1

        elif tier == "delayed":
            delayed += 1

        else:
            monthly += 1


    print(
        "\n================================"
    )

    print(
        "BondStats Global Yields updated."
    )

    print(
        "Countries:",
        len(countries)
    )

    print(
        "Daily:",
        daily
    )

    print(
        "Delayed:",
        delayed
    )

    print(
        "Monthly fallback:",
        monthly
    )

    print(
        "Errors:",
        len(errors)
    )


if __name__ == "__main__":
    main()
