"""Invariant tests for the demo's engine wrapper (``core/engine.py``).

These assert the *documented* contracts of the thin wrapper over the published
``cvprofiles==3.0.2`` engine, so the app is safe to deploy publicly:

* the headline number the demo advertises is reproducible from the real engine;
* a menu subset is a different validated input (different ``run_id``);
* leave-one-out has the documented shape, and the same measures are
  load-bearing / inert every time;
* the "empty" finding is reachable and is *not* an error;
* the wrapper cleans up its temp workspace and run dir on every path;
* the wrapper returns a structured error dict instead of raising.

No Streamlit runtime is needed: the cached functions fall back to an in-memory
cache and merely log a "No runtime found" warning, which is not a failure.

Run with::

    .venv/bin/python -m pytest tests/test_engine.py -v
"""

from __future__ import annotations

import glob
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Import the app's package without requiring an editable install.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import engine as E  # noqa: E402

FIXTURE = "wvs_gps"

# Ground truth, confirmed against the real engine.
EXPECTED_MEASURES = (
    "m_gps_patience",
    "m_wvs_q13",
    "m_wvs_q14",
    "m_composite",
    "m_prompt_a",
    "m_prompt_b",
    "m_noise",
)
EXPECTED_RESTRICTIONS = ("conv_edu", "mono_edu", "disc_risk")
LOAD_BEARING = {"m_gps_patience", "m_prompt_a"}
INERT = {"m_wvs_q13", "m_wvs_q14", "m_composite", "m_prompt_b", "m_noise"}
FULL_L = 0.3275
FULL_U = 0.4025


def _full_menu() -> tuple[str, ...]:
    return tuple(E.measures_of(E.BY_KEY[FIXTURE]))


def _rows_by_dropped(loo: dict) -> dict[str | None, dict]:
    return {r["dropped"]: r for r in loo["rows"]}


def _snapshot_cvp_dirs() -> set[str]:
    """Basenames of every ``cvp_*`` dir in the system temp dir, right now."""
    tmp = tempfile.gettempdir()
    return {os.path.basename(p) for p in glob.glob(os.path.join(tmp, "cvp_*"))}


# --------------------------------------------------------------------------
# Fixture metadata (the ground truth the rest of the suite rests on).
# --------------------------------------------------------------------------
def test_fixture_metadata_matches_documentation():
    fx = E.BY_KEY[FIXTURE]
    assert E.measures_of(fx) == list(EXPECTED_MEASURES)
    assert tuple(r["id"] for r in E.restrictions_of(fx)) == EXPECTED_RESTRICTIONS
    # Every restriction is a real, staged constraint.
    for r in E.restrictions_of(fx):
        assert r["type"]
        assert r["stage"]
        assert isinstance(r["theta"], float)


# --------------------------------------------------------------------------
# 1. The advertised headline number is reproducible.
# --------------------------------------------------------------------------
def test_reproduces_the_documented_headline():
    case = E.run_case(FIXTURE, _full_menu())

    assert case["ok"] is True, case
    assert case["empty"] is False, case
    assert case["n_measures"] == len(EXPECTED_MEASURES)

    # |M*| == 2
    assert len(case["M_star"]) == 2, case

    # L / U match the documented values, both raw and rounded to 4dp.
    assert case["L"] == pytest.approx(FULL_L, abs=1e-3)
    assert case["U"] == pytest.approx(FULL_U, abs=1e-3)
    assert round(case["L"], 4) == pytest.approx(FULL_L, abs=1e-9)
    assert round(case["U"], 4) == pytest.approx(FULL_U, abs=1e-9)

    # Width is the headline the demo shows.
    assert E.width_of(case) == pytest.approx(0.07496, abs=1e-4)

    # The provenance hashes are non-empty strings.
    for key in ("run_id", "scores_hash", "network_hash", "beta_hash"):
        assert isinstance(case[key], str) and case[key], (key, case[key])


# --------------------------------------------------------------------------
# 2. A subset is a different validated input (provenance contract).
# --------------------------------------------------------------------------
def test_subsetting_changes_the_run_id():
    menu = _full_menu()
    full = E.run_case(FIXTURE, menu)
    subset = E.run_case(FIXTURE, tuple(m for m in menu if m != "m_noise"))

    assert full["ok"] is True and subset["ok"] is True
    assert full["n_measures"] == 7 and subset["n_measures"] == 6
    assert full["run_id"] != subset["run_id"]

    # And the truncated menu really changed the scores fed to the engine.
    assert full["scores_hash"] != subset["scores_hash"]


