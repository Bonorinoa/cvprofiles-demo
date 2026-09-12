"""Cached wrapper over the published cvprofiles engine.

Rules this module exists to enforce:

* The engine is a **published package** (``cvprofiles==3.0.2``). We never reimplement
  it — the demo is a thin UI over the real thing.
* ``run_profile`` takes file paths and writes a run directory. Every call gets a
  **fresh** temp dir, because reusing one silently unlinks the previous run's
  inference-layer artifacts (documented in the package's ``USER_GUIDE``). Temp dirs
  are removed once the summary is extracted.
* A menu subset is a *different validated input*, so it has a different ``run_id``.
  That is expected, not a broken freeze contract.
* Everything crossing into the UI is a plain dict, so results are cacheable.

Two ways in:

``run_case``
    The pinned network, with θ optionally re-tuned. This is what ``Run`` uses.
``run_custom``
    A **user-authored** network that replaces the pinned one wholesale. This is
    what ``Build network`` uses.

The one structural fact that shapes the builder: a restriction may bind to an
**auxiliary** column or to a **measure**. Aux-anchored networks survive leave-one-out;
a restriction bound to a measure does not, because dropping that measure leaves the
restriction pointing at a column that is gone and the engine refuses. That refusal is
correct — see ``anchor_class`` and ``leave_one_out_custom``.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml
from cvprofiles.pipeline import run_profile, summary_dict

APP_ROOT = Path(__file__).resolve().parents[1]

# The engine's restriction vocabulary. Copied from the package's schema, not invented;
# an unknown type is rejected by pydantic validation at run time.
RESTRICTION_TYPES: tuple[str, ...] = (
    "corr_min",
    "corr_sign",
    "corr_zero",
    "monotone_rank",
    "mean_order",
    "rank_agree",
    "stability",
)

# Which params key each type binds its column to. Types absent here need no column.
BINDING_KEY: dict[str, str] = {
    "corr_min": "variable",
    "corr_sign": "variable",
    "corr_zero": "variable",
    "monotone_rank": "variable",
    "mean_order": "group",
    "rank_agree": "ref_measure",
}
NEEDS_BINDING = tuple(BINDING_KEY)
NEEDS_SIGN = ("monotone_rank",)

STAGES = ("select", "holdout")


@dataclass(frozen=True)
class Fixture:
    key: str
    label: str
    blurb: str
    where: str  # "wheel" | "local"
    path: str


FIXTURES: tuple[Fixture, ...] = (
    Fixture(
        key="mini_v1",
        label="Teaching fixture",
        blurb="10 units, 3 measures. Ships inside the package — the same fixture "
        "`cvprofiles demo` uses.",
        where="wheel",
        path="mini_v1",
    ),
    Fixture(
        key="wvs_gps",
        label="Flagged flagship",
        blurb="41 countries, 7 measures. The WVS/GPS patience application, the "
        "package's public empirical example.",
        where="local",
        path="data/wvs_gps",
    ),
)

BY_KEY = {f.key: f for f in FIXTURES}


# --------------------------------------------------------------------- fixtures


def fixture_root(fx: Fixture) -> Path:
    if fx.where == "wheel":
        return Path(str(files("cvprofiles.data") / fx.path))
    return APP_ROOT / fx.path


def measures_of(fx: Fixture) -> list[str]:
    roles = json.loads((fixture_root(fx) / "roles.json").read_text())
    return list(roles["measures"])


def roles_of(fx: Fixture) -> dict:
    return json.loads((fixture_root(fx) / "roles.json").read_text())


def restrictions_of(fx: Fixture) -> list[dict]:
    """The pinned network, flattened for sliders: id, type, theta, stage."""
    net = yaml.safe_load((fixture_root(fx) / "network.yaml").read_text())
    return [
        {
            "id": r["id"],
            "type": r["type"],
            "theta": float(r.get("theta", 0.0)),
            "stage": r.get("stage", "select"),
        }
        for r in net.get("restrictions", [])
    ]


def bindable_columns(fx: Fixture) -> list[str]:
    """Every column a restriction may legally bind to, measures included.

    The engine allows measures as correlation partners, so the builder offers them —
    but the pedagogy is in showing what that costs you.
    """
    roles = roles_of(fx)
    cols: list[str] = []
    for key in ("aux", "measures"):
        for c in roles.get(key) or []:
            if c not in cols:
                cols.append(c)
    if roles.get("outcome"):
        cols.append(roles["outcome"])
    return cols


# ------------------------------------------------------- user-authored networks


def default_restrictions(fx: Fixture) -> list[dict]:
    """The pinned network as editable rows, in the builder's column order."""
    net = yaml.safe_load((fixture_root(fx) / "network.yaml").read_text())
    rows: list[dict] = []
    for r in net.get("restrictions", []):
        params = r.get("params") or {}
        key = BINDING_KEY.get(r["type"])
        rows.append(
            {
                "type": r["type"],
                "binds to": params.get(key, "") if key else "",
                "theta": float(r.get("theta", 0.0)),
                "id": r["id"],
                "stage": r.get("stage", "select"),
                "sign": int(params.get("sign", 1) or 1),
            }
        )
    return rows


