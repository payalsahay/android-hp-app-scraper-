"""Cross-version comparison report: % breakdown of issues across builds."""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from CustomerInsight_Review_Agent import analyze_reviews, INSIGHT_CATEGORIES

VERSIONS = ["26.0.0", "26.0.1", "26.0.2"]

FILES = {
    "US": "data/HP_App_Android_US_Last30Days.json",
    "AllCountries": "data/HP_App_Android_AllCountries_Last30Days.json",
}

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
os.makedirs(os.path.join(PROJECT_ROOT, "output/insights"), exist_ok=True)


def load_filtered(filepath, version_prefix):
    with open(filepath) as f:
        data = json.load(f)
    return [r for r in data if (r.get("version") or "").startswith(version_prefix)]


def generate_comparison(scope_name, filepath):
    # Analyze each version separately
    analyses = {}
    counts = {}
    for v in VERSIONS:
        filtered = load_filtered(filepath, v)
        counts[v] = len(filtered)
        if filtered:
            analyses[v] = analyze_reviews(filtered)
        else:
            analyses[v] = None

    lines = []
    lines.append(f"# HP App v26.x — Cross-Version Issue Comparison ({scope_name})")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Scope:** {scope_name}")
    lines.append("")

    # Review counts & avg ratings
    lines.append("## Overview")
    lines.append("")
    lines.append("| Metric | v26.0.0 | v26.0.1 | v26.0.2 |")
    lines.append("|--------|---------|---------|---------|")
    lines.append(f"| Reviews | {counts['26.0.0']} | {counts['26.0.1']} | {counts['26.0.2']} |")

    for v in VERSIONS:
        a = analyses[v]
        if not a:
            continue
    avg_ratings = {}
    for v in VERSIONS:
        a = analyses[v]
        if a:
            total = a["total_reviews"]
            ratings = a["rating_distribution"]
            avg = sum(r * ratings.get(r, 0) for r in range(1, 6)) / total if total > 0 else 0
            avg_ratings[v] = f"{avg:.2f}⭐"
        else:
            avg_ratings[v] = "N/A"
    lines.append(f"| Avg Rating | {avg_ratings['26.0.0']} | {avg_ratings['26.0.1']} | {avg_ratings['26.0.2']} |")

    # Sentiment
    for label, key in [("Positive %", "positive"), ("Negative %", "negative")]:
        row = f"| {label} |"
        for v in VERSIONS:
            a = analyses[v]
            if a:
                total = a["total_reviews"]
                pct = a["sentiment_counts"].get(key, 0) / total * 100 if total > 0 else 0
                row += f" {pct:.1f}% |"
            else:
                row += " N/A |"
        lines.append(row)

    # 1-star %
    row = "| 1-Star % |"
    for v in VERSIONS:
        a = analyses[v]
        if a:
            total = a["total_reviews"]
            pct = a["rating_distribution"].get(1, 0) / total * 100 if total > 0 else 0
            row += f" {pct:.1f}% |"
        else:
            row += " N/A |"
    lines.append(row)
    lines.append("")

    # Category comparison
    lines.append("---")
    lines.append("")
    lines.append("## Issue Categories — % of Reviews per Version")
    lines.append("")
    lines.append("| Category | v26.0.0 | v26.0.1 | v26.0.2 | Trend |")
    lines.append("|----------|---------|---------|---------|-------|")

    # Collect all categories
    all_cats = list(INSIGHT_CATEGORIES.keys()) + ["uncategorized"]
    for cat_id in all_cats:
        cat_name = INSIGHT_CATEGORIES.get(cat_id, {}).get("name", "Other") if cat_id != "uncategorized" else "Other"
        pcts = []
        for v in VERSIONS:
            a = analyses[v]
            if a and a["total_reviews"] > 0:
                pct = a["category_counts"].get(cat_id, 0) / a["total_reviews"] * 100
                pcts.append(pct)
            else:
                pcts.append(None)

        # Skip if all zero
        if all((p or 0) < 1 for p in pcts):
            continue

        # Trend arrow (v26.0.0 -> v26.0.2)
        if pcts[0] is not None and pcts[2] is not None:
            delta = pcts[2] - pcts[0]
            trend = "📈" if delta > 3 else ("📉" if delta < -3 else "➡️")
        else:
            trend = "—"

        row_vals = []
        for p in pcts:
            row_vals.append(f"{p:.1f}%" if p is not None else "N/A")

        lines.append(f"| {cat_name} | {row_vals[0]} | {row_vals[1]} | {row_vals[2]} | {trend} |")

    lines.append("")

    # Sub-issue comparison
    lines.append("---")
    lines.append("")
    lines.append("## Priority Sub-Issues — % of Reviews per Version")
    lines.append("")
    lines.append("| Sub-Issue | Category | v26.0.0 | v26.0.1 | v26.0.2 | Trend |")
    lines.append("|-----------|----------|---------|---------|---------|-------|")

    # Collect all sub-issues
    sub_rows = []
    for cat_id, cat_info in INSIGHT_CATEGORIES.items():
        cat_name = cat_info.get("name", cat_id)
        subcats_info = cat_info.get("subcategories", {})
        for subcat_id, subcat_def in subcats_info.items():
            subcat_name = subcat_def.get("name", subcat_id)
            severity = subcat_def.get("severity", "medium")
            pcts = []
            for v in VERSIONS:
                a = analyses[v]
                if a and a["total_reviews"] > 0:
                    count = a.get("subcategory_counts", {}).get(cat_id, {}).get(subcat_id, 0)
                    pct = count / a["total_reviews"] * 100
                    pcts.append(pct)
                else:
                    pcts.append(None)

            total_mentions = sum(p for p in pcts if p is not None)
            if total_mentions < 1:
                continue

            sub_rows.append({
                "subcat_name": subcat_name,
                "cat_name": cat_name,
                "severity": severity,
                "pcts": pcts,
            })

    # Sort by severity then by total mentions
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sub_rows.sort(key=lambda x: (severity_order.get(x["severity"], 4), -sum(p for p in x["pcts"] if p is not None)))

    for row in sub_rows:
        pcts = row["pcts"]
        sev_icon = "🔴" if row["severity"] == "critical" else ("🟠" if row["severity"] == "high" else "🟡")

        if pcts[0] is not None and pcts[2] is not None:
            delta = pcts[2] - pcts[0]
            trend = "📈" if delta > 1 else ("📉" if delta < -1 else "➡️")
        else:
            trend = "—"

        row_vals = [f"{p:.1f}%" if p is not None else "N/A" for p in pcts]
        lines.append(
            f"| {sev_icon} {row['subcat_name']} | {row['cat_name']} | "
            f"{row_vals[0]} | {row_vals[1]} | {row_vals[2]} | {trend} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("*📈 increased >1% | 📉 decreased >1% | ➡️ stable across versions*")
    lines.append("")
    lines.append("*Generated by version_comparison.py*")

    return "\n".join(lines)


for scope_name, filepath in FILES.items():
    full_path = os.path.join(PROJECT_ROOT, filepath)
    md = generate_comparison(scope_name, full_path)
    out_path = os.path.join(PROJECT_ROOT, f"output/insights/HP_App_v26x_Comparison_{scope_name}.md")
    with open(out_path, "w") as f:
        f.write(md)
    print(f"Saved: {out_path}")

print("\nDone.")
