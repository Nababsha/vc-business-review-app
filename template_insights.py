"""
Deterministic, rule-based replacement for llm_insights.py — no external API
call, no cost, nothing to configure. Produces the exact same output shape
(same keys the tool schema in llm_insights.py would have returned) from the
same report_input dict, using plain Python string templates instead of an
LLM. The language is plainer and doesn't draw cross-metric connections the
way a written-by-hand or LLM-written narrative would, but every number is
still pulled directly from report_input — nothing is invented.
"""


def _fmt_pct_raw(x, decimals=0):
    return f"{x * 100:.{decimals}f}%"


def _trend_word(first, last):
    if last > first * 1.15:
        return "rose"
    if last < first * 0.85:
        return "fell"
    return "held roughly flat"


def _peak_index(values):
    return max(range(len(values)), key=lambda i: values[i])


def generate_insights(report_input: dict, api_key=None) -> dict:  # api_key accepted for call-site symmetry, unused
    client_name = report_input["client_name"]
    period_label = report_input["period_label"]
    pages_in = {p["key"]: p for p in report_input["pages"]}
    known_context = report_input.get("known_context") or ""

    exec_headline = f"{period_label}: a look at {client_name}'s recognition activity"

    kpi_cards = report_input["kpi_cards"]
    kpi_sublabels = []
    for card in kpi_cards:
        kpi_sublabels.append(f"{card['label']} across {period_label}")

    callout_bullets = []
    pe = pages_in.get("platform_engagement")
    if pe:
        rates = pe["unique_login_rate"]
        first, last = rates[0], rates[-1]
        peak_i = _peak_index(rates)
        callout_bullets.append(
            f"Login rate {_trend_word(first, last)} across {period_label}, from "
            f"{_fmt_pct_raw(first, 1)} to {_fmt_pct_raw(last, 1)}, peaking at "
            f"{_fmt_pct_raw(rates[peak_i], 1)} in {pe['labels'][peak_i]}."
        )
    rv = pages_in.get("recognition_volume")
    if rv:
        total_mon, total_nm = sum(rv["monetary"]), sum(rv["nonmonetary"])
        leader = "monetary" if total_mon > total_nm else "non-monetary"
        callout_bullets.append(
            f"Across {period_label}, {leader} recognition made up the larger share overall "
            f"({total_mon:,} monetary vs {total_nm:,} non-monetary)."
        )
    pc = pages_in.get("participation_coverage")
    if pc:
        avg_recv = sum(pc["receiver_monetary"] + pc["receiver_nonmonetary"]) / (
            len(pc["receiver_monetary"]) + len(pc["receiver_nonmonetary"]))
        avg_give = sum(pc["giver_monetary"] + pc["giver_nonmonetary"]) / (
            len(pc["giver_monetary"]) + len(pc["giver_nonmonetary"]))
        callout_bullets.append(
            f"Receiver coverage averaged {_fmt_pct_raw(avg_recv, 1)} across {period_label}, versus "
            f"{_fmt_pct_raw(avg_give, 1)} for giver coverage — recognition reached more people than it "
            f"came from."
        )
    while len(callout_bullets) < 3:
        callout_bullets.append(f"See the following pages for a full breakdown of {client_name}'s numbers.")
    callout_bullets = callout_bullets[:3]

    pages_out = []
    for p in report_input["pages"]:
        key = p["key"]
        entry = {"key": key, "title": key.replace("_", " ").title()}

        if key == "platform_engagement":
            rates, logins, labels = p["unique_login_rate"], p["unique_login"], p["labels"]
            peak_i = _peak_index(logins)
            entry["sidebar_heading"] = "Reading the trend"
            entry["sidebar_text"] = [
                f"Login rate went from {_fmt_pct_raw(rates[0], 1)} in {labels[0]} to "
                f"{_fmt_pct_raw(rates[-1], 1)} in {labels[-1]}.",
                f"Unique logins peaked in {labels[peak_i]} at {logins[peak_i]:,}.",
            ]
        elif key == "recognition_volume":
            entry["stat_box_bodies"] = [f"share of the most recent period's recognitions that were monetary."]
            entry["sidebar_text"] = [
                f"Monetary recognition totaled {sum(p['monetary']):,} and non-monetary totaled "
                f"{sum(p['nonmonetary']):,} across {period_label}."
            ]
        elif key == "participation_coverage":
            entry["sidebar_heading"] = "Reading coverage"
            entry["sidebar_text"] = [
                f"Receiver coverage (monetary) averaged {_fmt_pct_raw(sum(p['receiver_monetary']) / len(p['receiver_monetary']), 1)}; "
                f"giver coverage (monetary) averaged {_fmt_pct_raw(sum(p['giver_monetary']) / len(p['giver_monetary']), 1)}.",
                f"Receiver coverage (non-monetary) averaged {_fmt_pct_raw(sum(p['receiver_nonmonetary']) / len(p['receiver_nonmonetary']), 1)}; "
                f"giver coverage (non-monetary) averaged {_fmt_pct_raw(sum(p['giver_nonmonetary']) / len(p['giver_nonmonetary']), 1)}.",
            ]
        elif key == "points_redemption":
            entry["stat_box_bodies"] = [f"points redeemed across {period_label}."]
            if p.get("rsi"):
                rsi = p["rsi"]
                entry["note"] = (
                    f"Reward Spend Index: {rsi['lifetime_redeemed']:,} of {rsi['lifetime_awarded']:,} points "
                    f"awarded have been redeemed to date ({_fmt_pct_raw(rsi['rsi_pct'], 1)})."
                )
            else:
                entry["note"] = (
                    "A lifetime Reward Spend Index isn't derivable from this export (no cumulative "
                    "points-awarded figure) — this reflects only this period's own redemption totals."
                )
        elif key == "monetary_awards":
            top = p["top5"]
            entry["sidebar_heading"] = "Read"
            entry["sidebar_text"] = [
                f"{top[0]['name']} led with {top[0]['count']:,} receivers"
                + (f", ahead of {top[1]['name']} ({top[1]['count']:,})." if len(top) > 1 else ".")
            ]
        elif key == "non_monetary_badges":
            top = p["top5"]
            entry["stat_box_bodies"] = [
                f"share of all badge activity held by the single top badge ({top[0]['name']})."
            ]
            entry["note"] = (
                f"The remaining badges in the top 5 — "
                + ", ".join(f"{b['name']} ({b['count']:,})" for b in top[1:]) + "."
                if len(top) > 1 else ""
            )
        elif key == "social_engagement":
            likes, comments, labels = p["likes"], p["comments"], p["labels"]
            peak_i = _peak_index(likes)
            entry["stat_box_bodies"] = [
                f"Likes across {period_label}, peaking in {labels[peak_i]} ({likes[peak_i]:,}).",
                f"Comments across {period_label}, peaking in {labels[_peak_index(comments)]} "
                f"({comments[_peak_index(comments)]:,}).",
            ]
            entry["sidebar_text"] = []

        pages_out.append(entry)

    closing_items = [
        {"title": "Review receiver/giver coverage",
         "body": "Giver coverage trailed receiver coverage across the period — widening who actively "
                 "gives recognition, not just who receives it, is worth reviewing."},
        {"title": "Watch the recognition mix",
         "body": "Compare the monetary vs non-monetary split against what's intentional for this program "
                 "and adjust if either side is drifting unexpectedly."},
        {"title": "Review the awards/badges catalog",
         "body": "A small number of awards or badges carry most of the activity — confirm whether the "
                 "long tail still serves a purpose or could be consolidated."},
        {"title": "Track login rate month to month",
         "body": "Login rate moved across the period — identifying what drove the strongest month could "
                 "help replicate it going forward."},
        {"title": "Revisit this report next period",
         "body": f"Re-running this report next period will show whether these {client_name} trends are "
                 "continuing or reversing."},
    ]
    if known_context:
        closing_items[0]["body"] += f" Noted context: {known_context}"

    return {
        "exec_headline": exec_headline,
        "kpi_sublabels": kpi_sublabels,
        "callout_title": f"What {period_label} shows",
        "callout_bullets": callout_bullets,
        "pages": pages_out,
        "closing_title": f"Priorities going forward",
        "closing_items": closing_items,
    }