def rows_to_restrictions(rows: list[dict]) -> list[dict]:
    """Turn editor rows into the engine's restriction schema.

    Rows the user left half-finished are dropped rather than sent to the engine to
    explode: a restriction with no id, or one whose type needs a binding and has none,
    cannot be evaluated, and saying so here gives a better message than a pydantic
    traceback.
    """
    out: list[dict] = []
    for i, r in enumerate(rows, start=1):
        t = str(r.get("type") or "").strip()
        if t not in RESTRICTION_TYPES:
            continue
        binds = r.get("binds to")
        binds = "" if binds is None else str(binds).strip()
        params: dict = {}
        key = BINDING_KEY.get(t)
        if key is not None:
            if not binds:
                continue  # needs a column, has none — skip, do not guess
            params[key] = binds
        if t in NEEDS_SIGN:
            try:
                params["sign"] = int(r.get("sign") or 1)
            except (TypeError, ValueError):
                params["sign"] = 1
        rid = str(r.get("id") or "").strip() or f"u{i}"
        try:
            theta = float(r.get("theta") or 0.0)
        except (TypeError, ValueError):
            theta = 0.0
        stage = str(r.get("stage") or "select")
        out.append(
            {
                "id": rid,
                "type": t,
                "theta": theta,
                "params": params,
                "stage": stage if stage in STAGES else "select",
            }
        )
    return out


def anchor_class(restriction: dict, measure_names: set[str] | tuple[str, ...]) -> str:
    """What a restriction is anchored to: ``measure``, ``aux`` or ``none``.

    This is the whole lesson of the builder. A measure-anchored restriction cannot
    survive the removal of the measure it names, so the reduction curve stops being
    available for that network.
    """
    key = BINDING_KEY.get(restriction.get("type", ""))
    if key is None:
        return "none"
    value = (restriction.get("params") or {}).get(key)
    if not value:
        return "none"
    return "measure" if value in set(measure_names) else "aux"


def network_to_yaml(restrictions: list[dict], name: str = "user_authored") -> str:
    return yaml.safe_dump(
        {"schema_version": "1", "name": name, "delta": 0.0, "restrictions": restrictions},
        sort_keys=False,
    )


# ------------------------------------------------------------------- execution


def _stage_workspace(
    fx: Fixture,
    measures: tuple[str, ...],
    thetas: tuple[tuple[str, float], ...],
    restrictions: list[dict] | None = None,
) -> Path:
    """Materialise one validated input set in a fresh directory.

    The directory is removed if staging fails part-way: the caller cannot clean up
    a path it never received, so failure cleanup belongs here.
    """
    work = Path(tempfile.mkdtemp(prefix="cvp_case_"))
    try:
        _populate_workspace(work, fx, measures, thetas, restrictions)
    except Exception:
        shutil.rmtree(work, ignore_errors=True)
        raise
    return work


def _populate_workspace(
    work: Path,
    fx: Fixture,
    measures: tuple[str, ...],
    thetas: tuple[tuple[str, float], ...],
    restrictions: list[dict] | None = None,
) -> None:
    """Write one validated input set into ``work``."""
    root = fixture_root(fx)
    for name in ("network.yaml", "beta.yaml", "score_manifest.json"):
        src = root / name
        if src.exists():
            shutil.copy(src, work / name)

    roles = json.loads((root / "roles.json").read_text())
    roles["measures"] = [m for m in roles["measures"] if m in measures]
    (work / "roles.json").write_text(json.dumps(roles, indent=2))

    df = pd.read_csv(root / "scores.csv")
    all_measures = set(measures_of(fx))
    keep = [c for c in df.columns if c not in all_measures or c in measures]
    df[keep].to_csv(work / "scores.csv", index=False)

    if restrictions is not None:
        # A user-authored network REPLACES the pinned one wholesale.
        net = yaml.safe_load((root / "network.yaml").read_text())
        net["name"] = "user_authored"
        net["restrictions"] = restrictions
        (work / "network.yaml").write_text(yaml.safe_dump(net, sort_keys=False))
    elif thetas:
        override = dict(thetas)
        net = yaml.safe_load((root / "network.yaml").read_text())
        for r in net.get("restrictions", []):
            if r["id"] in override:
                r["theta"] = override[r["id"]]
        (work / "network.yaml").write_text(yaml.safe_dump(net, sort_keys=False))


