#!/usr/bin/env python3
"""Headless verification of the demo app.

Two jobs:
  1. Find a configuration that produces an EMPTY admissible set — the state the
     whole demo exists to show, and the one that must not read as a crash.
  2. Drive both pages through Streamlit's AppTest and assert they render without
     an unhandled exception.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.engine import FIXTURES, measures_of, restrictions_of, run_case, width_of  # noqa: E402


def find_empty() -> None:
    print("=" * 70)
    print("1. hunting for an empty-M* configuration (the demo's headline state)")
    print("=" * 70)
    for fx in FIXTURES:
        menu = tuple(measures_of(fx))
        rests = restrictions_of(fx)
        for level in (0.6, 0.8, 0.95, 1.0):
            thetas = tuple((r["id"], level) for r in rests)
            c = run_case(fx.key, menu, thetas)
            if not c.get("ok"):
                print(f"  {fx.key:<9} theta={level:<5} {c['error']}")
                continue
            tag = "EMPTY" if c["empty"] else f"width={width_of(c):.4f}"
            print(f"  {fx.key:<9} theta={level:<5} |M*|={len(c['M_star']):<2} {tag}")
        # also try dropping to a single measure
        for m in menu:
            c = run_case(fx.key, (m,))
            if c.get("ok") and c["empty"]:
                print(f"  {fx.key:<9} single measure {m!r} -> EMPTY")


def apptest() -> None:
    from streamlit.testing.v1 import AppTest

    print()
    print("=" * 70)
    print("2. AppTest — do the pages render without an unhandled exception?")
    print("=" * 70)
    for page in ("streamlit_app.py", "app_pages/run.py", "app_pages/reduction.py"):
        at = AppTest.from_file(str(ROOT / page), default_timeout=120)
        at.run()
        if at.exception:
            print(f"  {page:<28} EXCEPTION")
            for e in at.exception:
                print(f"      {e.type}: {e.message}"[:300])
        else:
            print(f"  {page:<28} ok  | titles={len(at.title)} "
                  f"metrics={len(at.metric)} sliders={len(at.slider)} "
                  f"dataframes={len(at.dataframe)}")


if __name__ == "__main__":
    find_empty()
    apptest()
