"""
Reads a Vantage Circle recognition-platform Excel export and computes every
number the report needs. Returns plain dicts/numbers only — no prose, no
formatting decisions beyond rounding. All narrative text is written later by
the LLM step (llm_insights.py), and it is only ever given these already-
correct numbers, never the raw workbook, so it cannot introduce a factual
error by recomputing something itself.
"""

import io
from collections import defaultdict

import openpyxl

MONTH_ORDER = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTH_SET = set(MONTH_ORDER)

# India fiscal year: Apr-Mar. Quarter number for each month name.
FY_QUARTER = {
    "April": 1, "May": 1, "June": 1,
    "July": 2, "August": 2, "September": 2,
    "October": 3, "November": 3, "December": 3,
    "January": 4, "February": 4, "March": 4,
}
FY_QUARTER_LABEL = {1: "Q1 (Apr-Jun)", 2: "Q2 (Jul-Sep)", 3: "Q3 (Oct-Dec)", 4: "Q4 (Jan-Mar)"}

METRIC_COLS = [
    "unique_login", "unique_receiver_monetary", "unique_receiver_non_monetary",
    "unique_giver_monetary", "unique_giver_non_monetary", "valid_user",
    "total_non_monetary_recognition", "total_monetary_recognition",
    "total_comments", "total_likes", "points_redemeed", "unique_login_rate",
    "receiver_coverage_monetary", "receiver_coverage_non_monetary",
    "giver_coverage_monetary", "giver_coverage_non_monetary", "recognition_mix",
]


def load_workbook(file_bytes: bytes):
    return openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)


def _header_row(ws):
    return [c for c in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]


def find_metrics_sheet(wb):
    """The sheet with one row per month/quarter — has company_id + month/quarter columns."""
    for ws in wb.worksheets:
        header = _header_row(ws)
        if "company_id" in header and "month/quarter" in header and "unique_login" in header:
            return ws
    raise ValueError(
        "Couldn't find a metrics sheet (expected columns like company_id, "
        "month/quarter, unique_login). This file doesn't match the expected export shape."
    )


def find_award_badge_sheet(wb):
    for ws in wb.worksheets:
        header = _header_row(ws)
        if "award_name_values" in header and "reward_type" in header:
            return ws
    return None  # optional — awards/badges pages just get skipped if absent


def parse_metrics_rows(ws):
    """Returns (month_rows, rollup_rows) — each a list of dicts keyed by column name.
    month_rows: one dict per real calendar month with actual data.
    rollup_rows: any row whose 'month/quarter' isn't a real month name (e.g. 'AMJ', 'Q1', 'FY25')."""
    header = _header_row(ws)
    month_rows, rollup_rows = [], []
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
        if row[0] is None or not isinstance(row[0], (int, float)):
            continue  # skip blank rows and any trailing metadata rows (e.g. an onboarding-date marker)
        record = dict(zip(header, row))
        label = record.get("month/quarter")
        if isinstance(label, str) and label in MONTH_SET:
            month_rows.append(record)
        else:
            rollup_rows.append(record)
    month_rows.sort(key=lambda r: (r["year_"], MONTH_ORDER.index(r["month/quarter"])))
    return month_rows, rollup_rows


def classify_periods(month_rows):
    """Returns one of:
    ('QBR', quarter_label, month_rows)      — 1-3 months, all in one FY quarter
    ('ABR', fy_label, month_rows)            — exactly 12 months spanning one FY (Apr-Mar)
    ('CUSTOM', None, month_rows)             — anything else; caller must ask the user
    """
    if not month_rows:
        raise ValueError("No monthly data rows found in this file.")

    quarters = {(r["year_"] if r["month/quarter"] not in ("January", "February", "March")
                 else r["year_"] - 1, FY_QUARTER[r["month/quarter"]]) for r in month_rows}

    if len(month_rows) <= 3 and len(quarters) == 1:
        (fy_start_year, q) = next(iter(quarters))
        return "QBR", f"FY{fy_start_year} {FY_QUARTER_LABEL[q]}", month_rows

    if len(month_rows) == 12:
        fy_years = {r["year_"] if r["month/quarter"] not in ("January", "February", "March")
                    else r["year_"] - 1 for r in month_rows}
        if len(fy_years) == 1:
            fy_start = next(iter(fy_years))
            return "ABR", f"FY{fy_start} (Apr {fy_start}–Mar {fy_start + 1})", month_rows

    return "CUSTOM", None, month_rows


