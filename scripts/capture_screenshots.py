from playwright.sync_api import sync_playwright
import time
import os

os.makedirs("docs/screenshots", exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
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

    # 2. Open Investigation Chamber via header button
    print("Navigating to Investigation Chamber...")
    try:
        header_dossier_btn = page.locator("button:has-text('View Dossier')").first
        if header_dossier_btn.is_visible():
            header_dossier_btn.click()
        else:
            page.locator("text=Dossier →").first.click()
        
        # Wait for graph intelligence topology
        page.wait_for_selector("text=Graph Intelligence Topology", timeout=12000)
        time.sleep(5)  # allow cytoscape to layout
        print("Capturing investigation.png...")
        page.screenshot(path="docs/screenshots/investigation.png", full_page=False)
    except Exception as e:
        print(f"Investigation chamber capture error: {e}")

    # 3. Open FinCEN Regulatory Hub
    print("Navigating to FinCEN Regulatory Hub...")
    try:
        sar_nav = page.locator("button:has-text('FinCEN Regulatory Hub')").first
        if sar_nav.is_visible():
            sar_nav.click()
            time.sleep(3)
            print("Capturing sar_hub.png...")
            page.screenshot(path="docs/screenshots/sar_hub.png", full_page=False)
    except Exception as e:
        print(f"FinCEN tab click error: {e}")

    # 4. Open Bayesian Scoreboard
    print("Navigating to Bayesian Scoreboard...")
    try:
        score_nav = page.locator("button:has-text('Bayesian Scoreboard')").first
        if score_nav.is_visible():
            score_nav.click()
            time.sleep(3)
            print("Capturing scoreboard.png...")
            page.screenshot(path="docs/screenshots/scoreboard.png", full_page=False)
    except Exception as e:
        print(f"Scoreboard tab click error: {e}")

    # 5. Open Policy-as-Code Engine
    print("Navigating to Policy-as-Code Engine...")
    try:
        policy_nav = page.locator("button:has-text('Policy-as-Code Engine')").first
        if policy_nav.is_visible():
            policy_nav.click()
            time.sleep(3)
            print("Capturing policy.png...")
            page.screenshot(path="docs/screenshots/policy.png", full_page=False)
    except Exception as e:
        print(f"Policy tab click error: {e}")

    browser.close()
    print("Screenshots captured successfully!")