def _run(
    fixture_key: str,
    measures: tuple[str, ...],
    thetas: tuple[tuple[str, float], ...] = (),
    restrictions: list[dict] | None = None,
) -> dict:
    """Run one construct-validity profile. Returns a dict, or {"ok": False, ...}."""
    work: Path | None = None
    run_dir: Path | None = None
    try:
        # Inside the try on purpose: an unknown fixture key must come back as a
        # structured error, not a KeyError. The UI only ever passes keys from
        # FIXTURES, but the contract is what the tests hold us to.
        fx = BY_KEY[fixture_key]
        work = _stage_workspace(fx, measures, thetas, restrictions)
        run_dir = Path(tempfile.mkdtemp(prefix="cvp_run_"))
        result = run_profile(
            scores=work / "scores.csv",
            roles=work / "roles.json",
            network=work / "network.yaml",
            beta=work / "beta.yaml",
            out_dir=run_dir,
            title=f"{fx.label} — {len(measures)} measure(s)",
            write_parquet=False,
        )
        s = summary_dict(result)
        return {
            "ok": True,
            "empty": bool(s["empty"]),
            "M_star": list(s["M_star"] or []),
            "rejected": {k: list(v) for k, v in (s["rejected"] or {}).items()},
            "L": s["L"],
            "U": s["U"],
            "run_id": s["run_id"],
            "scores_hash": s["scores_hash"],
            "network_hash": s["network_hash"],
            "beta_hash": s["beta_hash"],
            "n_measures": len(measures),
        }
    except Exception as exc:  # RestrictError et al. are expected outcomes, not crashes
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:400]}
    finally:
        for d in (work, run_dir):
            if d is not None:
                shutil.rmtree(d, ignore_errors=True)


@st.cache_data(show_spinner=False, max_entries=256)
def run_case(
    fixture_key: str,
    measures: tuple[str, ...],
    thetas: tuple[tuple[str, float], ...] = (),
) -> dict:
    """The pinned network, θ optionally re-tuned."""
    return _run(fixture_key, measures, thetas)


@st.cache_data(show_spinner=False, max_entries=128)
def run_custom(
    fixture_key: str, measures: tuple[str, ...], restrictions_json: str
) -> dict:
    """A user-authored network, replacing the pinned one."""
    return _run(fixture_key, measures, (), json.loads(restrictions_json))


@st.cache_data(show_spinner=False, max_entries=32)
def leave_one_out(
    fixture_key: str, thetas: tuple[tuple[str, float], ...] = ()
) -> dict:
    """Baseline, then every single-measure removal — network and beta held fixed."""
    fx = BY_KEY[fixture_key]
    menu = tuple(measures_of(fx))
    baseline = run_case(fixture_key, menu, thetas)
    rows = [{"label": "full menu", "dropped": None, **baseline}]
    for m in menu:
        subset = tuple(x for x in menu if x != m)
        rows.append(
            {"label": f"− {m}", "dropped": m, **run_case(fixture_key, subset, thetas)}
        )
    return {"baseline": baseline, "rows": rows}


@st.cache_data(show_spinner=False, max_entries=32)
def leave_one_out_custom(fixture_key: str, restrictions_json: str) -> dict:
    """Leave-one-out on a user-authored network.

    This is where a measure-anchored network announces itself: the removal that
    orphans a restriction comes back as ``ok=False``, and the page turns that into
    the lesson instead of an error.
    """
    fx = BY_KEY[fixture_key]
    menu = tuple(measures_of(fx))
    baseline = run_custom(fixture_key, menu, restrictions_json)
    rows = [{"label": "full menu", "dropped": None, **baseline}]
    for m in menu:
        subset = tuple(x for x in menu if x != m)
        rows.append(
            {
                "label": f"− {m}",
                "dropped": m,
                **run_custom(fixture_key, subset, restrictions_json),
            }
        )
    return {"baseline": baseline, "rows": rows}


def width_of(case: dict) -> float | None:
    if not case.get("ok") or case.get("L") is None or case.get("U") is None:
        return None
    return round(case["U"] - case["L"], 6)