# --------------------------------------------------------------------------
# 3. Leave-one-out shape.
# --------------------------------------------------------------------------
def test_leave_one_out_shape():
    loo = E.leave_one_out(FIXTURE)
    rows = loo["rows"]

    # 1 baseline + one row per measure.
    assert len(rows) == 1 + len(EXPECTED_MEASURES) == 8

    baseline_rows = [r for r in rows if r["label"] == "full menu"]
    assert len(baseline_rows) == 1
    assert baseline_rows[0]["dropped"] is None
    assert baseline_rows[0]["ok"] is True

    # The baseline row *is* the full-menu run.
    full = E.run_case(FIXTURE, _full_menu())
    assert baseline_rows[0]["run_id"] == full["run_id"]

    # Exactly one row per measure, each labelled and carrying that measure.
    dropped = [r["dropped"] for r in rows if r["dropped"] is not None]
    assert sorted(dropped) == sorted(EXPECTED_MEASURES)
    for r in rows:
        if r["dropped"] is not None:
            assert r["label"] == f"− {r['dropped']}"

    assert loo["baseline"]["run_id"] == full["run_id"]


# --------------------------------------------------------------------------
# 4. The two load-bearing measures are exactly the ones that collapse width.
# --------------------------------------------------------------------------
def test_load_bearing_measures_are_identified():
    rows = _rows_by_dropped(E.leave_one_out(FIXTURE))

    collapsed = set()
    for measure, row in rows.items():
        if measure is None:
            continue
        assert row["ok"] is True, (measure, row)
        width = E.width_of(row)
        assert width is not None, (measure, row)
        if width == 0.0 and len(row["M_star"]) == 1:
            collapsed.add(measure)

    assert collapsed == LOAD_BEARING


# --------------------------------------------------------------------------
# 5. The five inert measures leave the width and the reported set unchanged.
# --------------------------------------------------------------------------
def test_inert_measures_are_inert():
    loo = E.leave_one_out(FIXTURE)
    rows = _rows_by_dropped(loo)
    baseline = rows[None]
    baseline_width = E.width_of(baseline)
    baseline_M = list(baseline["M_star"])

    assert baseline_width is not None and baseline_width > 0.0
    assert len(baseline_M) == 2

    unchanged = set()
    for measure, row in rows.items():
        if measure is None:
            continue
        width = E.width_of(row)
        assert width is not None, (measure, row)
        # Inert means: same width (to the wrapper's 6dp rounding) AND same |M*|.
        if width == baseline_width and len(row["M_star"]) == 2:
            unchanged.add(measure)

    assert unchanged == INERT

    # Explicitly: the width delta for each inert drop is exactly zero, at the
    # same rounding the wrapper exposes.
    for measure in INERT:
        w = E.width_of(rows[measure])
        assert w is not None, measure
        assert round(w - baseline_width, 6) == 0.0, measure
        assert set(rows[measure]["M_star"]) == set(baseline_M), measure


# --------------------------------------------------------------------------
# 6. The empty menu state is reachable, and is a finding, not an error.
# --------------------------------------------------------------------------
def test_empty_menu_is_reachable_and_is_not_an_error():
    thetas = tuple((r["id"], 0.6) for r in E.restrictions_of(E.BY_KEY[FIXTURE]))
    assert len(thetas) == 3

    case = E.run_case(FIXTURE, _full_menu(), thetas)

    assert case["ok"] is True, case            # a finding, NOT an error
    assert case["empty"] is True, case
    assert case["M_star"] == [], case
    assert case["L"] is None and case["U"] is None, case
    assert "error" not in case, case
    assert E.width_of(case) is None            # guarded for the empty case


# --------------------------------------------------------------------------
# 7. No temp dirs leak, including on the error path.
# --------------------------------------------------------------------------
def test_no_temp_dirs_leak():
    menu = _full_menu()
    before = _snapshot_cvp_dirs()

    # Prove the detector is not vacuous: a planted cvp_* dir must show up as new.
    probe = Path(tempfile.gettempdir()) / "cvp_case_leakdetector_probe"
    probe.mkdir(exist_ok=True)
    try:
        assert str(probe.name) in (_snapshot_cvp_dirs() - before)
    finally:
        probe.rmdir()
    assert _snapshot_cvp_dirs() == before

    # Unique theta payloads guarantee cache misses, so each call really runs
    # the engine and really creates (and must remove) its dirs.
    ok_case = E.run_case(FIXTURE, menu, (("__leak_probe__", 0.101),))
    assert ok_case["ok"] is True, ok_case

    # The failing case: an input the engine refuses, exercising the error path.
    bad_case = E.run_case(FIXTURE, (), (("__leak_probe__", 0.202),))
    assert bad_case["ok"] is False, bad_case

    # A modified case too: a different surviving measure set.
    subset_case = E.run_case(
        FIXTURE, tuple(m for m in menu if m != "m_prompt_b"), (("__leak_probe__", 0.303),)
    )
    assert subset_case["ok"] is True, subset_case

    after = _snapshot_cvp_dirs()
    leaked = sorted(after - before)
    assert leaked == [], f"temp dirs left behind: {leaked}"


def test_documented_workspace_prefixes_are_cleaned_up():
    """The wrapper's own dirs (cvp_case_*, cvp_run_*) must not survive a call."""
    before = _snapshot_cvp_dirs()
    E.run_case(FIXTURE, _full_menu(), (("__leak_probe__", 0.404),))
    after = _snapshot_cvp_dirs()
    ours = {"cvp_case_", "cvp_run_"}
    new_ours = [
        name for name in (after - before) if any(name.startswith(p) for p in ours)
    ]
    assert new_ours == []


