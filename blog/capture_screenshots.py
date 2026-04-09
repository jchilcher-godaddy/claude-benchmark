"""Capture screenshots from the politeness-sweep experiment report."""

import pathlib
from playwright.sync_api import sync_playwright

REPORT = pathlib.Path(__file__).parent.parent / "results" / "experiment-politeness-sweep-combined" / "report.html"
OUT_DIR = pathlib.Path(__file__).parent / "images" / "politeness-sweep"

TARGETS = [
    ("executive-summary.png", "#summary"),
    ("statistical-comparison.png", "#statistical"),
    ("heatmap.png", "#heatmap"),
    ("radar-charts.png", "#charts .chart-grid"),
    ("composite-bar.png", "#bar-composite"),
    ("scatter-efficiency.png", "#scatter-efficiency"),
]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report_url = REPORT.resolve().as_uri()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(report_url)
        # Wait for Chart.js canvases to render
        page.wait_for_timeout(3000)

        for filename, selector in TARGETS:
            el = page.query_selector(selector)
            if el is None:
                print(f"WARN: selector '{selector}' not found, skipping {filename}")
                continue
            # For canvas elements, screenshot the parent .chart-card
            tag = el.evaluate("e => e.tagName.toLowerCase()")
            if tag == "canvas":
                parent = el.evaluate_handle("e => e.closest('.chart-card')").as_element()
                if parent:
                    el = parent
            dest = OUT_DIR / filename
            el.screenshot(path=str(dest))
            print(f"Saved {dest.relative_to(pathlib.Path.cwd())}")

        browser.close()
    print("Done.")


if __name__ == "__main__":
    main()
