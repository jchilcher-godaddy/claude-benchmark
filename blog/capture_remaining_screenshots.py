"""Capture screenshots from persona-sweep, persona-stacking, and capstone-best-practices reports."""

import pathlib
from playwright.sync_api import sync_playwright

RESULTS_DIR = pathlib.Path(__file__).parent.parent / "results"
IMAGES_DIR = pathlib.Path(__file__).parent / "images"

EXPERIMENTS = [
    ("persona-sweep", "experiment-persona-sweep-20260318-130438"),
    ("persona-stacking", "experiment-persona-stacking-20260319-141639"),
    ("capstone-best-practices", "experiment-capstone-best-practices-20260318-145904"),
]

TARGETS = [
    ("executive-summary.png", "#summary"),
    ("statistical-comparison.png", "#statistical"),
    ("heatmap.png", "#heatmap"),
    ("radar-charts.png", "#charts .chart-grid"),
    ("scatter-efficiency.png", "#scatter-efficiency"),
]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        for exp_name, result_dir in EXPERIMENTS:
            report = RESULTS_DIR / result_dir / "report.html"
            out_dir = IMAGES_DIR / exp_name
            out_dir.mkdir(parents=True, exist_ok=True)

            print(f"\n=== {exp_name} ===")
            page.goto(report.resolve().as_uri())
            page.wait_for_timeout(3000)

            for filename, selector in TARGETS:
                el = page.query_selector(selector)
                if el is None:
                    print(f"  WARN: selector '{selector}' not found, skipping {filename}")
                    continue
                tag = el.evaluate("e => e.tagName.toLowerCase()")
                if tag == "canvas":
                    parent = el.evaluate_handle("e => e.closest('.chart-card')").as_element()
                    if parent:
                        el = parent
                dest = out_dir / filename
                el.screenshot(path=str(dest))
                print(f"  Saved {filename}")

        browser.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
