"""
Toma capturas de pantalla de cada proyecto del portafolio.
Ejecutar: python take_screenshots.py
"""
import os
import subprocess
import time
import threading
import http.server
import socketserver
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("static/images/portfolio")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VIEWPORT = {"width": 1280, "height": 800}


def screenshot_url(page, url, filename, wait_ms=2000, full_page=False):
    try:
        page.goto(url, wait_until="networkidle", timeout=15000)
    except Exception:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=10000)
        except Exception as e:
            print(f"  [ERROR] {url}: {e}")
            return False
    page.wait_for_timeout(wait_ms)
    out = OUTPUT_DIR / filename
    page.screenshot(path=str(out), full_page=full_page, clip={"x": 0, "y": 0, "width": 1280, "height": 720})
    print(f"  [OK] {filename}")
    return True


def serve_static(directory, port):
    """Sirve una carpeta estática en un puerto dado."""
    handler = http.server.SimpleHTTPRequestHandler
    handler.log_message = lambda *a: None  # silenciar logs
    os.chdir(directory)
    with socketserver.TCPServer(("", port), handler) as httpd:
        httpd.serve_forever()


def start_static_server(directory, port):
    t = threading.Thread(target=serve_static, args=(directory, port), daemon=True)
    t.start()
    time.sleep(1.5)


def run_django(project_path, port):
    """Arranca un proyecto Django en background."""
    proc = subprocess.Popen(
        ["python", "manage.py", "runserver", str(port), "--noreload"],
        cwd=project_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    return proc


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport=VIEWPORT)
    page = context.new_page()

    # ── 1. CV Personal (estático) ──────────────────────────────────────
    print("CV Personal...")
    start_static_server("C:/Users/User/Desktop/CV-PERSONAL", 9001)
    screenshot_url(page, "http://localhost:9001/index.html", "cv-personal.jpg", wait_ms=1500)

    # ── 2. Daniela GT (estático) ───────────────────────────────────────
    print("Daniela GT...")
    start_static_server("C:/Users/User/Desktop/daniela GT", 9002)
    screenshot_url(page, "http://localhost:9002/index.html", "daniela-gt.jpg", wait_ms=1500)

    # ── 3. Tiendas / TiendaPos (estático) ─────────────────────────────
    print("TiendaPos...")
    start_static_server("C:/Users/User/Desktop/Tiendas", 9003)
    screenshot_url(page, "http://localhost:9003/index.html", "tiendapos.jpg", wait_ms=2000)

    # ── 4. Trekly (Django) ────────────────────────────────────────────
    print("Trekly...")
    proc_trekly = run_django("C:/Users/User/Desktop/Trekly_02", 9004)
    screenshot_url(page, "http://localhost:9004/", "trekly.jpg", wait_ms=2000)
    proc_trekly.terminate()

    # ── 5. ProJobs (Django) ───────────────────────────────────────────
    print("ProJobs...")
    proc_projobs = run_django("C:/Users/User/Desktop/projobsmejorado", 9005)
    screenshot_url(page, "http://localhost:9005/", "projobs.jpg", wait_ms=2000)
    proc_projobs.terminate()

    # ── 6. FumiElite (Next.js) — intento con build estático ───────────
    print("FumiElite (Next.js)...")
    fumi_out = Path("C:/Users/User/Desktop/fumi delta/.next")
    if fumi_out.exists():
        proc_fumi = subprocess.Popen(
            ["npm", "run", "start"],
            cwd="C:/Users/User/Desktop/fumi delta",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True,
        )
        time.sleep(5)
        screenshot_url(page, "http://localhost:3000/", "fumi-delta.jpg", wait_ms=2500)
        proc_fumi.terminate()
    else:
        proc_fumi = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd="C:/Users/User/Desktop/fumi delta",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True,
        )
        time.sleep(10)
        screenshot_url(page, "http://localhost:3000/", "fumi-delta.jpg", wait_ms=3000)
        proc_fumi.terminate()

    # ── 7. ERP ────────────────────────────────────────────────────────
    # El ERP requiere Docker; intentamos el frontend standalone si existe
    print("ERP...")
    erp_front = Path("C:/Users/User/Desktop/ERP/frontend")
    if erp_front.exists():
        proc_erp = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(erp_front),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True,
        )
        time.sleep(10)
        screenshot_url(page, "http://localhost:3000/", "erp.jpg", wait_ms=3000)
        proc_erp.terminate()
    else:
        print("  [SKIP] ERP frontend no encontrado, usando placeholder")

    browser.close()

print("\nListo. Capturas guardadas en static/images/portfolio/")
