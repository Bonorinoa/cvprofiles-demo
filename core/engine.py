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


def fixture_root(fx: Fixture) -> Path:
    if fx.where == "wheel":
        return Path(str(files("cvprofiles.data") / fx.path))
    return APP_ROOT / fx.path


def measures_of(fx: Fixture) -> list[str]:
    roles = json.loads((fixture_root(fx) / "roles.json").read_text())
    return list(roles["measures"])


def restrictions_of(fx: Fixture) -> list[dict]:
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


def _stage_workspace(
    fx: Fixture, measures: tuple[str, ...], thetas: tuple[tuple[str, float], ...]
) -> Path:
    """Materialise one validated input set in a fresh directory.

    The directory is removed if staging fails part-way: the caller cannot clean up
    a path it never received, so failure cleanup belongs here.
    """
    work = Path(tempfile.mkdtemp(prefix="cvp_case_"))
    try:
        _populate_workspace(work, fx, measures, thetas)
    except Exception:
        shutil.rmtree(work, ignore_errors=True)
        raise
    return work


def _populate_workspace(
    work: Path,
    fx: Fixture,
    measures: tuple[str, ...],
    thetas: tuple[tuple[str, float], ...],
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

    if thetas:
        override = dict(thetas)
        net = yaml.safe_load((root / "network.yaml").read_text())
        for r in net.get("restrictions", []):
            if r["id"] in override:
                r["theta"] = override[r["id"]]
        (work / "network.yaml").write_text(yaml.safe_dump(net, sort_keys=False))


@st.cache_data(show_spinner=False, max_entries=256)
def run_case(
    fixture_key: str,
    measures: tuple[str, ...],
    thetas: tuple[tuple[str, float], ...] = (),
) -> dict:
    """Run one construct-validity profile. Returns a dict, or {"ok": False, ...}."""
    work: Path | None = None
    run_dir: Path | None = None
    try:
        # Inside the try on purpose: an unknown fixture key must come back as a
        # structured error, not a KeyError. The UI only ever passes keys from
        # FIXTURES, but the contract is what the tests hold us to.
        fx = BY_KEY[fixture_key]
        work = _stage_workspace(fx, measures, thetas)
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
        rows.append({"label": f"− {m}", "dropped": m, **run_case(fixture_key, subset, thetas)})
    return {"baseline": baseline, "rows": rows}


def width_of(case: dict) -> float | None:
    if not case.get("ok") or case.get("L") is None or case.get("U") is None:
        return None
    return round(case["U"] - case["L"], 6)
