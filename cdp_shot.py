#!/usr/bin/env python3
"""Screenshot a local Streamlit page AFTER its websocket session has rendered.

Chrome's --screenshot fires too early for Streamlit: the skeleton paints before the
session delivers the element tree. This drives Chrome over CDP instead, waits for
the load event plus a settle delay, then captures.

Usage: cdp_shot.py <url> <out.png> [settle_seconds] [height]
"""
import asyncio
import base64
import json
import sys
import urllib.request
from pathlib import Path

import websockets

DEBUG_PORT = 9222


def ws_url() -> str:
    with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/list", timeout=10) as r:
        targets = json.loads(r.read().decode())
    pages = [t for t in targets if t.get("type") == "page"]
    if not pages:
        raise SystemExit("no page target — is Chrome running with --remote-debugging-port?")
    return pages[0]["webSocketDebuggerUrl"]


async def capture(url: str, out: Path, settle: float, height: int) -> None:
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
            width=1440,
            height=height,
            deviceScaleFactor=2,
            mobile=False,
        )
        await send("Page.navigate", url=url)
        # let the load event land, then let the Streamlit session render
        await asyncio.sleep(settle)

        res = await send("Page.captureScreenshot", format="png", captureBeyondViewport=True)
        data = res.get("result", {}).get("data")
        if not data:
            raise SystemExit(f"capture failed: {json.dumps(res)[:300]}")
        out.write_bytes(base64.b64decode(data))
        print(f"  wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    url = sys.argv[1]
    out = Path(sys.argv[2])
    settle = float(sys.argv[3]) if len(sys.argv) > 3 else 9.0
    height = int(sys.argv[4]) if len(sys.argv) > 4 else 1600
    asyncio.run(capture(url, out, settle, height))