#!/usr/bin/env python3
"""Screenshot a Streamlit page, optionally after driving a slider.

Streamlit renders over a websocket, so Chrome's --screenshot fires too early and
captures only the loading skeleton. This drives Chrome over CDP and waits.

Usage: cdp_interact.py <url> <out.png> [--arrows N] [--settle S] [--height H]

--arrows N focuses the first slider and presses ArrowRight N times, which is how
you reach a state the page only shows after interaction.
"""
import argparse
import asyncio
import base64
import json
import os
import urllib.request
from pathlib import Path

import websockets

# Overridable: the user's own Chrome can hold the default 9222, and killing their
# browser to take a screenshot is not an acceptable trade. Use CDP_PORT=9333 instead.
DEBUG_PORT = int(os.environ.get("CDP_PORT", "9222"))


def ws_url() -> str:
    with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/list", timeout=10) as r:
        targets = json.loads(r.read().decode())
    pages = [t for t in targets if t.get("type") == "page"]
    if not pages:
        raise SystemExit("no page target — is Chrome running with --remote-debugging-port?")
    return pages[0]["webSocketDebuggerUrl"]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("out")
    ap.add_argument("--arrows", type=int, default=0)
    ap.add_argument("--click-text", default=None,
                    help="click the first element whose visible text matches, then settle")
    ap.add_argument("--settle", type=float, default=14.0)
    ap.add_argument("--height", type=int, default=1500)
    args = ap.parse_args()

    async with websockets.connect(ws_url(), max_size=64 * 1024 * 1024) as ws:
        n = 0

        async def send(method: str, **params):
            nonlocal n
            n += 1
            await ws.send(json.dumps({"id": n, "method": method, "params": params}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == n:
                    return msg

        await send("Page.enable")
        await send(
            "Emulation.setDeviceMetricsOverride",
            width=1440, height=args.height, deviceScaleFactor=2, mobile=False,
        )
        await send("Page.navigate", url=args.url)
        await asyncio.sleep(args.settle)

        if args.click_text:
            box = await send(
                "Runtime.evaluate",
                returnByValue=True,
                expression=f"""
                  (() => {{
                    const want = {json.dumps(args.click_text)};
                    const els = Array.from(document.querySelectorAll('button, [role="radio"], [role="tab"], label'));
                    const el = els.find(e => (e.textContent || '').trim() === want)
                            || els.find(e => (e.textContent || '').includes(want));
                    if (!el) return null;
                    el.scrollIntoView({{block: 'center'}});
                    const r = el.getBoundingClientRect();
                    return JSON.stringify({{x: r.x + r.width / 2, y: r.y + r.height / 2}});
                  }})()
                """,
            )
            raw = box["result"]["result"]["value"]
            if not raw:
                print(f"  click target not found: {args.click_text!r}")
            else:
                point = json.loads(raw)
                for kind in ("mousePressed", "mouseReleased"):
                    await send(
                        "Input.dispatchMouseEvent",
                        type=kind,
                        x=point["x"],
                        y=point["y"],
                        button="left",
                        clickCount=1,
                    )
                print(f"  clicked {args.click_text!r} at ({point['x']:.0f},{point['y']:.0f})")
                await asyncio.sleep(7)  # rerun + repaint

        if args.arrows:
            found = await send(
                "Runtime.evaluate",
                expression="""
                  (() => {
                    const s = document.querySelector('input[type=range], div[role="slider"], [role="slider"]');
                    if (!s) return 'no-slider';
                    s.focus();
                    return 'focused tag=' + s.tagName + ' value=' + s.value;
                  })()
                """,
                returnByValue=True,
            )
            print("  slider:", found["result"]["result"]["value"])
            for _ in range(args.arrows):
                for key in ("rawKeyDown", "keyUp"):
                    await send(
                        "Input.dispatchKeyEvent",
                        type=key,
                        key="ArrowRight",
                        code="ArrowRight",
                        windowsVirtualKeyCode=39,
                        nativeVirtualKeyCode=39,
                    )
            await asyncio.sleep(6)  # let Streamlit rerun and repaint

            probe = await send(
                "Runtime.evaluate",
                returnByValue=True,
                expression="""
                  (() => {
                    const s = document.querySelector('input[type=range], div[role="slider"], [role="slider"]');
                    return s ? String(s.value) : 'gone';
                  })()
                """,
            )
            value = probe["result"]["result"]["value"]
            print("  value after arrows:", value)
            if value in ("no-slider", "gone", "1", "1.0"):
                # Arrow keys did not move it — set it the React-compatible way:
                # bypass the value setter so React's onChange sees a real event.
                print("  falling back to React-compatible value set")
                await send(
                    "Runtime.evaluate",
                    expression=f"""
                      (() => {{
                        const s = document.querySelector('input[type=range]');
                        if (!s) return 'no-slider';
                        const setter = Object.getOwnPropertyDescriptor(
                          window.HTMLInputElement.prototype, 'value').set;
                        setter.call(s, {args.arrows * 0.1 + 1.0});
                        s.dispatchEvent(new Event('input', {{bubbles: true}}));
                        s.dispatchEvent(new Event('change', {{bubbles: true}}));
                        return 'set to ' + s.value;
                      }})()
                    """,
                )
                await asyncio.sleep(7)

        res = await send("Page.captureScreenshot", format="png", captureBeyondViewport=True)
        data = res.get("result", {}).get("data")
        if not data:
            raise SystemExit(f"capture failed: {json.dumps(res)[:300]}")
        out = Path(args.out)
        out.write_bytes(base64.b64decode(data))
        print(f"  wrote {out} ({out.stat().st_size} bytes)")


asyncio.run(main())