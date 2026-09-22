import tempfile
from datetime import datetime

import streamlit as st

import charts
import metrics
import pdf_builder
from template_insights import generate_insights

st.set_page_config(page_title="VC Business Review Builder", page_icon="\U0001F4C4", layout="wide")


def fmt_count(n):
    return f"{round(n):,}"


def fmt_millions(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    return f"{round(n):,}"


def fmt_pct(x, decimals=0):
    return f"{x * 100:.{decimals}f}%"


PAGE_DEFS = [
    {"key": "platform_engagement", "eyebrow": "Platform Engagement"},
    {"key": "recognition_volume", "eyebrow": "Recognition Volume"},
    {"key": "participation_coverage", "eyebrow": "Participation Coverage"},
    {"key": "points_redemption", "eyebrow": "Points & Redemption"},
    {"key": "monetary_awards", "eyebrow": "Monetary Awards"},
    {"key": "non_monetary_badges", "eyebrow": "Non-monetary Badges"},
    {"key": "social_engagement", "eyebrow": "Social Engagement"},
]


def build_report_input(client_name, report_type, period_label, m, aw, rsi, known_context):
    t = m["totals"]
    kpi_cards = [
        {"value": fmt_count(t["total_recognitions"]), "label": "Total recognitions"},
        {"value": fmt_millions(t["total_points_redeemed"]), "label": "Points redeemed"},
        {"value": fmt_pct(t["avg_login_rate"]), "label": "Avg login rate"},
        {"value": f"{t['recognition_mix']:.1f}", "label": "Recognition mix (NM:M)"},
    ]

    pages = []
    for pd in PAGE_DEFS:
        key = pd["key"]
        if key in ("monetary_awards", "non_monetary_badges") and aw is None:
            continue
        page = {"key": key, "eyebrow": pd["eyebrow"]}
        if key == "platform_engagement":
            page.update(labels=m["labels"], unique_login=m["unique_login"],
                        unique_login_rate=[round(v, 4) for v in m["unique_login_rate"]])
        elif key == "recognition_volume":
            latest_share = m["monetary_recognition"][-1] / max(
                1, m["monetary_recognition"][-1] + m["nonmonetary_recognition"][-1])
            page.update(labels=m["labels"], monetary=m["monetary_recognition"],
                        nonmonetary=m["nonmonetary_recognition"],
                        stat_value=fmt_pct(latest_share),
                        stat_meaning="share of the most recent period's recognitions that were monetary")
        elif key == "participation_coverage":
            page.update(labels=m["labels"],
                        receiver_monetary=[round(v, 4) for v in m["receiver_coverage_monetary"]],
                        receiver_nonmonetary=[round(v, 4) for v in m["receiver_coverage_non_monetary"]],
                        giver_monetary=[round(v, 4) for v in m["giver_coverage_monetary"]],
                        giver_nonmonetary=[round(v, 4) for v in m["giver_coverage_non_monetary"]])
        elif key == "points_redemption":
            page.update(labels=m["labels"], points_redeemed=m["points_redeemed"],
                        stat_value=fmt_millions(t["total_points_redeemed"]),
                        rsi=rsi)
        elif key == "monetary_awards":
            page.update(top5=[{"name": n, "count": c} for n, c in aw["awards"]])
        elif key == "non_monetary_badges":
            top1_share = aw["badges"][0][1] / max(1, aw["badges_total"])
            page.update(top5=[{"name": n, "count": c} for n, c in aw["badges"]],
                        stat_value=fmt_pct(top1_share),
                        stat_meaning=f"share of all badge activity held by the single top badge ({aw['badges'][0][0]})")
        elif key == "social_engagement":
            page.update(labels=m["labels"], likes=m["likes"], comments=m["comments"],
                        stat_likes=fmt_count(t["total_likes"]), stat_comments=fmt_count(t["total_comments"]))
        pages.append(page)

    return {
        "client_name": client_name,
        "report_type": report_type,
        "period_label": period_label,
        "kpi_cards": kpi_cards,
        "pages": pages,
        "known_context": known_context or "",
    }, kpi_cards


def build_pdf_context(client_name, report_title, period_label, prepared_date, kpi_cards,
                       m, aw, insights, report_type, closing_footer_label):
    chart_dir = tempfile.mkdtemp()
    page_by_key = {p["key"]: p for p in insights["pages"]}
    pdf_pages = []

    for pd in PAGE_DEFS:
        key = pd["key"]
        if key not in page_by_key:
            continue
        narrative = page_by_key[key]
        entry = {"eyebrow": pd["eyebrow"], "title": narrative.get("title", pd["eyebrow"])}

        if key == "platform_engagement":
            path = f"{chart_dir}/logins.png"
            charts.bar_line_chart(m["labels"], m["unique_login"], "Unique logins",
                                   m["unique_login_rate"], "Login rate %",
                                   f"Unique logins (bars) & login rate (line), {period_label}", path)
            entry.update(chart_path=path, sidebar_heading=narrative.get("sidebar_heading", "Reading the trend"),
                        sidebar_text=narrative.get("sidebar_text", []))
        elif key == "recognition_volume":
            path = f"{chart_dir}/recognition_volume.png"
            charts.grouped_bar_chart(m["labels"],
                                      [("Monetary", "orange", m["monetary_recognition"]),
                                       ("Non-monetary", "navy_soft", m["nonmonetary_recognition"])],
                                      f"Recognitions per period by type, {period_label}", path)
            latest_share = m["monetary_recognition"][-1] / max(
                1, m["monetary_recognition"][-1] + m["nonmonetary_recognition"][-1])
            body = (narrative.get("stat_box_bodies") or [""])[0]
            entry.update(chart_path=path,
                        stat_boxes=[{"value": fmt_pct(latest_share), "body": body}],
                        sidebar_text=narrative.get("sidebar_text", []))
        elif key == "participation_coverage":
            path = f"{chart_dir}/coverage.png"
            n_cat = len(m["labels"])
            charts.grouped_bar_chart(
                m["labels"],
                [("Receiver - Monetary", "orange", m["receiver_coverage_monetary"]),
                 ("Receiver - Non-monetary", "purple", m["receiver_coverage_non_monetary"]),
                 ("Giver - Monetary", "navy_soft", m["giver_coverage_monetary"]),
                 ("Giver - Non-monetary", "gray", m["giver_coverage_non_monetary"])],
                f"% of valid users active each period, {period_label}", path,
                is_pct=True, show_values=(n_cat <= 6),
                figsize=(7.6, 3.6) if n_cat > 6 else (6.4, 3.4),
            )
            entry.update(chart_path=path, sidebar_heading=narrative.get("sidebar_heading", "Reading coverage"),
                        sidebar_text=narrative.get("sidebar_text", []))
        elif key == "points_redemption":
            path = f"{chart_dir}/points.png"
            values_m = [v / 1_000_000 for v in m["points_redeemed"]]
            charts.comparison_bar_chart(m["labels"], values_m, path, highlight_last=False,
                                        is_pct=False, value_fmt="{:.2f}M",
                                        title=f"Points redeemed per period (millions), {period_label}")
            body = (narrative.get("stat_box_bodies") or [""])[0]
            entry.update(chart_path=path,
                        stat_boxes=[{"value": fmt_millions(sum(m["points_redeemed"])), "body": body}],
                        note=narrative.get("note") or None)
        elif key == "monetary_awards":
            names = [name for name, _ in aw["awards"]]
            counts = [count for _, count in aw["awards"]]
            path = f"{chart_dir}/awards.png"
            charts.horizontal_bar_chart(names, counts, path, title="Total receivers by award")
            entry.update(chart_path=path, sidebar_heading=narrative.get("sidebar_heading", "Read"),
                        sidebar_text=narrative.get("sidebar_text", []))
        elif key == "non_monetary_badges":
            names = [name for name, _ in aw["badges"]]
            counts = [count for _, count in aw["badges"]]
            path = f"{chart_dir}/badges.png"
            charts.horizontal_bar_chart(names, counts, path, title="Total receivers by badge", color_key="navy_soft")
            top1_share = aw["badges"][0][1] / max(1, aw["badges_total"])
            body = (narrative.get("stat_box_bodies") or [""])[0]
            entry.update(chart_path=path,
                        stat_boxes=[{"value": fmt_pct(top1_share), "body": body, "value_color": "#29294C"}],
                        note=narrative.get("note") or None)
        elif key == "social_engagement":
            path = f"{chart_dir}/social.png"
            charts.grouped_bar_chart(m["labels"], [("Likes", "orange", m["likes"]),
                                                    ("Comments", "navy_soft", m["comments"])],
                                      f"Likes & comments per period, {period_label}", path)
            bodies = narrative.get("stat_box_bodies") or ["", ""]
            entry.update(chart_path=path, sidebar_text=narrative.get("sidebar_text", []),
                        stat_boxes=[
                            {"value": fmt_count(sum(m["likes"])), "body": bodies[0] if bodies else ""},
                            {"value": fmt_count(sum(m["comments"])), "body": bodies[1] if len(bodies) > 1 else ""},
                        ])
        pdf_pages.append(entry)

    counter = {"n": 2}

    def next_page():
        counter["n"] += 1
        return counter["n"]

    return {
        "client_name": client_name,
        "report_title": report_title,
        "subtitle": f"Recognition & Rewards Program  ·  {period_label}",
        "cover_stats": kpi_cards[:3],
        "prepared_date": prepared_date,
        "footer_left": f"{client_name}  |  {report_title} — {period_label}",
        "page_counter": next_page,
        "exec_summary": {
            "headline": insights["exec_headline"],
            "kpi_cards": [{**kpi_cards[i], "sublabel": insights["kpi_sublabels"][i]} for i in range(4)],
            "callout_title": insights["callout_title"],
            "bullets": insights["callout_bullets"],
        },
        "pages": pdf_pages,
        "closing": {
            "eyebrow": "Recommended Actions",
            "title": insights["closing_title"],
            "items": [{"num": i + 1, **item} for i, item in enumerate(insights["closing_items"])],
            "footer": closing_footer_label,
        },
    }


st.title("VC Business Review Builder")
st.caption("Upload a recognition-platform export. Get back a client-ready QBR/ABR PDF.")

uploaded = st.file_uploader("Excel export (.xlsx)", type=["xlsx"])

if uploaded:
    try:
        wb = metrics.load_workbook(uploaded.read())
        metrics_ws = metrics.find_metrics_sheet(wb)
        award_ws = metrics.find_award_badge_sheet(wb)
        month_rows, rollup_rows = metrics.parse_metrics_rows(metrics_ws)
        auto_type, auto_label, _ = metrics.classify_periods(month_rows)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    month_names = [f"{r['month/quarter']} {r['year_']}" for r in month_rows]
    st.success(f"Found {len(month_rows)} month(s) of data: {month_names[0]} – {month_names[-1]}. "
               f"Auto-detected: **{auto_type}**"
               + (f" ({auto_label})" if auto_label else " (spans more than one clean quarter/year — pick below)"))

    col1, col2 = st.columns(2)
    with col1:
        default_name = uploaded.name.rsplit(".", 1)[0].split("_")[0]
        client_name = st.text_input("Client display name (confirm — not read from the file)", value=default_name)
        report_type_choice = st.selectbox(
            "Report type", ["Auto (" + auto_type + ")", "QBR", "ABR", "Custom / since-onboarding"])
    with col2:
        prepared_date = st.text_input("Prepared date", value=datetime.now().strftime("%B %Y"))
        known_context = st.text_area(
            "Known context (optional)",
            placeholder="e.g. 'April spike was a fiscal year-end redemption push' — "
                        "only what you confirm here will be used as a cause in the report.")

    if report_type_choice.startswith("Auto"):
        resolved_type = auto_type
    elif report_type_choice == "QBR":
        resolved_type = "QBR"
    elif report_type_choice == "ABR":
        resolved_type = "ABR"
    else:
        resolved_type = "CUSTOM"

    if resolved_type == "QBR":
        selected_rows = month_rows
        period_label = auto_label or f"{month_names[0]} – {month_names[-1]}"
        report_title = "Quarterly Business Review"
    elif resolved_type == "ABR":
        selected_rows = metrics.bucket_into_fy_quarters(month_rows)
        period_label = auto_label or f"{month_names[0]} – {month_names[-1]}"
        report_title = "Yearly Business Review"
    else:
        chosen = st.multiselect("Which months to include", month_names, default=month_names)
        selected_rows = [r for r, label in zip(month_rows, month_names) if label in chosen]
        bucket = st.checkbox("Bucket into fiscal quarters instead of showing every month",
                              value=(len(selected_rows) == 12))
        if bucket and len(selected_rows) >= 3:
            selected_rows = metrics.bucket_into_fy_quarters(selected_rows)
        period_label = f"{chosen[0]} – {chosen[-1]}" if chosen else ""
        report_title = "Business Review"

    if not selected_rows:
        st.warning("Select at least one month to continue.")
        st.stop()

    labels = metrics.month_labels(selected_rows)

    st.subheader("Reward Spend Index (optional)")
    st.caption("This export has no lifetime points-awarded column — RSI can't be computed from the file alone. "
               "Only fill these in if you have the real lifetime figures; otherwise leave blank and it's omitted.")
    rsi_col1, rsi_col2 = st.columns(2)
    lifetime_awarded = rsi_col1.number_input("Lifetime points awarded", min_value=0, value=0, step=1000)
    lifetime_redeemed = rsi_col2.number_input("Lifetime points redeemed", min_value=0, value=0, step=1000)
    rsi = None
    if lifetime_awarded > 0 and lifetime_redeemed > 0:
        rsi = {"lifetime_awarded": lifetime_awarded, "lifetime_redeemed": lifetime_redeemed,
               "rsi_pct": lifetime_redeemed / lifetime_awarded}

    if st.button("Generate report", type="primary"):
        with st.spinner("Computing metrics..."):
            m = metrics.compute_period_metrics(selected_rows, labels)
            aw = metrics.compute_awards_badges(award_ws) if award_ws is not None else None

        with st.spinner("Writing insights..."):
            report_input, kpi_cards = build_report_input(
                client_name, report_type_choice, period_label, m, aw, rsi, known_context)
            insights = generate_insights(report_input)

        with st.spinner("Building charts and PDF..."):
            ctx = build_pdf_context(client_name, report_title, period_label, prepared_date,
                                    kpi_cards, m, aw, insights, resolved_type,
                                    f"Vantage Circle · {client_name} {report_title} — {period_label} · {prepared_date}")
            out_path = tempfile.mktemp(suffix=".pdf")
            pdf_builder.build_report(ctx, out_path)

        with open(out_path, "rb") as f:
            pdf_bytes = f.read()
        st.success("Done.")
        st.download_button("Download PDF", data=pdf_bytes,
                            file_name=f"{client_name}_{resolved_type}_{prepared_date.replace(' ', '')}.pdf",
                            mime="application/pdf")