def month_labels(month_rows, multi_year=None):
    """Short display labels for chart x-axes, e.g. 'April' or 'Apr\\'26' if the
    selection spans more than one calendar year."""
    years = {r["year_"] for r in month_rows}
    if multi_year is None:
        multi_year = len(years) > 1
    labels = []
    for r in month_rows:
        if multi_year:
            labels.append(f"{r['month/quarter'][:3]}'{str(r['year_'])[2:]}")
        else:
            labels.append(r["month/quarter"])
    return labels


def bucket_into_fy_quarters(month_rows):
    """Aggregates 12 months of rows into 4 FY-quarter rows. Counts are summed;
    rate/coverage %s are averaged across the quarter's months; recognition_mix
    is recomputed from the summed monetary/non-monetary totals (never averaged
    as a ratio directly, since that would weight months unevenly)."""
    buckets = defaultdict(list)
    for r in month_rows:
        fy_year = r["year_"] if r["month/quarter"] not in ("January", "February", "March") else r["year_"] - 1
        q = FY_QUARTER[r["month/quarter"]]
        buckets[(fy_year, q)].append(r)

    out = []
    for (fy_year, q) in sorted(buckets.keys(), key=lambda k: k[1]):
        rows = buckets[(fy_year, q)]
        agg = {"month/quarter": f"Q{q}", "year_": fy_year}
        for col in ["unique_login", "total_non_monetary_recognition", "total_monetary_recognition",
                    "total_comments", "total_likes", "points_redemeed"]:
            agg[col] = sum(r[col] for r in rows)
        for col in ["unique_login_rate", "receiver_coverage_monetary", "receiver_coverage_non_monetary",
                    "giver_coverage_monetary", "giver_coverage_non_monetary"]:
            agg[col] = sum(r[col] for r in rows) / len(rows)
        agg["recognition_mix"] = (
            agg["total_non_monetary_recognition"] / agg["total_monetary_recognition"]
            if agg["total_monetary_recognition"] else 0.0
        )
        out.append(agg)
    return out


def compute_period_metrics(rows, labels):
    """The core numeric payload for a set of period rows (months or FY quarters),
    already labeled for chart display. Everything downstream — charts, PDF,
    and the LLM insight prompt — reads from this dict only."""
    total_monetary = sum(r["total_monetary_recognition"] for r in rows)
    total_nonmonetary = sum(r["total_non_monetary_recognition"] for r in rows)
    total_points = sum(r["points_redemeed"] for r in rows)
    total_likes = sum(r["total_likes"] for r in rows)
    total_comments = sum(r["total_comments"] for r in rows)
    avg_login_rate = sum(r["unique_login_rate"] for r in rows) / len(rows)
    overall_mix = (total_nonmonetary / total_monetary) if total_monetary else 0.0

    return {
        "labels": labels,
        "unique_login": [r["unique_login"] for r in rows],
        "unique_login_rate": [r["unique_login_rate"] for r in rows],
        "monetary_recognition": [r["total_monetary_recognition"] for r in rows],
        "nonmonetary_recognition": [r["total_non_monetary_recognition"] for r in rows],
        "receiver_coverage_monetary": [r["receiver_coverage_monetary"] for r in rows],
        "receiver_coverage_non_monetary": [r["receiver_coverage_non_monetary"] for r in rows],
        "giver_coverage_monetary": [r["giver_coverage_monetary"] for r in rows],
        "giver_coverage_non_monetary": [r["giver_coverage_non_monetary"] for r in rows],
        "points_redeemed": [r["points_redemeed"] for r in rows],
        "likes": [r["total_likes"] for r in rows],
        "comments": [r["total_comments"] for r in rows],
        "totals": {
            "total_recognitions": total_monetary + total_nonmonetary,
            "total_monetary": total_monetary,
            "total_nonmonetary": total_nonmonetary,
            "total_points_redeemed": total_points,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "avg_login_rate": avg_login_rate,
            "recognition_mix": overall_mix,
        },
    }


def compute_awards_badges(ws, top_n=5):
    """Returns {'awards': [(name, count), ...], 'badges': [(name, count), ...]},
    each aggregated by exact name across source (csv/frontend) duplicates,
    sorted descending, top_n each. Returns None if no award/badge sheet exists."""
    if ws is None:
        return None
    header = _header_row(ws)
    reward_type_cols = [i for i, h in enumerate(header) if h == "reward_type"]

    totals = {"award": defaultdict(int), "badge": defaultdict(int)}
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
        for col in reward_type_cols:
            rtype = row[col]
            if rtype not in ("award", "badge"):
                continue
            name = row[col + 1]
            count = row[col + 3]
            if name is None or count is None:
                continue
            totals[rtype][name] += count

    def top(d):
        return sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:top_n]

    return {
        "awards": top(totals["award"]),
        "badges": top(totals["badge"]),
        "awards_total": sum(totals["award"].values()),
        "badges_total": sum(totals["badge"].values()),
    }
