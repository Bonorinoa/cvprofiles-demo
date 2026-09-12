# cvprofiles — interactive demo

**Change the assumptions, watch the conclusion move.**

A thin Streamlit UI over the published [`cvprofiles`](https://pypi.org/project/cvprofiles/)
package. The engine is *never* reimplemented here — this project only stages validated
inputs, calls `run_profile`, and renders what comes back.

## Why it exists

`cvprofiles` answers a question most tooling skips: *given your theory's observable
implications, which of your measures is even entitled to the interpretation you want?*
The answer is a set (`M*`) and a range, not a star. That is hard to explain in prose and
obvious when someone moves a slider.

## Run it

```bash
uv venv .venv --python 3.11
uv pip install -e .
.venv/bin/streamlit run streamlit_app.py
```

Two screens:

| Route | Screen | What it shows |
|---|---|---|
| `/` | **Run** | Menu + restriction θ as live controls. Reports the admissible set `M*`, the identified range `[L, U]`, and which restriction rejected each measure. |
| `/reduction` | **Reduction** | Leave-one-out over the menu. Shows which measures are load-bearing and which are inert. |

The default page lives at `/`; `url_path` on a `default=True` page does **not** create a
route, so `/run` 404s. `reduction` is its own route.

## Design notes

* **Theme lives in `.streamlit/config.toml`** — the site's own academic tokens (oxblood
  `#6b2c1f`, paper `#f6f1e7`, Fraunces). No custom CSS; `streamlit config show` confirms
  attribution.
* **Every engine call gets a fresh temp dir.** A reused `out_dir` silently unlinks the
  previous run's inference-layer artifacts. Temp dirs are removed after the summary is
  extracted.
* **Subsetting the menu changes the validated input, and therefore the `run_id`.** That is
  the provenance contract working, not a broken freeze.
* **The empty admissible set is a designed state, not an error.** The engine returns
  `empty=True` and exit 0 — "a finding, not a failure". The UI says so in words.
* **`RestrictError` is surfaced, not swallowed** — the engine refused the input rather
  than guessing, and the page explains which kind of binding caused it.
* Outputs are labelled **exploratory**. They are not citable paper evidence; the package's
  provenance rule requires the pinned freeze bundle.

## What the flagship actually shows

41 countries, 7 measures, WVS/GPS patience application:

* `[L, U] = [0.3275, 0.4025]`, width `0.0750`, `|M*| = 2`
* **Five of seven measures are inert** — dropping `m_wvs_q13`, `m_wvs_q14`, `m_composite`,
  `m_prompt_b`, or `m_noise` moves the range by exactly zero.
* The width comes entirely from two measures in tension: `m_gps_patience` (floor) and
  `m_prompt_a` (ceiling).
* Dropping *either* collapse the width to zero while `|M*|` falls to 1 — a **narrower
  range that is a worse answer**. The same disagreement with one side deleted.
* `wvs_gps` empties entirely at θ ≥ 0.6.

## Verifying changes

```bash
.venv/bin/python verify_app.py     # AppTest: both pages render, no exceptions
```

`verify_app.py` also hunts for empty-`M*` configurations, so the headline state stays
reachable.

Screenshots need care: Chrome's `--screenshot` fires before Streamlit's websocket delivers
the element tree, so it captures a bare skeleton. Use `cdp_shot.py`, which drives Chrome
over CDP and waits:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --user-data-dir=/tmp/cdp-profile --remote-debugging-port=9222 about:blank &
.venv/bin/python cdp_shot.py "http://127.0.0.1:8507/" shots/run.png 15 1500
```

`--user-data-dir` is required: without it Chrome reuses a running instance and ignores
`--remote-debugging-port`.
