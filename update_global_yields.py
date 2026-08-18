import csv
import io
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# ============================================================
# CONFIG
# ============================================================

FRED_API_KEY = os.environ.get("FRED_API_KEY")

if not FRED_API_KEY:
    raise RuntimeError("Missing FRED_API_KEY")

OUTPUT_FILE = "global_yields.json"
TEMP_FILE = "global_yields.json.tmp"

TIMEOUT = 30
DAILY_MAX_AGE = 7


# ============================================================
# HTTP
# ============================================================

def http_bytes(url, accept="*/*"):

    request = Request(
        url,
        headers={
            "User-Agent": "BondStats-Global-Yields/4.0",
            "Accept": accept
        }
    )

    with urlopen(
        request,
        timeout=TIMEOUT
    ) as response:

        return response.read()


def http_text(url, accept="*/*"):

    raw = http_bytes(url, accept)

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


def http_json(url):

    return json.loads(
        http_text(
            url,
            "application/json"
        )
    )


# ============================================================
# BASIC HELPERS
# ============================================================

def parse_date(value):

    if value is None:
        return None

    value = str(value).strip()

    if "T" in value:
        value = value.split("T")[0]

    formats = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%d-%m-%Y"
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

    parsed = parse_date(value)

    if not parsed:
        return None

    return parsed.strftime("%Y-%m-%d")


def days_old(value):

    parsed = parse_date(value)

    if not parsed:
        return 9999

    today = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    return max(
        0,
        (today - parsed).days
    )


def round_value(value):

    return round(
        float(value),
        4
    )


def valid_yield(value):

    try:
        value = float(value)
    except (TypeError, ValueError):
        return False

    return -5.0 < value < 40.0


def make_observation(
    date,
    value,
    previous_date,
    previous_value
):

    date = normalize_date(date)
    previous_date = normalize_date(
        previous_date
    )

    if not date or not previous_date:
        raise RuntimeError(
            "Invalid observation date"
        )

    if not valid_yield(value):
        raise RuntimeError(
            f"Invalid yield: {value}"
        )

    if not valid_yield(previous_value):
        raise RuntimeError(
            f"Invalid previous yield: "
            f"{previous_value}"
        )

    value = float(value)
    previous_value = float(
        previous_value
    )

    return {
        "date": date,
        "value": round_value(value),

        "previousDate":
            previous_date,

        "previousValue":
            round_value(
                previous_value
            ),

        "change":
            round_value(
                value -
                previous_value
            )
    }


def is_current(obs):

    if not obs:
        return False

    return (
        valid_yield(
            obs.get("value")
        )
        and
        days_old(
            obs.get("date")
        )
        <= DAILY_MAX_AGE
    )


def tier_for(
    date,
    frequency
):

    age = days_old(date)

    if frequency == "Monthly":
        return "monthly"

    if age <= 1:
        return "daily"

    if age <= 7:
        return "delayed"

    return "monthly"


