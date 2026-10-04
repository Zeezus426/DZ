"""
Benchmark commodity prices for the home page ticker.

Source: World Bank Commodity Price Data (the "Pink Sheet"), published monthly
under CC-BY 4.0 at https://www.worldbank.org/en/research/commodity-markets

Why this source and not a live spot feed: there is no free, licence-clean API
for *daily* Australian coal or 62% Fe iron ore assessments. Those benchmarks
(Argus/McCloskey Newcastle, Platts PHCC, Platts IODEX) are commercial products
sold by the price reporting agencies — that is the whole business. The free
alternatives were checked and rejected: Yahoo Finance still serves the iron ore
and coal futures chains but the contracts are dead (last ticks 2021 and Feb
2025), CME blocks automated access under its data terms, API Ninjas carries no
bulk commodities at all, and the Trading Economics guest key now returns 410.

The Pink Sheet is the authoritative free fallback: monthly averages, released
around the second business day of each month. The template therefore labels
these as monthly benchmark averages, never as live spot.

To move to a real daily feed later, replace fetch_benchmarks(). The cache
contract and the template's data shape stay the same.
"""

import io
import logging
import re
import urllib.request

from django.core.cache import cache

logger = logging.getLogger(__name__)

CMO_LANDING = "https://www.worldbank.org/en/research/commodity-markets"

# Used only if the landing page cannot be scraped for the current release.
# The path carries a release stamp, so this pin goes stale — it is a floor,
# not the happy path.
CMO_FALLBACK_XLSX = (
    "https://thedocs.worldbank.org/en/doc/"
    "74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/"
    "CMO-Historical-Data-Monthly.xlsx"
)

# Keyed on the column headings exactly as they appear in the "Monthly Prices"
# sheet. Labels and units are pinned here rather than read off the sheet's unit
# row, because that row is unreliable: it labels iron ore "($/dmtu)" while the
# workbook's own Description sheet defines the series as "spot in US dollar/dry
# ton ... 62% Fe, c.f.r. China", and the values (~USD 98) are plainly per tonne,
# not per dry metric tonne unit. Quoting a bulk cargo in the wrong unit is the
# kind of error a counterparty notices, so the unit is stated deliberately.
#
# Definitions, per the same Description sheet:
#   Coal, Australian   — port thermal, f.o.b. Newcastle, 6,000 kcal/kg futures
#   Iron ore, cfr spot — any origin fines, 62% Fe, c.f.r. China
SERIES = (
    {
        "heading": "Coal, Australian",
        "label": "Thermal coal · Newcastle 6,000 kcal",
        "unit": "USD/t",
    },
    {
        "heading": "Iron ore, cfr spot",
        "label": "Iron ore 62% Fe · CFR China",
        "unit": "USD/dmt",
    },
)
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

CACHE_KEY = "home:benchmarks"
CACHE_TTL = 60 * 60 * 24           # one refresh per day, as specified
STALE_KEY = "home:benchmarks:last_good"
STALE_TTL = 60 * 60 * 24 * 30      # survives a month of upstream failures

_UA = "OTEC-website/1.0 (+https://otec.ltd)"
_TIMEOUT = 30


def _fetch(url, timeout=_TIMEOUT):
    request = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _workbook_url():
    """Resolve the current release URL; the path is versioned per release."""
    try:
        html = _fetch(CMO_LANDING).decode("utf-8", "replace")
        match = re.search(
            r"https://thedocs\.worldbank\.org/[^\"']*"
            r"CMO-Historical-Data-Monthly\.xlsx",
            html,
        )
        if match:
            return match.group(0)
        logger.warning("Pink Sheet link not found on CMO landing page")
    except Exception:
        logger.warning("Could not read CMO landing page", exc_info=True)
    return CMO_FALLBACK_XLSX


def _period_label(period):
    """'2026M07' -> 'Jul 2026'."""
    match = re.fullmatch(r"(\d{4})M(\d{2})", str(period).strip())
    if not match:
        return str(period)
    year, month = match.group(1), int(match.group(2))
    return f"{MONTHS[month - 1]} {year}" if 1 <= month <= 12 else str(period)


def _number(value):
    """Sheet uses '…' for months with no assessment."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_benchmarks():
    """Download and parse the Pink Sheet. Returns None if anything fails."""
    import openpyxl  # imported lazily so a parse-only dependency never blocks boot

    workbook = openpyxl.load_workbook(
        io.BytesIO(_fetch(_workbook_url(), timeout=60)),
        read_only=True,
        data_only=True,
    )
    rows = list(workbook["Monthly Prices"].iter_rows(values_only=True))

    # Locate the header by finding the first period row rather than hardcoding
    # offsets — the sheet carries a variable number of preamble notes.
    first_data = next(
        i for i, row in enumerate(rows)
        if row and re.fullmatch(r"\d{4}M\d{2}", str(row[0] or "").strip())
    )
    names = rows[first_data - 2]
    data = [row for row in rows[first_data:] if row and row[0]]

    # Keyed "series", not "items" — a dict key named `items` shadows nothing in
    # Django templates (dict lookup wins over attribute lookup) but reads as if
    # it might, which is a trap for the next person editing the template.
    series, as_of = [], None
    for spec in SERIES:
        heading = spec["heading"]
        try:
            column = names.index(heading)
        except ValueError:
            logger.warning("Pink Sheet column missing: %s", heading)
            continue

        priced = [(row[0], _number(row[column])) for row in data]
        priced = [(period, value) for period, value in priced if value is not None]
        if not priced:
            continue

        period, value = priced[-1]
        previous = priced[-2][1] if len(priced) > 1 else None
        change = ((value - previous) / previous * 100) if previous else None

        as_of = as_of or _period_label(period)
        series.append({
            "label": spec["label"],
            "value": f"{value:,.2f}",
            "unit": spec["unit"],
            "change": None if change is None else f"{abs(change):.1f}",
            "direction": "flat" if not change else ("up" if change > 0 else "down"),
        })

    if not series:
        return None

    return {"series": series, "as_of": as_of, "source": "World Bank Pink Sheet"}


def get_benchmarks():
    """
    Cached accessor for the template. Refreshes once every 24 hours; on an
    upstream failure it serves the last good result rather than an empty
    ticker, so a World Bank outage never blanks the home page.
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    try:
        result = fetch_benchmarks()
    except Exception:
        logger.warning("Benchmark price refresh failed", exc_info=True)
        result = None

    if result is None:
        stale = cache.get(STALE_KEY)
        if stale:
            stale = dict(stale, stale=True)
        return stale

    cache.set(CACHE_KEY, result, CACHE_TTL)
    cache.set(STALE_KEY, result, STALE_TTL)
    return result
