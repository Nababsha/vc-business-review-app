"""
Chart generators for the VC Business Review PDF skill.

Every function renders one PNG at 2x resolution (crisp when placed into the
PDF at its display size) using the shared Vantage Circle palette below.
Colors were pulled from the existing vc-qbr-deck-builder-v5 PowerPoint
template so this PDF and the deck stay visually related.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

PALETTE = {
    "orange": "#FF6D05",     # primary accent
    "navy": "#1E2761",       # dark page background / headings
    "navy_soft": "#29294C",  # secondary dark
    "purple": "#4F4F95",     # tertiary series
    "gray": "#A5A5A5",       # quaternary series / neutral
    "green": "#1D9E75",      # positive delta
    "red": "#C0392B",        # negative delta
    "card_bg": "#F3F4F8",    # light KPI card background
    "text_dark": "#1A1A1A",
    "text_muted": "#5F5E5A",
    "gridline": "#E4E4EA",
}

_FONT = "DejaVu Sans"


def _base_style(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="both", colors=PALETTE["text_muted"], labelsize=9)
    ax.yaxis.grid(True, color=PALETTE["gridline"], linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["bottom"].set_color(PALETTE["gridline"])


def _fmt_axis_pct(ax, axis="y"):
    fmt = mticker.PercentFormatter(xmax=1.0, decimals=0)
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def bar_line_chart(categories, bar_values, bar_label, line_values, line_label,
                    title, out_path, bar_value_fmt="{:,.0f}", line_is_pct=True,
                    figsize=(6.4, 3.4)):
    """Bars on primary y-axis + a % line on a secondary y-axis (login trend style)."""
    fig, ax1 = plt.subplots(figsize=figsize, dpi=200)
    x = range(len(categories))
    bars = ax1.bar(x, bar_values, color=PALETTE["navy_soft"], width=0.55, label=bar_label, zorder=3)
    _base_style(ax1)
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(categories)
    ax1.set_title(title, fontsize=10, color=PALETTE["text_muted"], loc="left", pad=10)
    top = max(bar_values) * 1.25 if bar_values else 1
    ax1.set_ylim(0, top)
    for rect, val in zip(bars, bar_values):
        # Label anchors at the base of the bar (white, va="bottom") rather than
        # near its top — with many categories the line can pass close to a
        # bar's top on any given axis, and a label placed there gets visually
        # cut by the line/marker crossing through it. The base is always clear.
        ax1.text(rect.get_x() + rect.get_width() / 2, top * 0.03,
                  bar_value_fmt.format(val), ha="center", va="bottom",
                  fontsize=8.5, color="white", fontweight="bold")

    ax2 = ax1.twinx()
    ax2.plot(x, line_values, color=PALETTE["orange"], linewidth=2.5,
              marker="o", markersize=5, label=line_label, zorder=4)
    ax2.spines["top"].set_visible(False)
    ax2.spines["left"].set_visible(False)
    ax2.spines["right"].set_color(PALETTE["gridline"])
    ax2.tick_params(axis="y", colors=PALETTE["orange"], labelsize=9)
    if line_is_pct:
        line_max = max(line_values) if line_values else 1
        ax2.set_ylim(0, max(line_max * 1.3, 0.1))
        _fmt_axis_pct(ax2)
    for xi, val in zip(x, line_values):
        label = f"{val*100:.1f}%" if line_is_pct else f"{val:,.0f}"
        # A white backing box stops a steep line segment from painting
        # through its own neighboring point's label (seen on sharp
        # rises/drops with many categories).
        ax2.annotate(label, (xi, val), textcoords="offset points", xytext=(0, 10),
                     ha="center", fontsize=8.5, color=PALETTE["orange"], fontweight="bold",
                     bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none"), zorder=6)

    fig.legend(loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.02),
               frameon=False, fontsize=9)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(out_path, transparent=True, bbox_inches="tight")
    plt.close(fig)


def grouped_bar_chart(categories, series, title, out_path, value_fmt="{:,.0f}",
                       is_pct=False, figsize=(6.4, 3.4), show_values=True):
    """series: list of (label, color_key_or_hex, values) tuples, 2-4 series."""
    fig, ax = plt.subplots(figsize=figsize, dpi=200)
    n = len(series)
    width = 0.8 / n
    x = list(range(len(categories)))
    all_vals = [v for _, _, vals in series for v in vals]
    top = (max(all_vals) if all_vals else 1) * 1.25

    for i, (label, color_key, values) in enumerate(series):
        color = PALETTE.get(color_key, color_key)
        offsets = [xi + (i - (n - 1) / 2) * width for xi in x]
        bars = ax.bar(offsets, values, width=width * 0.92, color=color, label=label, zorder=3)
        if show_values:
            for rect, val in zip(bars, values):
                label_txt = f"{val*100:.1f}%" if is_pct else value_fmt.format(val)
                ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + top * 0.015,
                        label_txt, ha="center", va="bottom", fontsize=7, color=PALETTE["text_dark"])

    _base_style(ax)
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylim(0, top)
    if is_pct:
        _fmt_axis_pct(ax)
    ax.set_title(title, fontsize=10, color=PALETTE["text_muted"], loc="left", pad=10)
    legend_ncol = 2 if n >= 3 else n
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=legend_ncol,
               bbox_to_anchor=(0.5, -0.02), frameon=False, fontsize=8.5)
    fig.tight_layout(rect=[0, 0.14 if n >= 3 else 0.08, 1, 1])
    fig.savefig(out_path, transparent=True, bbox_inches="tight")
    plt.close(fig)


def horizontal_bar_chart(labels, values, out_path, title=None, value_fmt="{:,.0f}",
                          color_key="orange", figsize=(6.2, 3.6)):
    """Top-N style horizontal bars, largest at top."""
    fig, ax = plt.subplots(figsize=figsize, dpi=200)
    pairs = sorted(zip(labels, values), key=lambda p: p[1])
    labels_sorted, values_sorted = zip(*pairs) if pairs else ([], [])
    y = range(len(labels_sorted))
    bars = ax.barh(y, values_sorted, color=PALETTE.get(color_key, color_key), height=0.6, zorder=3)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels_sorted, fontsize=9, color=PALETTE["text_dark"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.xaxis.grid(True, color=PALETTE["gridline"], linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", colors=PALETTE["text_muted"], labelsize=8.5)
    top = max(values_sorted) * 1.18 if values_sorted else 1
    ax.set_xlim(0, top)
    for rect, val in zip(bars, values_sorted):
        ax.text(rect.get_width() + top * 0.015, rect.get_y() + rect.get_height() / 2,
                value_fmt.format(val), va="center", fontsize=8.5,
                color=PALETTE["text_dark"], fontweight="bold")
    if title:
        ax.set_title(title, fontsize=10, color=PALETTE["text_muted"], loc="left", pad=10)
    fig.tight_layout()
    fig.savefig(out_path, transparent=True, bbox_inches="tight")
    plt.close(fig)


def comparison_bar_chart(categories, values, out_path, highlight_last=True,
                          value_fmt="{:.1f}%", is_pct=True, title=None, figsize=(5.4, 3.4)):
    """Trend bars with the most recent/newest period highlighted in orange."""
    fig, ax = plt.subplots(figsize=figsize, dpi=200)
    colors = [PALETTE["navy_soft"]] * len(categories)
    if highlight_last and categories:
        colors[-1] = PALETTE["orange"]
    x = range(len(categories))
    top = (max(values) if values else 1) * 1.25
    bars = ax.bar(x, values, color=colors, width=0.55, zorder=3)
    _base_style(ax)
    ax.set_xticks(list(x))
    ax.set_xticklabels(categories)
    ax.set_ylim(0, top)
    if is_pct:
        _fmt_axis_pct(ax)
    for rect, val in zip(bars, values):
        label = f"{val*100:.1f}%" if is_pct else value_fmt.format(val)
        ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + top * 0.02,
                label, ha="center", va="bottom", fontsize=8.5, color=PALETTE["text_dark"], fontweight="bold")
    if title:
        ax.set_title(title, fontsize=10, color=PALETTE["text_muted"], loc="left", pad=10)
    fig.tight_layout()
    fig.savefig(out_path, transparent=True, bbox_inches="tight")
    plt.close(fig)
