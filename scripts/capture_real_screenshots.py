"""
capture_real_screenshots.py
Captures authentic high-resolution desktop (1920x1080) and mobile (390x844)
screenshots directly from the active AutoShorts Web Studio at http://127.0.0.1:8787.
"""
import asyncio
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request
import websockets

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if not os.path.exists(CHROME_PATH):
    CHROME_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

TARGET_URL = "http://127.0.0.1:8787/"
OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "assets" / "screenshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CDP_PORT = 9444

async def cdp_call(ws, method, params=None, msg_id=1):
    req = {"id": msg_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(req))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == msg_id:
            return resp.get("result", {})

async def main():
    print(f"[*] Output directory: {OUT_DIR}")
    temp_profile = tempfile.mkdtemp(prefix="chrome_shot_")
    
    cmd = [
        CHROME_PATH,
        "--headless=new",
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={temp_profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-gpu",
        "--hide-scrollbars",
        TARGET_URL,
    ]
    
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.5)
    
    try:
        # Get target websocket URL from json/list
        page_ws = None
        for _ in range(10):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/list") as r:
                    targets = json.loads(r.read().decode())
                    for t in targets:
                        if t.get("type") == "page":
                            page_ws = t["webSocketDebuggerUrl"]
                            break
                    if page_ws:
                        break
            except Exception:
                time.sleep(0.5)
        
        if not page_ws:
            raise RuntimeError("Could not find page target in Chrome CDP")
            
        print(f"[*] Connected to Chrome CDP target: {page_ws}")
        
        async with websockets.connect(page_ws, max_size=50 * 1024 * 1024) as ws:
            # Enable Page and Runtime
            await cdp_call(ws, "Page.enable", {}, 1)
            await cdp_call(ws, "Runtime.enable", {}, 2)
            
            # Wait for DOM and initial fetch to complete
            await asyncio.sleep(3.0)
            
            # Viewport setup helper
            async def set_viewport(width, height, mobile=False, scale=1.0):
                await cdp_call(ws, "Emulation.setDeviceMetricsOverride", {
                    "width": width,
                    "height": height,
                    "deviceScaleFactor": scale,
                    "mobile": mobile,
                }, 10)
                await asyncio.sleep(0.5)

            async def click_tab(tab_id):
                script = f"""
                (function() {{
                    const el = document.getElementById('{tab_id}');
                    if (el) {{
                        el.click();
                        return true;
                    }}
                    return false;
                }})()
                """
                await cdp_call(ws, "Runtime.evaluate", {"expression": script}, 20)
                await asyncio.sleep(1.2)

            async def capture_png(filename):
                res = await cdp_call(ws, "Page.captureScreenshot", {"format": "png"}, 30)
                img_data = base64.b64decode(res["data"])
                dest = OUT_DIR / filename
                dest.write_bytes(img_data)
                print(f"[+] Saved: {filename} ({len(img_data):,} bytes)")

            # 1. Desktop - Web Studio Dashboard (Overview / Criar)
            print("[*] Capturing web-studio-dashboard.png (1920x1080)...")
            await set_viewport(1920, 1080)
            await click_tab("tab-cortes")
            await capture_png("web-studio-dashboard.png")

            # 2. Desktop - Sentinel Pre-Render QA Panel
            print("[*] Capturing sentinel-pre-render-qa.png (1920x1080)...")
            await click_tab("tab-sentinel")
            await capture_png("sentinel-pre-render-qa.png")

            # 3. Desktop - Video Vault Library
            print("[*] Capturing video-vault-library.png (1920x1080)...")
            await click_tab("tab-videos")
            await capture_png("video-vault-library.png")

            # 4. Desktop - Trends & Radar
            print("[*] Capturing radar-trends.png (1920x1080)...")
            await click_tab("tab-synapse")
            await capture_png("radar-trends.png")

            # 5. Desktop - System Health & Settings
            print("[*] Capturing system-health.png (1920x1080)...")
            await click_tab("tab-sistema")
            await capture_png("system-health.png")

            # 6. Mobile - Web Studio Dashboard (390x844)
            print("[*] Capturing mobile-web-studio-dashboard.png (390x844)...")
            await set_viewport(390, 844, mobile=True, scale=2.0)
            await click_tab("tab-cortes")
            await capture_png("mobile-web-studio-dashboard.png")

            # 7. Mobile - Sentinel QA
            print("[*] Capturing mobile-sentinel-qa.png (390x844)...")
            await click_tab("tab-sentinel")
            await capture_png("mobile-sentinel-qa.png")
            
            # 8. Mobile - Vault
            print("[*] Capturing mobile-video-vault.png (390x844)...")
            await click_tab("tab-videos")
            await capture_png("mobile-video-vault.png")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
        print("[*] Chrome process terminated cleanly.")

if __name__ == "__main__":
    asyncio.run(main())
