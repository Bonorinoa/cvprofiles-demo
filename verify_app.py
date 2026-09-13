#!/usr/bin/env python3
"""Headless verification of the demo app.

Two jobs:
  1. Find a configuration that produces an EMPTY admissible set — the state the
     whole demo exists to show, and the one that must not read as a crash.
  2. Drive every page through Streamlit's AppTest, *inside the router*, and assert it
     renders without an unhandled exception.

Why through the router rather than each page standalone: in production the pages run
under ``st.navigation``, and some elements only resolve there. ``st.page_link`` raises
``StreamlitPageNotFoundError`` outside a navigation context, so a standalone check is
both less faithful and less strict than this one.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.engine import FIXTURES, measures_of, restrictions_of, run_case, width_of  # noqa: E402

PAGES = (
    "app_pages/run.py",
    "app_pages/reduction.py",
    "app_pages/build_network.py",
    "app_pages/failure_mode.py",
    "app_pages/method.py",
)


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
    print("2. AppTest — every page, through the router (the production path)")
    print("=" * 70)

    router = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=180)
    router.run()
    if router.exception:
        print("  streamlit_app.py             EXCEPTION (router itself)")
        for e in router.exception:
            print(f"      {e.type}: {e.message}"[:300])
        return
    print(f"  {'streamlit_app.py':<28} ok  | title={[t.value for t in router.title][:1]}")

    failures = 0
    for page in PAGES:
        at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=180)
        at.session_state["_probe"] = None
        at.switch_page(page)
        at.run()
        if at.exception:
            failures += 1
            print(f"  {page:<28} EXCEPTION")
            for e in at.exception:
                print(f"      {e.type}: {e.message}"[:300])
        else:
            print(
                f"  {page:<28} ok  | titles={len(at.title)} metrics={len(at.metric)} "
                f"dataframes={len(at.dataframe)}"
            )
    print(f"\n  {len(PAGES) - failures}/{len(PAGES)} pages clean")


if __name__ == "__main__":
    find_empty()
    apptest()
