import csv
import html
import io
import json
import os
import re

from datetime import datetime, timezone
from html.parser import HTMLParser
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

TIMEOUT = 20

# Daily sources are accepted as fresh
# through weekends / normal publication lags.
FRESHNESS_MAX_DAYS = 7


# ============================================================
# HTTP
# ============================================================

def fetch_bytes(url, accept=None):

    headers = {
        "User-Agent":
            "BondStats Global Yields/2.0"
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


def fetch_text(
    url,
    accept=None
):

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
            continue

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
# DATES
# ============================================================

def parse_date(value):

    if not value:
        return None

    value = str(value).strip()

    formats = (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%d-%m-%Y",
        "%d %b %Y",
        "%d %B %Y",
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

    now = (
        datetime.now(timezone.utc)
        .replace(tzinfo=None)
    )

    return max(
        0,
        (now - d).days
    )


def is_fresh(date_str):

    return (
        staleness_days(date_str)
        <=
        FRESHNESS_MAX_DAYS
    )


def calc_tier(days, freq):

    if freq == "Monthly":
        return "monthly"

    if days <= 1:
        return "daily"

    if days <= 7:
        return "delayed"

    return "monthly"


def r(value):

    return (
        round(value, 4)
        if value is not None
        else None
    )


# ============================================================
# RESULT HELPER
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

    if (
        not latest_date
        or
        not previous_date
    ):
        raise RuntimeError(
            "Invalid observation date."
        )

    latest_value = float(
        latest_value
    )

    previous_value = float(
        previous_value
    )

    # Basic sanity validation for sovereign yields.
    if not (
        -10.0
        <
        latest_value
        <
        100.0
    ):
        raise RuntimeError(
            "Yield failed sanity check."
        )

    if not (
        -10.0
        <
        previous_value
        <
        100.0
    ):
        raise RuntimeError(
            "Previous yield failed sanity check."
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


# ============================================================
# SERIES
#
# Existing slugs are intentionally preserved.
# Do not rename them.
# ============================================================

SERIES = {

    "united_states": {
        "label":
            "United States",

        "series_id":
            "DGS10",

        "primary_source":
            "fred",

        "frequency_hint":
            "Daily"
    },


    "euro_area": {
        "label":
            "Euro Area",

        "primary_source":
            "ecb"
    },


    "united_kingdom": {
        "label":
            "United Kingdom",

        "primary_source":
            "boe",

        "fallback_series_id":
            "IRLTLT01GBM156N"
    },


    "canada": {
        "label":
            "Canada",

        "primary_source":
            "boc",

        "series_id":
            "V39055",

        "fallback_series_id":
            "IRLTLT01CAM156N"
    },


    "australia": {
        "label":
            "Australia",

        "primary_source":
            "rba",

        "fallback_series_id":
            "IRLTLT01AUM156N"
    },


    "sweden": {
        "label":
            "Sweden",

        "primary_source":
            "riksbank",

        "series_id":
            "SEK_GOVT_BOND_10Y",

        "fallback_series_id":
            "IRLTLT01SEM156N"
    },


    # --------------------------------------------------------
    # NEW DAILY PRIMARY SOURCES
    # --------------------------------------------------------

    "germany": {
        "label":
            "Germany",

        "primary_source":
            "bundesbank",

        "fallback_series_id":
            "IRLTLT01DEM156N"
    },


    "switzerland": {
        "label":
            "Switzerland",

        "primary_source":
            "snb",

        "fallback_series_id":
            "IRLTLT01CHM156N"
    },


    "norway": {
        "label":
            "Norway",

        "primary_source":
            "norges",

        "fallback_series_id":
            "IRLTLT01NOM156N"
    },


    "new_zealand": {
        "label":
            "New Zealand",

        "primary_source":
            "rbnz",

        "fallback_series_id":
            "IRLTLT01NZM156N"
    },


    # --------------------------------------------------------
    # EXISTING FRED SERIES — UNCHANGED
    # --------------------------------------------------------

    "france": {
        "label":"France",
        "series_id":"IRLTLT01FRM156N",
        "primary_source":"fred"
    },

    "italy": {
        "label":"Italy",
        "series_id":"IRLTLT01ITM156N",
        "primary_source":"fred"
    },

    "spain": {
        "label":"Spain",
        "series_id":"IRLTLT01ESM156N",
        "primary_source":"fred"
    },

    "netherlands": {
        "label":"Netherlands",
        "series_id":"IRLTLT01NLM156N",
        "primary_source":"fred"
    },

    # Keep this legacy key because an existing
    # frontend may still reference it.
    "sweden_fred": {
        "label":"Sweden (OECD)",
        "series_id":"IRLTLT01SEM156N",
        "primary_source":"fred"
    },

    "belgium": {
        "label":"Belgium",
        "series_id":"IRLTLT01BEM156N",
        "primary_source":"fred"
    },

    "austria": {
        "label":"Austria",
        "series_id":"IRLTLT01ATM156N",
        "primary_source":"fred"
    },

    "portugal": {
        "label":"Portugal",
        "series_id":"IRLTLT01PTM156N",
        "primary_source":"fred"
    },

    "finland": {
        "label":"Finland",
        "series_id":"IRLTLT01FIM156N",
        "primary_source":"fred"
    },

    "ireland": {
        "label":"Ireland",
        "series_id":"IRLTLT01IEM156N",
        "primary_source":"fred"
    },

    "denmark": {
        "label":"Denmark",
        "series_id":"IRLTLT01DKM156N",
        "primary_source":"fred"
    },

    "india": {
        "label":"India",
        "series_id":"INDIRLTLT01STM",
        "primary_source":"fred"
    },

    "south_korea": {
        "label":"South Korea",
        "series_id":"IRLTLT01KRM156N",
        "primary_source":"fred"
    },

    "greece": {
        "label":"Greece",
        "series_id":"IRLTLT01GRM156N",
        "primary_source":"fred"
    },

    "israel": {
        "label":"Israel",
        "series_id":"IRLTLT01ILM156N",
        "primary_source":"fred"
    },

    "mexico": {
        "label":"Mexico",
        "series_id":"IRLTLT01MXM156N",
        "primary_source":"fred"
    },

    "poland": {
        "label":"Poland",
        "series_id":"IRLTLT01PLM156N",
        "primary_source":"fred"
    },

    "czech_republic": {
        "label":"Czech Republic",
        "series_id":"IRLTLT01CZM156N",
        "primary_source":"fred"
    },

    "hungary": {
        "label":"Hungary",
        "series_id":"IRLTLT01HUM156N",
        "primary_source":"fred"
    },

    "slovakia": {
        "label":"Slovakia",
        "series_id":"IRLTLT01SKM156N",
        "primary_source":"fred"
    },

    "slovenia": {
        "label":"Slovenia",
        "series_id":"IRLTLT01SIM156N",
        "primary_source":"fred"
    },

    "lithuania": {
        "label":"Lithuania",
        "series_id":"LTUIRLTLT01STM",
        "primary_source":"fred"
    },

    "chile": {
        "label":"Chile",
        "series_id":"IRLTLT01CLM156N",
        "primary_source":"fred"
    },

    "south_africa": {
        "label":"South Africa",
        "series_id":"IRLTLT01ZAM156N",
        "primary_source":"fred"
    }
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
        for item
        in data.get(
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
            f"FRED returned insufficient "
            f"data for {series_id}."
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
# ECB — EXISTING LOGIC PRESERVED
# ============================================================

def fetch_ecb():

    url = (
        "https://data-api.ecb.europa.eu/"
        "service/data/YC/"
        "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y"
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
        series["observations"]
    )

    keys = sorted(
        observations.keys(),
        key=lambda value:
            int(value)
    )

    times = (
        data["structure"]
        ["dimensions"]
        ["observation"][0]
        ["values"]
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
# BANK OF ENGLAND
#
# Existing approach is retained. Direct request first,
# proxy only as secondary attempt.
# ============================================================

def parse_boe_csv(raw):

    parsed = []

    for line in raw.splitlines():

        if "/" not in line:
            continue

        parts = [
            part
            .strip()
            .replace('"', '')
            for part
            in line.split(",")
        ]

        if len(parts) < 2:
            continue

        date = parse_date(
            parts[0]
        )

        if not date:
            continue

        try:
            value = float(
                parts[1]
            )
        except ValueError:
            continue

        parsed.append(
            (
                date.strftime(
                    "%Y-%m-%d"
                ),
                value
            )
        )

    parsed.sort(
        key=lambda item:
            item[0]
    )

    if len(parsed) < 2:
        raise RuntimeError(
            "Bank of England CSV "
            "contained insufficient data."
        )

    latest = parsed[-1]
    previous = parsed[-2]

    return make_result(
        latest[0],
        latest[1],
        previous[0],
        previous[1]
    )


def fetch_boe():

    official = (
        "https://www.bankofengland.co.uk/"
        "boeapps/database/"
        "FromShowColumns.asp?"
        "csv.x=yes&SeriesCodes=IUMAJNB"
    )

    try:
        return parse_boe_csv(
            fetch_text(official)
        )

    except Exception as direct_error:

        print(
            "BoE direct request failed:",
            direct_error
        )

    proxy = (
        "https://api.allorigins.win/raw?"
        "url="
        +
        official
    )

    try:
        return parse_boe_csv(
            fetch_text(proxy)
        )

    except Exception as proxy_error:

        print(
            "BoE proxy request failed:",
            proxy_error
        )

    return None


# ============================================================
# BANK OF CANADA
#
# IMPORTANT FIX:
# The old endpoint in your script was malformed.
#
# Official series:
# V39055 = 10-year Government of Canada benchmark.
# ============================================================

def fetch_boc(series_id):

    try:

        url = (
            "https://www.bankofcanada.ca/"
            f"valet/observations/{series_id}/json"
            "?recent=10"
        )

        data = fetch_json(url)

        parsed = []

        for observation in data.get(
            "observations",
            []
        ):

            date = observation.get("d")

            series = observation.get(
                series_id
            )

            if not series:
                continue

            value = series.get("v")

            if (
                date
                and
                value not in (
                    None,
                    ""
                )
            ):

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

    except Exception as error:

        print(
            "BoC error:",
            error
        )

        return None


# ============================================================
# RBA
#
# Uses official daily F2.1 CSV rather than the old
# non-working JSON endpoint.
# ============================================================

def fetch_rba():

    try:

        url = (
            "https://www.rba.gov.au/"
            "statistics/tables/csv/"
            "f2.1-data.csv"
        )

        raw = fetch_text(url)

        rows = list(
            csv.reader(
                io.StringIO(raw)
            )
        )

        if not rows:

            raise RuntimeError(
                "RBA CSV was empty."
            )

        ten_year_column = None

        # Metadata/header rows identify
        # the 10-year government bond column.
        for row in rows[:20]:

            for index, cell in enumerate(row):

                normalized = (
                    cell
                    .lower()
                    .replace("-", " ")
                )

                if (
                    "10 year"
                    in normalized
                    and
                    "bond"
                    in normalized
                ):

                    ten_year_column = index
                    break

            if ten_year_column is not None:
                break


        if ten_year_column is None:

            raise RuntimeError(
                "Could not identify RBA "
                "10-year column."
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
                row[0].strip()
            )

            if not date:
                continue

            raw_value = (
                row[
                    ten_year_column
                ]
                .strip()
            )

            if raw_value in (
                "",
                "-",
                "na",
                "NA"
            ):
                continue

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
                "10-year observations."
            )


        latest = observations[-1]
        previous = observations[-2]


        return make_result(
            latest[0],
            latest[1],
            previous[0],
            previous[1]
        )


    except Exception as error:

        print(
            "RBA error:",
            error
        )

        return None


# ============================================================
# RIKSBANK
#
# Existing source retained; parser made tolerant
# of different API wrappers.
# ============================================================

def fetch_riksbank(
    series_id
):

    urls = [

        (
            "https://api.riksbank.se/"
            "swea/v1/Observations/"
            f"{series_id}"
        ),

        (
            "https://api.riksbank.se/"
            "swea/v1/Observations/"
            "Latest/"
            f"{series_id}"
        )
    ]


    for url in urls:

        try:

            data = fetch_json(url)

            if isinstance(
                data,
                dict
            ):

                observations = (
                    data.get(
                        "observations"
                    )
                    or
                    data.get(
                        "value"
                    )
                    or
                    []
                )

            elif isinstance(
                data,
                list
            ):

                observations = data

            else:

                observations = []


            parsed = []


            for item in observations:

                date = (
                    item.get("date")
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
                    item.get(
                        "observationValue"
                    )
                )


                if (
                    date
                    and
                    value not in (
                        None,
                        ""
                    )
                ):

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
                for item
                in parsed
                if item[0]
            ]


            parsed.sort(
                key=lambda item:
                    item[0]
            )


            if len(parsed) >= 2:

                latest = parsed[-1]
                previous = parsed[-2]

                return make_result(
                    latest[0],
                    latest[1],
                    previous[0],
                    previous[1]
                )


        except Exception as error:

            print(
                "Riksbank attempt failed:",
                error
            )


    return None


# ============================================================
# BUNDESBANK
#
# Official daily 10-year current federal bond:
#
# BBSSY.D.REN.EUR.A630.000000WT1010.A
# ============================================================

def fetch_bundesbank():

    url = (
        "https://api.statistiken.bundesbank.de/"
        "rest/data/BBSSY/"
        "D.REN.EUR.A630.000000WT1010.A"
        "?format=csv&lang=en"
    )

    try:

        raw = fetch_text(
            url,
            "application/vnd.bbk.data+csv"
        )

        # Bundesbank CSV can use semicolon
        # depending on representation.
        try:

            dialect = (
                csv.Sniffer()
                .sniff(
                    raw[:5000],
                    delimiters=";,|\t,"
                )
            )

        except csv.Error:

            dialect = csv.excel


        rows = list(
            csv.reader(
                io.StringIO(raw),
                dialect
            )
        )


        observations = []


        for row in rows:

            if len(row) < 2:
                continue


            date = None
            value = None


            for cell in row:

                cell = cell.strip()

                if date is None:

                    d = parse_date(cell)

                    if d:
                        date = d


            if date is None:
                continue


            # Search from right to left for
            # the observation value.
            for cell in reversed(row):

                cleaned = (
                    cell
                    .strip()
                    .replace(",", ".")
                )

                try:
                    candidate = float(
                        cleaned
                    )
                except ValueError:
                    continue


                if (
                    -10.0
                    <
                    candidate
                    <
                    100.0
                ):

                    value = candidate
                    break


            if value is not None:

                observations.append(
                    (
                        date.strftime(
                            "%Y-%m-%d"
                        ),
                        value
                    )
                )


        # Remove duplicate dates.
        by_date = {
            date: value
            for date, value
            in observations
        }


        observations = sorted(
            by_date.items(),
            key=lambda item:
                item[0]
        )


        if len(observations) < 2:

            raise RuntimeError(
                "Bundesbank returned "
                "insufficient observations."
            )


        latest = observations[-1]
        previous = observations[-2]


        return make_result(
            latest[0],
            latest[1],
            previous[0],
            previous[1]
        )


    except Exception as error:

        print(
            "Bundesbank error:",
            error
        )

        return None


# ============================================================
# SNB
#
# Official SNB data portal.
#
# We attempt the official source first.
# If its page structure changes, FRED remains
# the automatic fallback.
# ============================================================

def strip_html(raw):

    raw = re.sub(
        r"<script.*?</script>",
        " ",
        raw,
        flags=re.I | re.S
    )

    raw = re.sub(
        r"<style.*?</style>",
        " ",
        raw,
        flags=re.I | re.S
    )

    raw = re.sub(
        r"<[^>]+>",
        " ",
        raw
    )

    raw = html.unescape(raw)

    return re.sub(
        r"\s+",
        " ",
        raw
    )


def fetch_snb():

    url = (
        "https://data.snb.ch/en/"
        "topics/ziredev/cube/rendoblid"
    )

    try:

        raw = fetch_text(url)

        text = strip_html(raw)


        # SNB's portal exposes the
        # 10-year Confederation bond
        # time series in the page data.

        patterns = [

            (
                r"10 years.{0,250}?"
                r"(-?\d+(?:\.\d+)?)\s*%?"
                r".{0,120}?"
                r"(20\d{2}-\d{2}-\d{2})"
            ),

            (
                r"Yield on Swiss Confederation bonds,"
                r"\s*10 years.{0,120}?"
                r"(-?\d+(?:\.\d+)?)\s*%?"
                r".{0,100}?"
                r"(20\d{2}-\d{2}-\d{2})"
            )
        ]


        matches = []


        for pattern in patterns:

            for match in re.finditer(
                pattern,
                text,
                flags=re.I
            ):

                value = float(
                    match.group(1)
                )

                date = match.group(2)

                matches.append(
                    (
                        date,
                        value
                    )
                )


        matches = sorted(
            set(matches),
            key=lambda item:
                item[0]
        )


        if len(matches) >= 2:

            latest = matches[-1]
            previous = matches[-2]

            return make_result(
                latest[0],
                latest[1],
                previous[0],
                previous[1]
            )


        raise RuntimeError(
            "SNB page parser did not "
            "find two observations."
        )


    except Exception as error:

        print(
            "SNB error:",
            error
        )

        return None


# ============================================================
# NORGES BANK
#
# Official zero-coupon government yield data.
# Daily publication.
# ============================================================

def fetch_norges():

    url = (
        "https://data.norges-bank.no/"
        "api/data/GOVT_ZEROCOUPON/B"
        "?bom=include"
        "&format=csv"
        "&locale=en"
        "&startPeriod=2025"
    )


    try:

        raw = fetch_text(
            url,
            "text/csv"
        )


        # Determine delimiter.
        try:

            dialect = (
                csv.Sniffer()
                .sniff(
                    raw[:5000],
                    delimiters=";,|\t,"
                )
            )

        except csv.Error:

            dialect = csv.excel


        reader = csv.DictReader(
            io.StringIO(raw),
            dialect=dialect
        )


        observations = []


        for row in reader:

            normalized = {
                str(key).strip():
                    str(value).strip()
                for key, value
                in row.items()
                if key is not None
            }


            date = None
            value = None
            maturity_10y = False


            for key, cell in normalized.items():

                key_lower = key.lower()
                cell_lower = cell.lower()


                if (
                    "time_period"
                    in key_lower
                    or
                    key_lower
                    in (
                        "date",
                        "time"
                    )
                ):

                    if parse_date(cell):

                        date = (
                            parse_date(cell)
                            .strftime(
                                "%Y-%m-%d"
                            )
                        )


                combined = (
                    key_lower
                    +
                    " "
                    +
                    cell_lower
                )


                if (
                    "10 year"
                    in combined
                    or
                    "10-year"
                    in combined
                    or
                    "10y"
                    in combined
                    or
                    cell_lower
                    in (
                        "10",
                        "10.0"
                    )
                ):

                    maturity_10y = True


                if (
                    "obs_value"
                    in key_lower
                    or
                    key_lower
                    in (
                        "value",
                        "obs value"
                    )
                ):

                    try:
                        value = float(cell)
                    except ValueError:
                        pass


            if (
                date
                and
                value is not None
                and
                maturity_10y
            ):

                observations.append(
                    (
                        date,
                        value
                    )
                )


        observations.sort(
            key=lambda item:
                item[0]
        )


        if len(observations) < 2:

            raise RuntimeError(
                "Norges Bank parser did not "
                "identify two 10-year observations."
            )


        latest = observations[-1]
        previous = observations[-2]


        return make_result(
            latest[0],
            latest[1],
            previous[0],
            previous[1]
        )


    except Exception as error:

        print(
            "Norges Bank error:",
            error
        )

        return None


# ============================================================
# RBNZ
#
# Official Wholesale Interest Rates B2 page.
# Daily benchmark 10-year government yield.
# ============================================================

class TableParser(
    HTMLParser
):

    def __init__(self):

        super().__init__()

        self.rows = []
        self.current_row = None
        self.current_cell = None


    def handle_starttag(
        self,
        tag,
        attrs
    ):

        if tag == "tr":
            self.current_row = []

        elif (
            tag in (
                "td",
                "th"
            )
            and
            self.current_row
            is not None
        ):

            self.current_cell = ""


    def handle_data(
        self,
        data
    ):

        if self.current_cell is not None:

            self.current_cell += data


    def handle_endtag(
        self,
        tag
    ):

        if (
            tag in (
                "td",
                "th"
            )
            and
            self.current_cell
            is not None
            and
            self.current_row
            is not None
        ):

            self.current_row.append(
                re.sub(
                    r"\s+",
                    " ",
                    self.current_cell
                ).strip()
            )

            self.current_cell = None


        elif (
            tag == "tr"
            and
            self.current_row
            is not None
        ):

            if self.current_row:
                self.rows.append(
                    self.current_row
                )

            self.current_row = None


def fetch_rbnz():

    url = (
        "https://www.rbnz.govt.nz/"
        "statistics/series/"
        "exchange-and-interest-rates/"
        "wholesale-interest-rates"
    )


    try:

        raw = fetch_text(url)

        parser = TableParser()

        parser.feed(raw)


        observations = []


        for row in parser.rows:

            if not row:
                continue


            date = parse_date(
                row[0]
            )


            if not date:
                continue


            # Current B2 table layout:
            #
            # 0 Date
            # 1 OCR
            # 2 Overnight deposit
            # 3 reverse repo
            # 4 cash rate
            # 5 30d
            # 6 60d
            # 7 90d
            # 8 1Y govt
            # 9 2Y govt
            # 10 5Y govt
            # 11 10Y govt

            if len(row) <= 11:
                continue


            raw_value = (
                row[11]
                .replace("%", "")
                .strip()
            )


            if raw_value in (
                "",
                "-",
                "—"
            ):
                continue


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
                "RBNZ page did not provide "
                "two valid 10-year observations."
            )


        latest = observations[-1]
        previous = observations[-2]


        return make_result(
            latest[0],
            latest[1],
            previous[0],
            previous[1]
        )


    except Exception as error:

        print(
            "RBNZ error:",
            error
        )

        return None


# ============================================================
# ROUTER
#
# Primary source first.
# FRED fallback second.
# ============================================================

def fetch_data(info):

    primary = info[
        "primary_source"
    ]


    # --------------------------------------------------------
    # FRED
    # --------------------------------------------------------

    if primary == "fred":

        return (
            fetch_fred(
                info["series_id"]
            ),
            "fred",
            info.get(
                "frequency_hint",
                "Monthly"
            ),
            False
        )


    # --------------------------------------------------------
    # ECB
    # --------------------------------------------------------

    if primary == "ecb":

        d = fetch_ecb()

        if (
            d
            and
            is_fresh(d["date"])
        ):

            return (
                d,
                "ecb",
                "Daily",
                False
            )


    # --------------------------------------------------------
    # BOE
    # --------------------------------------------------------

    elif primary == "boe":

        d = fetch_boe()

        if (
            d
            and
            is_fresh(d["date"])
        ):

            return (
                d,
                "boe",
                "Daily",
                False
            )


    # --------------------------------------------------------
    # BOC
    # --------------------------------------------------------

    elif primary == "boc":

        d = fetch_boc(
            info["series_id"]
        )

        if (
            d
            and
            is_fresh(d["date"])
        ):

            return (
                d,
                "boc",
                "Daily",
                False
            )


    # --------------------------------------------------------
    # RBA
    # --------------------------------------------------------

    elif primary == "rba":

        d = fetch_rba()

        if (
            d
            and
            is_fresh(d["date"])
        ):

            return (
                d,
                "rba",
                "Daily",
                False
            )


    # --------------------------------------------------------
    # RIKSBANK
    # --------------------------------------------------------

    elif primary == "riksbank":

        d = fetch_riksbank(
            info["series_id"]
        )

        if (
            d
            and
            is_fresh(d["date"])
        ):

            return (
                d,
                "riksbank",
                "Daily",
                False
            )


    # --------------------------------------------------------
    # BUNDESBANK
    # --------------------------------------------------------

    elif primary == "bundesbank":

        d = fetch_bundesbank()

        if (
            d
            and
            is_fresh(d["date"])
        ):

            return (
                d,
                "bundesbank",
                "Daily",
                False
            )


    # --------------------------------------------------------
    # SNB
    # --------------------------------------------------------

    elif primary == "snb":

        d = fetch_snb()

        if (
            d
            and
            is_fresh(d["date"])
        ):

            return (
                d,
                "snb",
                "Daily",
                False
            )


    # --------------------------------------------------------
    # NORGES BANK
    # --------------------------------------------------------

    elif primary == "norges":

        d = fetch_norges()

        if (
            d
            and
            is_fresh(d["date"])
        ):

            return (
                d,
                "norges",
                "Daily",
                False
            )


    # --------------------------------------------------------
    # RBNZ
    # --------------------------------------------------------

    elif primary == "rbnz":

        d = fetch_rbnz()

        if (
            d
            and
            is_fresh(d["date"])
        ):

            return (
                d,
                "rbnz",
                "Daily",
                False
            )


    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    fallback = info.get(
        "fallback_series_id"
    )


    if fallback:

        print(
            f"Primary source {primary} "
            "unavailable/stale → "
            "using FRED fallback."
        )

        return (
            fetch_fred(
                fallback
            ),
            "fred",
            "Monthly",
            True
        )


    raise RuntimeError(
        "All sources failed."
    )


# ============================================================
# LAST-KNOWN-GOOD PROTECTION
#
# This is the critical safety layer.
# If an API and its fallback both fail,
# the existing country object is retained.
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
            "Could not read existing JSON:",
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

    existing_countries = (
        existing.get(
            "countries",
            {}
        )
    )

    countries = {}

    errors = {}


    for slug, info in SERIES.items():

        print(
            "\n=============================="
        )

        print(
            f"Updating {info['label']}"
        )

        try:

            obs, source, freq, is_fb = (
                fetch_data(info)
            )


            stale = staleness_days(
                obs["date"]
            )


            tier = calc_tier(
                stale,
                freq
            )


            countries[slug] = {

                "label":
                    info["label"],

                "source":
                    source,

                "frequency":
                    freq,

                "date":
                    obs["date"],

                "value":
                    obs["value"],

                "previousDate":
                    obs["previousDate"],

                "previousValue":
                    obs["previousValue"],

                "change":
                    obs["change"],

                "stalenessDays":
                    stale,

                "tier":
                    tier,

                "isFallback":
                    is_fb
            }


            print(
                f"{info['label']} → "
                f"{source} | "
                f"{obs['date']} | "
                f"{tier} | "
                f"fallback={is_fb}"
            )


        except Exception as error:

            errors[slug] = str(
                error
            )


            print(
                f"ERROR {info['label']}: "
                f"{error}"
            )


            # -----------------------------------------------
            # NEVER DROP AN EXISTING COUNTRY
            # -----------------------------------------------

            old = (
                existing_countries
                .get(slug)
            )


            if old:

                countries[slug] = old

                print(
                    "Preserving last known "
                    "good observation."
                )

            else:

                print(
                    "No previous observation "
                    "available."
                )


    # ========================================================
    # VALIDATION BEFORE WRITE
    # ========================================================

    if not countries:

        raise RuntimeError(
            "No countries available. "
            "Existing JSON will not be replaced."
        )


    # Critical core markets must exist.
    for required in (
        "united_states",
        "euro_area"
    ):

        if required not in countries:

            raise RuntimeError(
                f"Critical market "
                f"{required} missing. "
                "JSON will not be replaced."
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
    #
    # Build a temporary JSON first.
    # Only replace the live file after the complete
    # document has been generated successfully.
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


    # Confirm generated JSON can be read.
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


    print(
        "\n=============================="
    )

    print(
        "Global yields update complete."
    )

    print(
        f"Countries preserved: "
        f"{len(countries)}"
    )

    print(
        f"Source errors: "
        f"{len(errors)}"
    )


if __name__ == "__main__":
    main()