# ============================================================
# EXISTING DATA
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

    except Exception as exc:

        print(
            "Existing JSON unreadable:",
            exc
        )

        return {
            "countries": {}
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
                FRED_API_KEY,

            "file_type":
                "json",

            "sort_order":
                "desc",

            "limit":
                20
        })
    )

    data = http_json(url)

    observations = []

    for item in data.get(
        "observations",
        []
    ):

        value = item.get("value")

        if value in (
            ".",
            "",
            None
        ):
            continue

        if not valid_yield(value):
            continue

        observations.append(
            (
                item["date"],
                float(value)
            )
        )

    if len(observations) < 2:
        raise RuntimeError(
            f"FRED {series_id}: "
            "not enough observations"
        )

    return make_observation(
        observations[0][0],
        observations[0][1],
        observations[1][0],
        observations[1][1]
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

    data = http_json(url)

    dataset = data[
        "dataSets"
    ][0]

    series = next(
        iter(
            dataset[
                "series"
            ].values()
        )
    )

    observations = (
        series["observations"]
    )

    dates = (
        data["structure"]
        ["dimensions"]
        ["observation"][0]
        ["values"]
    )

    keys = sorted(
        observations,
        key=lambda x:
            int(x)
    )

    latest = keys[-1]
    previous = keys[-2]

    return make_observation(

        dates[
            int(latest)
        ]["id"],

        observations[
            latest
        ][0],

        dates[
            int(previous)
        ]["id"],

        observations[
            previous
        ][0]
    )


# ============================================================
# RIKSBANK
#
# IMPORTANT:
# Correct official endpoint:
#
# /Observations/Latest/ByGroup/100
#
# Group 100 =
# international 10Y government bonds.
# ============================================================

RIKSBANK_GROUP_URL = (
    "https://api.riksbank.se/"
    "swea/v1/Observations/"
    "Latest/ByGroup/100"
)


RIKSBANK_SERIES = {

    "united_states":
        "USGVB10Y",

    "germany":
        "DEGVB10Y",

    "france":
        "FRGVB10Y",

    "netherlands":
        "NLGVB10Y",

    "united_kingdom":
        "GBGVB10Y",

    "norway":
        "NOGVB10Y",

    "denmark":
        "DKGVB10Y",

    "finland":
        "FIGVB10Y"
}


def identify_series(item):

    candidates = (
        "seriesId",
        "seriesID",
        "SeriesId",
        "SeriesID",
        "series",
        "Series"
    )

    for key in candidates:

        value = item.get(key)

        if value:
            return str(value).upper()

    return None


def identify_value(item):

    candidates = (
        "value",
        "Value",
        "observationValue",
        "ObservationValue"
    )

    for key in candidates:

        value = item.get(key)

        if value is not None:
            return value

    return None


def identify_date(item):

    candidates = (
        "date",
        "Date",
        "observationDate",
        "ObservationDate",
        "dateValue",
        "DateValue"
    )

    for key in candidates:

        value = item.get(key)

        if value:
            return value

    return None


def flatten_items(data):

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        for key in (
            "observations",
            "Observations",
            "value",
            "Value",
            "data",
            "Data"
        ):

            value = data.get(key)

            if isinstance(value, list):
                return value

        return [data]

    return []


def fetch_riksbank_group():

    data = http_json(
        RIKSBANK_GROUP_URL
    )

    items = flatten_items(data)

    results = {}

    reverse_map = {
        series:
            slug
        for slug, series
        in RIKSBANK_SERIES.items()
    }

    for item in items:

        if not isinstance(
            item,
            dict
        ):
            continue

        series_id = identify_series(
            item
        )

        if not series_id:
            continue

        slug = reverse_map.get(
            series_id
        )

        if not slug:
            continue

        value = identify_value(
            item
        )

        date = identify_date(
            item
        )

        if (
            value is None
            or
            not date
            or
            not valid_yield(value)
        ):
            continue

        results[slug] = {
            "date":
                normalize_date(date),

            "value":
                float(value)
        }

    return results


# ============================================================
# RIKSBANK SWEDEN
# ============================================================

def fetch_riksbank_latest(
    series_id
):

    url = (
        "https://api.riksbank.se/"
        "swea/v1/Observations/"
        "Latest/"
        +
        series_id
    )

    data = http_json(url)

    items = flatten_items(data)

    if not items:
        raise RuntimeError(
            f"Riksbank {series_id}: "
            "empty response"
        )

    item = items[0]

    date = identify_date(item)
    value = identify_value(item)

    if not date:
        raise RuntimeError(
            "Riksbank date missing"
        )

    if not valid_yield(value):
        raise RuntimeError(
            "Riksbank yield invalid"
        )

    return {
        "date":
            normalize_date(date),

        "value":
            float(value)
    }


# ============================================================
# BANK OF CANADA
# ============================================================

def fetch_boc():

    series_id = "V39055"

    url = (
        "https://www.bankofcanada.ca/"
        "valet/observations/"
        f"{series_id}/json"
        "?recent=15"
    )

    data = http_json(url)

    rows = []

    for item in data.get(
        "observations",
        []
    ):

        series = item.get(
            series_id
        )

        if not series:
            continue

        value = series.get("v")
        date = item.get("d")

        if (
            not date
            or
            not valid_yield(value)
        ):
            continue

        rows.append(
            (
                date,
                float(value)
            )
        )

    rows.sort(
        key=lambda x:
            x[0]
    )

    if len(rows) < 2:
        raise RuntimeError(
            "BoC: not enough observations"
        )

    latest = rows[-1]
    previous = rows[-2]

    return make_observation(
        latest[0],
        latest[1],
        previous[0],
        previous[1]
    )


# ============================================================
# RBA
#
# IMPORTANT:
# F2 = daily/near-daily table.
# Do NOT use F2.1 here;
# F2.1 is monthly.
# ============================================================

def detect_delimiter(text):

    try:

        return csv.Sniffer().sniff(
            text[:8000],
            delimiters=",;\t"
        )

    except csv.Error:

        return csv.excel


def fetch_rba():

    possible_urls = (

        "https://www.rba.gov.au/"
        "statistics/tables/csv/"
        "f2-data.csv",

        "https://www.rba.gov.au/"
        "statistics/tables/csv/"
        "f2.csv"
    )

    last_error = None

    for url in possible_urls:

        try:

            text = http_text(
                url,
                "text/csv"
            )

            rows = list(
                csv.reader(
                    io.StringIO(text),
                    dialect=
                        detect_delimiter(
                            text
                        )
                )
            )

            column = None

            for row in rows[:30]:

                for index, cell in enumerate(
                    row
                ):

                    label = re.sub(
                        r"\s+",
                        " ",
                        cell.lower()
                        .replace("-", " ")
                    )

                    if (
                        "10 year"
                        in label
                        and
                        (
                            "government"
                            in label
                            or
                            "bond"
                            in label
                        )
                    ):

                        column = index
                        break

                if column is not None:
                    break

            if column is None:
                raise RuntimeError(
                    "RBA 10Y column "
                    "not found"
                )

            observations = []

            for row in rows:

                if len(row) <= column:
                    continue

                date = parse_date(
                    row[0]
                )

                if not date:
                    continue

                value = (
                    row[column]
                    .strip()
                    .replace("%", "")
                )

                if not valid_yield(value):
                    continue

                observations.append(
                    (
                        date.strftime(
                            "%Y-%m-%d"
                        ),
                        float(value)
                    )
                )

            observations.sort(
                key=lambda x:
                    x[0]
            )

            if len(observations) < 2:
                raise RuntimeError(
                    "RBA: not enough "
                    "10Y observations"
                )

            latest = observations[-1]
            previous = observations[-2]

            return make_observation(
                latest[0],
                latest[1],
                previous[0],
                previous[1]
            )

        except Exception as exc:

            last_error = exc

    raise RuntimeError(
        f"RBA failed: {last_error}"
    )


# ============================================================
# COUNTRY CONFIG
#
# ALL EXISTING SLUGS KEPT.
# ============================================================

COUNTRIES = {

    "united_states": {
        "label":
            "United States",

        "primary":
            "fred",

        "fred":
            "DGS10",

        "fred_frequency":
            "Daily"
    },


    "euro_area": {
        "label":
            "Euro Area",

        "primary":
            "ecb"
    },


    "united_kingdom": {
        "label":
            "United Kingdom",

        "primary":
            "riksbank",

        "fred":
            "IRLTLT01GBM156N"
    },


    "canada": {
        "label":
            "Canada",

        "primary":
            "boc",

        "fred":
            "IRLTLT01CAM156N"
    },


    "australia": {
        "label":
            "Australia",

        "primary":
            "rba",

        "fred":
            "IRLTLT01AUM156N"
    },


    "sweden": {
        "label":
            "Sweden",

        "primary":
            "riksbank_sweden",

        "riksbank":
            "SEGVB10YC",

        "fred":
            "IRLTLT01SEM156N"
    },


    "germany": {
        "label":
            "Germany",

        "primary":
            "riksbank",

        "fred":
            "IRLTLT01DEM156N"
    },


    "france": {
        "label":
            "France",

        "primary":
            "riksbank",

        "fred":
            "IRLTLT01FRM156N"
    },


    "italy": {
        "label":
            "Italy",

        "primary":
            "fred",

        "fred":
            "IRLTLT01ITM156N"
    },


    "spain": {
        "label":
            "Spain",

        "primary":
            "fred",

        "fred":
            "IRLTLT01ESM156N"
    },


    "netherlands": {
        "label":
            "Netherlands",

        "primary":
            "riksbank",

        "fred":
            "IRLTLT01NLM156N"
    },


    "switzerland": {
        "label":
            "Switzerland",

        "primary":
            "fred",

        "fred":
            "IRLTLT01CHM156N"
    },


    "sweden_fred": {
        "label":
            "Sweden (OECD)",

        "primary":
            "fred",

        "fred":
            "IRLTLT01SEM156N"
    },


    "belgium": {
        "label":"Belgium",
        "primary":"fred",
        "fred":"IRLTLT01BEM156N"
    },


    "austria": {
        "label":"Austria",
        "primary":"fred",
        "fred":"IRLTLT01ATM156N"
    },


    "portugal": {
        "label":"Portugal",
        "primary":"fred",
        "fred":"IRLTLT01PTM156N"
    },


    "finland": {
        "label":
            "Finland",

        "primary":
            "riksbank",

        "fred":
            "IRLTLT01FIM156N"
    },


    "ireland": {
        "label":"Ireland",
        "primary":"fred",
        "fred":"IRLTLT01IEM156N"
    },


    "denmark": {
        "label":
            "Denmark",

        "primary":
            "riksbank",

        "fred":
            "IRLTLT01DKM156N"
    },


    "norway": {
        "label":
            "Norway",

        "primary":
            "riksbank",

        "fred":
            "IRLTLT01NOM156N"
    },


    "india": {
        "label":"India",
        "primary":"fred",
        "fred":"INDIRLTLT01STM"
    },


    "south_korea": {
        "label":"South Korea",
        "primary":"fred",
        "fred":"IRLTLT01KRM156N"
    },


    "new_zealand": {
        "label":"New Zealand",
        "primary":"fred",
        "fred":"IRLTLT01NZM156N"
    },


    "greece": {
        "label":"Greece",
        "primary":"fred",
        "fred":"IRLTLT01GRM156N"
    },


    "israel": {
        "label":"Israel",
        "primary":"fred",
        "fred":"IRLTLT01ILM156N"
    },


    "mexico": {
        "label":"Mexico",
        "primary":"fred",
        "fred":"IRLTLT01MXM156N"
    },


    "poland": {
        "label":"Poland",
        "primary":"fred",
        "fred":"IRLTLT01PLM156N"
    },


    "czech_republic": {
        "label":"Czech Republic",
        "primary":"fred",
        "fred":"IRLTLT01CZM156N"
    },


    "hungary": {
        "label":"Hungary",
        "primary":"fred",
        "fred":"IRLTLT01HUM156N"
    },


    "slovakia": {
        "label":"Slovakia",
        "primary":"fred",
        "fred":"IRLTLT01SKM156N"
    },


    "slovenia": {
        "label":"Slovenia",
        "primary":"fred",
        "fred":"IRLTLT01SIM156N"
    },


    "lithuania": {
        "label":"Lithuania",
        "primary":"fred",
        "fred":"LTUIRLTLT01STM"
    },


    "chile": {
        "label":"Chile",
        "primary":"fred",
        "fred":"IRLTLT01CLM156N"
    },


    "south_africa": {
        "label":"South Africa",
        "primary":"fred",
        "fred":"IRLTLT01ZAM156N"
    }
}


# ============================================================
# BUILD FROM RIKSBANK LATEST + PREVIOUS STORED OBSERVATION
#
# We deliberately preserve the prior stored observation
# rather than inventing a previous quote.
# ============================================================

def from_riksbank_latest(
    slug,
    latest,
    old
):

    if slug not in latest:
        raise RuntimeError(
            "Riksbank series missing"
        )

    current = latest[slug]

    if (
        not current.get("date")
        or
        not valid_yield(
            current.get("value")
        )
    ):
        raise RuntimeError(
            "Riksbank result invalid"
        )

    if not is_current(current):
        raise RuntimeError(
            "Riksbank result stale"
        )

    previous_date = old.get(
        "date"
    )

    previous_value = old.get(
        "value"
    )

    # If old data were monthly, change is not
    # a true one-day move. We therefore avoid
    # fabricating a daily move and set previous
    # to current on the first migration.
    if (
        not previous_date
        or
        not valid_yield(previous_value)
        or
        old.get("frequency")
        != "Daily"
    ):

        previous_date = (
            current["date"]
        )

        previous_value = (
            current["value"]
        )

    return make_observation(

        current["date"],
        current["value"],

        previous_date,
        previous_value
    )


# ============================================================
# ROUTER
# ============================================================

def get_country(
    slug,
    config,
    old_country,
    riksbank_group
):

    primary = config[
        "primary"
    ]


    # ---------------------------
    # USA
    # ---------------------------

    if primary == "fred":

        observation = fetch_fred(
            config["fred"]
        )

        frequency = config.get(
            "fred_frequency",
            "Monthly"
        )

        return (
            observation,
            "fred",
            frequency,
            False
        )


    # ---------------------------
    # ECB
    # ---------------------------

    if primary == "ecb":

        try:

            observation = fetch_ecb()

            if is_current(
                observation
            ):

                return (
                    observation,
                    "ecb",
                    "Daily",
                    False
                )

        except Exception as exc:

            print(
                slug,
                "ECB failed:",
                exc
            )


    # ---------------------------
    # RIKSBANK GROUP
    # ---------------------------

    if primary == "riksbank":

        try:

            observation = (
                from_riksbank_latest(
                    slug,
                    riksbank_group,
                    old_country
                )
            )

            return (
                observation,
                "riksbank",
                "Daily",
                False
            )

        except Exception as exc:

            print(
                slug,
                "Riksbank failed:",
                exc
            )


    # ---------------------------
    # SWEDEN
    # ---------------------------

    if (
        primary ==
        "riksbank_sweden"
    ):

        try:

            latest = (
                fetch_riksbank_latest(
                    config[
                        "riksbank"
                    ]
                )
            )

            if not is_current(
                latest
            ):

                raise RuntimeError(
                    "Swedish rate stale"
                )

            previous_date = (
                old_country.get(
                    "date"
                )
            )

            previous_value = (
                old_country.get(
                    "value"
                )
            )

            if (
                old_country.get(
                    "frequency"
                )
                != "Daily"
                or
                not previous_date
                or
                not valid_yield(
                    previous_value
                )
            ):

                previous_date = (
                    latest["date"]
                )

                previous_value = (
                    latest["value"]
                )

            observation = (
                make_observation(
                    latest["date"],
                    latest["value"],
                    previous_date,
                    previous_value
                )
            )

            return (
                observation,
                "riksbank",
                "Daily",
                False
            )

        except Exception as exc:

            print(
                "Sweden Riksbank "
                "failed:",
                exc
            )


    # ---------------------------
    # CANADA
    # ---------------------------

    if primary == "boc":

        try:

            observation = fetch_boc()

            if is_current(
                observation
            ):

                return (
                    observation,
                    "boc",
                    "Daily",
                    False
                )

        except Exception as exc:

            print(
                "Canada BoC failed:",
                exc
            )


    # ---------------------------
    # AUSTRALIA
    # ---------------------------

    if primary == "rba":

        try:

            observation = fetch_rba()

            if is_current(
                observation
            ):

                return (
                    observation,
                    "rba",
                    "Daily",
                    False
                )

        except Exception as exc:

            print(
                "Australia RBA failed:",
                exc
            )


    # ========================================================
    # FRED FALLBACK
    # ========================================================

    fred_series = config.get(
        "fred"
    )

    if fred_series:

        observation = fetch_fred(
            fred_series
        )

        return (
            observation,
            "fred",
            "Monthly",
            True
        )


    raise RuntimeError(
        "No usable source"
    )


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


    # ========================================================
    # ONE RIKSBANK REQUEST FOR 8 COUNTRIES
    # ========================================================

    try:

        riksbank_group = (
            fetch_riksbank_group()
        )

        print(
            "Riksbank group 100:",
            len(
                riksbank_group
            ),
            "matching series"
        )

    except Exception as exc:

        print(
            "Riksbank group request "
            "failed:",
            exc
        )

        riksbank_group = {}


    # ========================================================
    # COUNTRIES
    # ========================================================

    for slug, config in COUNTRIES.items():

        label = config["label"]

        old_country = (
            old_countries.get(
                slug,
                {}
            )
        )

        print(
            "\n--------------------------"
        )

        print(
            "Updating",
            label
        )

        try:

            (
                observation,
                source,
                frequency,
                is_fallback
            ) = get_country(

                slug,
                config,
                old_country,
                riksbank_group
            )


            country = {

                "label":
                    label,

                "source":
                    source,

                "frequency":
                    frequency,

                "date":
                    observation[
                        "date"
                    ],

                "value":
                    observation[
                        "value"
                    ],

                "previousDate":
                    observation[
                        "previousDate"
                    ],

                "previousValue":
                    observation[
                        "previousValue"
                    ],

                "change":
                    observation[
                        "change"
                    ],

                "stalenessDays":
                    days_old(
                        observation[
                            "date"
                        ]
                    ),

                "tier":
                    tier_for(
                        observation[
                            "date"
                        ],
                        frequency
                    ),

                "isFallback":
                    is_fallback
            }


            countries[
                slug
            ] = country


            print(
                label,
                "→",
                source,
                observation[
                    "date"
                ],
                observation[
                    "value"
                ]
            )


        except Exception as exc:

            print(
                label,
                "FAILED:",
                exc
            )

            errors[slug] = str(
                exc
            )


            # =================================================
            # ABSOLUTE FAIL-SAFE
            #
            # Never remove an existing market
            # because one external API failed.
            # =================================================

            if old_country:

                countries[
                    slug
                ] = old_country

                print(
                    "Preserved last "
                    "known good value."
                )


    # ========================================================
    # HARD VALIDATION
    # ========================================================

    if not countries:

        raise RuntimeError(
            "No market data generated. "
            "Live JSON was not touched."
        )


    for required in (
        "united_states",
        "euro_area"
    ):

        if required not in countries:

            raise RuntimeError(
                f"Critical market missing: "
                f"{required}. "
                "Live JSON was not touched."
            )


    # Do not accidentally publish
    # a drastically truncated file.

    old_count = len(
        old_countries
    )

    new_count = len(
        countries
    )

    if (
        old_count
        and
        new_count
        <
        old_count * 0.90
    ):

        raise RuntimeError(
            "Too many countries missing. "
            "Live JSON was not touched."
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

    with open(
        TEMP_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False
        )


    # Validate the completed file
    # before replacing production.

    with open(
        TEMP_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        json.load(file)


    os.replace(
        TEMP_FILE,
        OUTPUT_FILE
    )


    # ========================================================
    # REPORT
    # ========================================================

    daily = []

    delayed = []

    monthly = []


    for slug, country in (
        countries.items()
    ):

        tier = country.get(
            "tier"
        )

        if tier == "daily":
            daily.append(slug)

        elif tier == "delayed":
            delayed.append(slug)

        else:
            monthly.append(slug)


    print(
        "\n=========================="
    )

    print(
        "BondStats update complete"
    )

    print(
        "Countries:",
        len(countries)
    )

    print(
        "Daily:",
        len(daily)
    )

    print(
        "Delayed:",
        len(delayed)
    )

    print(
        "Monthly:",
        len(monthly)
    )

    print(
        "Errors:",
        len(errors)
    )

    print(
        "\nDaily:",
        ", ".join(daily)
    )

    print(
        "\nDelayed:",
        ", ".join(delayed)
    )

    print(
        "\nStill monthly:",
        ", ".join(monthly)
    )


if __name__ == "__main__":
    main()
