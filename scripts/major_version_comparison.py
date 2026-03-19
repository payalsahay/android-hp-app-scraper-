"""Compare v20.2 vs v26.0 (all sub-versions) — US and Global."""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from CustomerInsight_Review_Agent import analyze_reviews, INSIGHT_CATEGORIES

VERSIONS = {
    "v20.2": ("20.2",),
    "v26.0": ("26.0.0", "26.0.1", "26.0.2"),
}

FILES = {
    "US": "data/HP_App_Android_US_Deep.json",
    "AllCountries": "data/HP_App_Android_AllCountries_Deep.json",
}

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
os.makedirs(os.path.join(PROJECT_ROOT, "output/insights"), exist_ok=True)


def load_filtered(filepath, prefixes):
    with open(filepath) as f:
        data = json.load(f)
    return [r for r in data if (r.get("version") or "").startswith(prefixes)]


def avg_rating(analysis):
    total = analysis["total_reviews"]
    ratings = analysis["rating_distribution"]
    return sum(r * ratings.get(r, 0) for r in range(1, 6)) / total if total > 0 else 0


def generate_comparison(scope_name, filepath):
    analyses = {}
    counts = {}
    for label, prefixes in VERSIONS.items():
        filtered = load_filtered(filepath, prefixes)
        counts[label] = len(filtered)
        analyses[label] = analyze_reviews(filtered) if filtered else None

    v1, v2 = "v20.2", "v26.0"
    a1, a2 = analyses[v1], analyses[v2]

    lines = []
    lines.append(f"# HP App — v20.2 vs v26.0 Comparison ({scope_name})")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Scope:** {scope_name}")
    lines.append("")

    # Overview
    lines.append("---")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append("| Metric | v20.2 | v26.0 (all) | Change |")
    lines.append("|--------|-------|-------------|--------|")

    lines.append(f"| Reviews | {counts[v1]} | {counts[v2]} | — |")

    ar1 = avg_rating(a1)
    ar2 = avg_rating(a2)
    delta = ar2 - ar1
    arrow = "📉" if delta < -0.1 else ("📈" if delta > 0.1 else "➡️")
    lines.append(f"| Avg Rating | {ar1:.2f}⭐ | {ar2:.2f}⭐ | {delta:+.2f} {arrow} |")

    for label, key in [("Positive %", "positive"), ("Negative %", "negative")]:
        p1 = a1["sentiment_counts"].get(key, 0) / a1["total_reviews"] * 100
        p2 = a2["sentiment_counts"].get(key, 0) / a2["total_reviews"] * 100
        d = p2 - p1
        arrow = "📈" if d > 2 else ("📉" if d < -2 else "➡️")
        lines.append(f"| {label} | {p1:.1f}% | {p2:.1f}% | {d:+.1f}% {arrow} |")

    for star in [1, 5]:
        p1 = a1["rating_distribution"].get(star, 0) / a1["total_reviews"] * 100
        p2 = a2["rating_distribution"].get(star, 0) / a2["total_reviews"] * 100
        d = p2 - p1
        arrow = "📈" if d > 2 else ("📉" if d < -2 else "➡️")
        lines.append(f"| {star}-Star % | {p1:.1f}% | {p2:.1f}% | {d:+.1f}% {arrow} |")

    lines.append("")

    # Category comparison
    lines.append("---")
    lines.append("")
    lines.append("## Issue Categories — % of Reviews")
    lines.append("")
    lines.append(f"*v20.2 total: {a1['total_reviews']} reviews | v26.0 total: {a2['total_reviews']} reviews*")
    lines.append("")
    lines.append("| Category | v20.2 reviews | v20.2 % (neg%) | v26.0 reviews | v26.0 % (neg%) | Change | Trend |")
    lines.append("|----------|---------------|----------------|---------------|----------------|--------|-------|")

    all_cats = list(INSIGHT_CATEGORIES.keys()) + ["uncategorized"]
    cat_rows = []
    for cat_id in all_cats:
        cat_name = INSIGHT_CATEGORIES.get(cat_id, {}).get("name", "Other") if cat_id != "uncategorized" else "Other"
        c1 = a1["category_counts"].get(cat_id, 0)
        c2 = a2["category_counts"].get(cat_id, 0)
        p1 = c1 / a1["total_reviews"] * 100
        p2 = c2 / a2["total_reviews"] * 100
        if p1 < 1 and p2 < 1:
            continue
        d = p2 - p1
        arrow = "📈" if d > 3 else ("📉" if d < -3 else "➡️")

        n1 = a1["category_sentiment"].get(cat_id, {}).get("negative", 0)
        n2 = a2["category_sentiment"].get(cat_id, {}).get("negative", 0)
        neg1 = f"{n1/c1*100:.0f}%" if c1 > 0 else "—"
        neg2 = f"{n2/c2*100:.0f}%" if c2 > 0 else "—"

        cat_rows.append((abs(d), cat_name, c1, p1, c2, p2, d, arrow, neg1, neg2))

    cat_rows.sort(key=lambda x: -max(x[3], x[5]))
    for _, cat_name, c1, p1, c2, p2, d, arrow, neg1, neg2 in cat_rows:
        lines.append(f"| {cat_name} | {c1} | {p1:.1f}% (neg:{neg1}) | {c2} | {p2:.1f}% (neg:{neg2}) | {d:+.1f}% | {arrow} |")

    lines.append("")

    # Sub-issue comparison
    lines.append("---")
    lines.append("")
    lines.append("## Priority Sub-Issues — % of Reviews")
    lines.append("")
    lines.append(f"*v20.2 total: {a1['total_reviews']} reviews | v26.0 total: {a2['total_reviews']} reviews*")
    lines.append("")
    lines.append("| Sub-Issue | Category | v20.2 reviews | v20.2 % | v26.0 reviews | v26.0 % | Change | Trend |")
    lines.append("|-----------|----------|---------------|---------|---------------|---------|--------|-------|")

    sub_rows = []
    for cat_id, cat_info in INSIGHT_CATEGORIES.items():
        cat_name = cat_info.get("name", cat_id)
        subcats_info = cat_info.get("subcategories", {})
        for subcat_id, subcat_def in subcats_info.items():
            subcat_name = subcat_def.get("name", subcat_id)
            severity = subcat_def.get("severity", "medium")

            c1 = a1.get("subcategory_counts", {}).get(cat_id, {}).get(subcat_id, 0)
            c2 = a2.get("subcategory_counts", {}).get(cat_id, {}).get(subcat_id, 0)
            p1 = c1 / a1["total_reviews"] * 100
            p2 = c2 / a2["total_reviews"] * 100

            if p1 < 0.5 and p2 < 0.5:
                continue

            d = p2 - p1
            arrow = "📈" if d > 1 else ("📉" if d < -1 else "➡️")

            sub_rows.append({
                "subcat_name": subcat_name,
                "cat_name": cat_name,
                "severity": severity,
                "c1": c1, "p1": p1,
                "c2": c2, "p2": p2,
                "d": d,
                "arrow": arrow,
            })

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sub_rows.sort(key=lambda x: (severity_order.get(x["severity"], 4), -max(x["p1"], x["p2"])))

    for row in sub_rows:
        sev_icon = "🔴" if row["severity"] == "critical" else ("🟠" if row["severity"] == "high" else "🟡")
        lines.append(
            f"| {sev_icon} {row['subcat_name']} | {row['cat_name']} | "
            f"{row['c1']} | {row['p1']:.1f}% | {row['c2']} | {row['p2']:.1f}% | {row['d']:+.1f}% | {row['arrow']} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("*📈 worsened | 📉 improved | ➡️ stable (threshold: categories >3%, sub-issues >1%)*")
    lines.append("")
    lines.append("*Generated by major_version_comparison.py*")

    return "\n".join(lines)


for scope_name, filepath in FILES.items():
    full_path = os.path.join(PROJECT_ROOT, filepath)
    md = generate_comparison(scope_name, full_path)
    out_path = os.path.join(PROJECT_ROOT, f"output/insights/HP_App_v20.2_vs_v26.0_Comparison_{scope_name}.md")
    with open(out_path, "w") as f:
        f.write(md)
    print(f"Saved: {out_path}")

print("\nDone.")
