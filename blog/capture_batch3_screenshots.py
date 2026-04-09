"""Capture screenshots from instruction-ordering, constraint-formatting, skeleton-of-thought, step-back, anchoring, and gsd-methodology reports."""

import pathlib
from playwright.sync_api import sync_playwright

RESULTS_DIR = pathlib.Path(__file__).parent.parent / "results"
IMAGES_DIR = pathlib.Path(__file__).parent / "images"

EXPERIMENTS = [
    ("instruction-ordering", "experiment-instruction-ordering-20260325-172249"),
    ("constraint-formatting", "experiment-constraint-formatting-20260326-075910"),
    ("skeleton-of-thought", "experiment-skeleton-of-thought-20260327-083438"),
    ("step-back", "experiment-step-back-20260331-093143"),
    ("anchoring", "experiment-anchoring-20260326-135535"),
    ("gsd-methodology", "experiment-gsd-methodology-20260320-144326"),
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
