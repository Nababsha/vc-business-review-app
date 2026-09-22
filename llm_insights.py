"""
NOT CURRENTLY USED by app.py — kept here as a documented upgrade path.

app.py uses template_insights.py instead, which needs no external API call
(current policy doesn't allow external LLM API spend for this app). This
module is the higher-quality alternative: it calls the Claude API to write
the narrative text for the report. This step never sees the raw workbook and
never invents a number — it is handed only the already-computed metrics dict
from metrics.py (all arithmetic done in Python) and asked to produce prose
that describes those numbers accurately, plus recommendations grounded in
them. A forced tool-call schema keeps the output structured so app.py could
drop it straight into the PDF context, same shape as template_insights.py's
output.

To switch to this: add `anthropic` back to requirements.txt, set
ANTHROPIC_API_KEY as a Streamlit secret, and change app.py's import from
`from template_insights import generate_insights` to
`from llm_insights import generate_insights` (and pass api_key= through).
"""

import json
import os

import anthropic

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """You are writing the narrative text for a Vantage Circle client \
recognition-platform business review PDF (a QBR, ABR, or since-onboarding review). \
You are given ONLY pre-computed, already-correct numbers — never raw data — and your \
job is to describe them accurately and write grounded recommendations. You must never \
introduce a number, campaign, or cause that isn't present in the data you were given.

## Rounding (apply consistently — a number must read the same everywhere it recurs)
- Login rate, coverage %: 1 decimal for a single period's value (e.g. monthly), whole \
number for an aggregate/overall value.
- Recognition mix (NM:M ratio): always 1 decimal.
- Recognitions, receiver/giver counts, likes, comments: whole numbers, comma-separated \
(e.g. "12,439").
- Points redeemed: millions to 2 decimals once >= 1,000,000 (e.g. "8.49M"), else whole \
number.

## Per deep-dive page
Write 1-3 short sidebar paragraphs and/or 1-2 stat-box bodies (never more) per page. \
Structure: (1) the within-metric trend stated with real numbers, (2) a cross-metric \
connection ONLY if genuinely meaningful (don't force one), (3) keep recommendations for \
the closing page, not scattered per-page — a one-line recommendation tightly scoped to \
that page's own finding is fine inside a "note", but the five main recommendations belong \
in closing_items.

## The Six-Point Check — apply to every insight block before finalizing it
1. Numeric accuracy — every number must come from the data you were given.
2. Magnitude language calibration — word choice must scale to the actual gap: a >2x \
change or >15-20pt swing earns "sharply"/"reversed"/"overtook"; a few points earns \
"slightly"/"held roughly flat"/"eased".
3. Causal-attribution scoping — NEVER attach a cause ("driven by X", "due to a \
campaign") unless it was explicitly given to you as confirmed context. Describe trends \
without attributing a cause otherwise.
4. Topical fit — don't reuse a sentence or finding across pages it doesn't belong to.
5. Non-repetition — don't reuse the same stylistic adjective ("steady", "strong", \
"healthy") across multiple pages. Subject-matter terms (monetary, coverage, recognition) \
are fine to repeat; descriptive/stylistic words are not.
6. Recommendation-grounding — every closing-page item must trace back to a specific \
number from a specific page. Double-check direction (if metric A is lagging, the \
recommendation targets A, not B) and entity attribution (a named award/badge's number \
must match that award/badge, not a neighboring one).

## Guardrails
- No data manufacturing: never invent a number, campaign, cause, or lifetime/RSI figure \
that wasn't given to you. If `rsi` is not present in the input, do not mention a Reward \
Spend Index, a lifetime points-awarded figure, or any redemption ratio beyond the \
period's own totals — say only what the period's own numbers show.
- Every number you state must be traceable to the input JSON you were given.
- Write tightly: each sidebar paragraph or stat-box body should read in a few seconds, \
not become a paragraph.

You must respond only by calling the write_insights tool with the complete structured \
output — do not write any other text."""

TOOL_SCHEMA = {
    "name": "write_insights",
    "description": "The complete narrative text for the business review PDF.",
    "input_schema": {
        "type": "object",
        "properties": {
            "exec_headline": {"type": "string", "description": "Executive summary page title, one sentence."},
            "kpi_sublabels": {
                "type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4,
                "description": "One short sublabel per KPI card, in the same order as the input's kpi_cards.",
            },
            "callout_title": {"type": "string", "description": "e.g. 'What the quarter tells us'"},
            "callout_bullets": {
                "type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3,
            },
            "pages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "title": {"type": "string"},
                        "sidebar_heading": {"type": "string"},
                        "sidebar_text": {"type": "array", "items": {"type": "string"}},
                        "stat_box_bodies": {"type": "array", "items": {"type": "string"}},
                        "note": {"type": "string"},
                    },
                    "required": ["key", "title"],
                },
            },
            "closing_title": {"type": "string"},
            "closing_items": {
                "type": "array", "minItems": 4, "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
                    "required": ["title", "body"],
                },
            },
        },
        "required": ["exec_headline", "kpi_sublabels", "callout_title", "callout_bullets",
                     "pages", "closing_title", "closing_items"],
    },
}


def get_client(api_key=None):
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("No Anthropic API key found (set ANTHROPIC_API_KEY or pass one in).")
    return anthropic.Anthropic(api_key=key)


def generate_insights(report_input: dict, api_key=None) -> dict:
    """report_input: {client_name, report_type, period_label, kpi_cards (value+label only),
    pages (key/eyebrow/available metric series), awards, badges, rsi (optional), notable_patterns
    (optional list of strings describing e.g. a sharp month-over-month swing to ask about
    but NOT explain a cause for unless the caller already confirmed one)}."""
    client = get_client(api_key)
    message = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        tools=[TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": "write_insights"},
        messages=[{"role": "user", "content": json.dumps(report_input, indent=2)}],
    )
    for block in message.content:
        if block.type == "tool_use" and block.name == "write_insights":
            return block.input
    raise RuntimeError("Claude did not return a write_insights tool call.")
