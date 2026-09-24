from playwright.sync_api import sync_playwright
import time
import os

os.makedirs("docs/screenshots", exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    context = browser.new_context(
        viewport={"width": 1600, "height": 1000},
        device_scale_factor=2
    )
    page = context.new_page()

    print("Navigating to http://localhost:8000...")
    page.goto("http://localhost:8000", wait_until="networkidle")
    time.sleep(3)

    # 1. Capture Dashboard / Case Queue
    print("Capturing dashboard.png...")
    page.screenshot(path="docs/screenshots/dashboard.png", full_page=False)

    # 2. Open Investigation Chamber / Entity Dossier
    print("Navigating to Entity Dossier (HHG-001)...")
    try:
        open_btn = page.locator("button:has-text('Open Full Dossier')").first
        if open_btn.is_visible():
            open_btn.click()
        else:
            page.locator("button:has-text('Entity Dossier')").first.click()
        time.sleep(5)
        print("Capturing investigation.png...")
        page.screenshot(path="docs/screenshots/investigation.png", full_page=False)
        print("Capturing room_ring.png...")
        page.screenshot(path="docs/screenshots/room_ring.png", full_page=False)
    except Exception as e:
        print(f"Investigation chamber capture error: {e}")

    # 3. Open FinCEN SAR Regulatory Center
    print("Navigating to SAR Regulatory Center...")
    try:
        sar_btn = page.locator("button:has-text('SAR Regulatory Center')").first
        if sar_btn.is_visible():
            sar_btn.click()
            time.sleep(3)
            print("Capturing sar_hub.png...")
            page.screenshot(path="docs/screenshots/sar_hub.png", full_page=False)
    except Exception as e:
        print(f"SAR center tab click error: {e}")

    # 4. Open Risk Engine Observatory
    print("Navigating to Risk Engine Observatory...")
    try:
        obs_btn = page.locator("button:has-text('Risk Engine Observatory')").first
        if obs_btn.is_visible():
            obs_btn.click()
            time.sleep(3)
            print("Capturing scoreboard.png...")
            page.screenshot(path="docs/screenshots/scoreboard.png", full_page=False)
    except Exception as e:
        print(f"Observatory tab click error: {e}")

    # 5. Open Governance & SOP Policy Engine
    print("Navigating to Governance & SOP...")
    try:
        gov_btn = page.locator("button:has-text('Governance & SOP')").first
        if gov_btn.is_visible():
            gov_btn.click()
            time.sleep(3)
            print("Capturing policy.png...")
            page.screenshot(path="docs/screenshots/policy.png", full_page=False)
    except Exception as e:
        print(f"Governance tab click error: {e}")

    browser.close()
    print("All screenshots successfully captured with TRACER branding!")
