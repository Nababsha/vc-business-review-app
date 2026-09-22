# VC Business Review Builder

Upload a Vantage Circle recognition-platform Excel export and get back a
client-ready QBR/ABR PDF: cover, executive summary, one page per metric, and
closing recommendations. Charts and layout are deterministic Python
(`charts.py` / `pdf_builder.py`); the narrative text is written by
`template_insights.py` from the already-computed numbers only — no external
API calls, no cost, nothing to configure.

## Run it locally

```
pip install -r requirements.txt
streamlit run app.py
```

## Deploy so colleagues can use it

1. Push this repo to GitHub (already done if you're reading this from the repo).
2. Go to https://share.streamlit.io, sign in, click "New app", pick this repo
   and `app.py` as the entry point. No secrets to configure.
3. Share the app's URL (looks like `https://<something>.streamlit.app`) with
   colleagues. No login is required to open it — anyone with the link can
   use it, so don't post the link anywhere public.

## How it works

- `metrics.py` — reads the uploaded workbook, classifies it as a QBR (1-3
  months in one fiscal quarter), ABR (a full Apr-Mar fiscal year, bucketed
  into quarters), or a custom period range; computes every number the report
  needs.
- `template_insights.py` — turns those computed numbers into plain,
  templated sentences (no LLM). Every number it states comes directly from
  what `metrics.py` computed — nothing is invented, but the language is
  simpler and doesn't draw the same cross-metric connections a hand-written
  or LLM-written narrative would.
- `llm_insights.py` — **not currently wired in.** A higher-quality
  alternative that calls the Claude API for the narrative step, kept as a
  documented upgrade path if the no-external-API-spend policy changes later
  (see the docstring at the top of that file for how to switch to it).
- `charts.py` / `pdf_builder.py` — render the charts and lay out the final
  PDF. This is the same rendering engine used to build the initial QBR PDFs
  by hand, so the visual design stays consistent.
- `app.py` — the Streamlit UI that ties it together: upload, confirm client
  name / report type / period, optionally supply real lifetime
  points-awarded figures for a Reward Spend Index, generate, download.

## Notes / limitations carried over from the manual process

- **RSI (Reward Spend Index)** isn't derivable from the standard export (no
  cumulative points-awarded column). The app only shows it if you type in
  real lifetime figures; otherwise it's omitted rather than guessed.
- **Client display name** is taken from the uploaded filename as a starting
  guess but always requires confirmation in the form — never trust the
  filename blindly for a real client name.
- If the file spans more than one clean quarter/year (e.g. a client's first
  several months since onboarding), the app asks you to pick exactly which
  months to include rather than guessing a boundary.
- Without an LLM writing the narrative, the insight text is more formulaic
  than the PDFs built by hand earlier — it states real numbers and trends
  accurately, but doesn't draw deeper cross-metric conclusions or calibrate
  language to the size of a gap the way a person (or an LLM prompted for it)
  would.