# --------------------------------------------------------------------------
# 8. Bad input is reported, never raised.
# --------------------------------------------------------------------------
def test_bad_input_returns_a_structured_error():
    """The wrapper must return a dict, not raise, for every input shape.

    FINDING (see module report): contrary to the original hypothesis, neither
    ``('m_noise',)`` nor ``('m_gps_patience',)`` makes the engine refuse the
    input. Both are *accepted*: a lone inert measure yields the empty state and
    a lone load-bearing measure yields a degenerate singleton ``M*`` with
    ``L == U``. The refusal path is real, but it triggers only when the menu
    leaves **zero** surviving measures. This test pins that behaviour down.
    """
    # (a) Neither of the two hypothesised measures is refused — no exception,
    #     a dict comes back, and the engine reports a valid (possibly empty)
    #     result. Whichever way the engine behaves, it must be structured.
    for measure in ("m_noise", "m_gps_patience"):
        case = E.run_case(FIXTURE, (measure,))
        assert isinstance(case, dict), (measure, case)
        assert "ok" in case, (measure, case)
        assert case["ok"] is True, (measure, case)
        assert "error" not in case, (measure, case)
        if measure == "m_noise":
            assert case["empty"] is True and case["M_star"] == [], case
        else:
            assert case["M_star"] == ["m_gps_patience"], case
            assert case["L"] == case["U"], case  # degenerate, width 0

    # (b) The structured-error contract IS real and reachable: an input whose
    #     measure menu survives as zero measures makes the engine refuse.
    for bad in ((), ("m_does_not_exist",)):
        case = E.run_case(FIXTURE, bad)
        assert isinstance(case, dict), bad
        assert case["ok"] is False, (bad, case)
        assert isinstance(case["error"], str) and case["error"], (bad, case)
        assert case["error"] == "ValidationError", (bad, case)
        assert isinstance(case.get("detail"), str), (bad, case)


def test_error_shape_is_complete():
    """Every non-ok result carries the documented {ok, error, detail} keys."""
    case = E.run_case(FIXTURE, ())
    assert set(case) == {"ok", "error", "detail"}, case
    assert case["ok"] is False
    assert case["error"]
    assert case["detail"]  # a non-empty human-readable explanation


def test_unknown_fixture_key_returns_a_structured_error():
    """Regression: an unknown fixture key must not raise.

    ``BY_KEY[fixture_key]`` used to sit *outside* the try block, so a bad key
    escaped as a KeyError and broke the "always returns a dict" contract. The UI
    only ever passes keys from FIXTURES, but the contract is the contract.
    """
    case = E.run_case("no_such_fixture", ("m_noise",))
    assert isinstance(case, dict), case
    assert case["ok"] is False, case
    assert case["error"] == "KeyError", case
    assert isinstance(case["detail"], str) and case["detail"], case


def test_user_authored_aux_anchored_network_runs():
    """A network a user writes from scratch is a first-class input."""
    served = E.rows_to_restrictions(E.default_restrictions(E.BY_KEY[FIXTURE]))
    assert len(served) == 3, served
    case = E.run_custom(
        FIXTURE, tuple(E.measures_of(E.BY_KEY[FIXTURE])), json.dumps(served, sort_keys=True)
    )
    assert case["ok"] is True, case


def test_measure_anchored_network_breaks_the_reduction_curve():
    """The builder's central lesson, pinned as a contract.

    A restriction bound to an AUXILIARY column survives every single-measure removal.
    Bind one to a MEASURE instead and the removal of that measure is refused, because
    the restriction would point at a column that no longer exists. This is why the
    page can promise the reduction curve for one network shape and not the other --
    if this test ever fails, the page is lying to the reader.
    """
    fx = E.BY_KEY[FIXTURE]
    menu = tuple(E.measures_of(fx))
    spec = E.rows_to_restrictions(E.default_restrictions(fx))

    # aux-anchored: leave-one-out is clean, and nothing is classified as measure-anchored
    aux = E.leave_one_out_custom(FIXTURE, json.dumps(spec, sort_keys=True))
    assert all(r.get("ok") for r in aux["rows"]), aux["rows"]
    assert all(E.anchor_class(r, menu) != "measure" for r in spec), spec

    # bind one restriction to a measure
    measured = [
        *spec,
        {
            "id": "u_meas",
            "type": "corr_min",
            "theta": 0.10,
            "params": {"variable": menu[0]},
            "stage": "select",
        },
    ]
    assert E.anchor_class(measured[-1], menu) == "measure"

    loo = E.leave_one_out_custom(FIXTURE, json.dumps(measured, sort_keys=True))
    refused = [r for r in loo["rows"] if not r.get("ok")]
    assert len(refused) == 1, refused
    assert refused[0]["dropped"] == menu[0], refused
    assert refused[0]["error"] == "RestrictError", refused
    # the damage is specific: every OTHER removal still runs
    assert len(loo["rows"]) - 1 - len(refused) == len(menu) - 1, loo["rows"]
