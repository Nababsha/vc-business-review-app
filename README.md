# VC Business Review Builder

Upload a Vantage Circle recognition-platform Excel export and get back a
client-ready QBR/ABR PDF: cover, executive summary, one page per metric, and
closing recommendations. Charts and layout are deterministic Python
(`charts.py` / `pdf_builder.py`); the narrative text is written by Claude
(`llm_insights.py`), given only the already-computed numbers so it can't
introduce a factual error.

## Run it locally

```
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit .streamlit/secrets.toml and paste in a real Anthropic API key
streamlit run app.py
```

Get an API key at https://console.anthropic.com/ (Settings -> API Keys).

## Deploy so colleagues can use it

1. Push this repo to GitHub (see below for the exact commands).
2. Go to https://share.streamlit.io, sign in, click "New app", pick this repo
   and `app.py` as the entry point.
3. Before or after deploying, open the app's **Settings -> Secrets** in the
   Streamlit Cloud dashboard and paste:
   ```
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
4. Share the app's URL (looks like `https://<something>.streamlit.app`) with
   colleagues. No login is required to open it — anyone with the link can
   use it, so don't post the link anywhere public.

## How it works

- `metrics.py` — reads the uploaded workbook, classifies it as a QBR (1-3
  months in one fiscal quarter), ABR (a full Apr-Mar fiscal year, bucketed
  into quarters), or a custom period range; computes every number the report
  needs.
- `llm_insights.py` — sends only those computed numbers (never the raw file)
  to Claude with a forced structured-output schema, asking it to write the
  headline, KPI sublabels, callout bullets, per-page narrative, and closing
  recommendations.
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
