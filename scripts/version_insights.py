"""Generate top issues report filtered by app version."""

import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from CustomerInsight_Review_Agent import (
    analyze_reviews, save_insights_json, INSIGHT_CATEGORIES
)

VERSION_PREFIX = "26.0.1"

FILES = {
    "HP_App_v26.0.1_US": "data/HP_App_Android_US_Last30Days.json",
    "HP_App_v26.0.1_AllCountries": "data/HP_App_Android_AllCountries_Last30Days.json",
}

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
os.makedirs(os.path.join(PROJECT_ROOT, "output/insights"), exist_ok=True)
os.makedirs(os.path.join(PROJECT_ROOT, "output/reports"), exist_ok=True)


def generate_report(name, filtered, analysis):
    total = len(filtered)
    ratings = analysis["rating_distribution"]
    sent = analysis["sentiment_counts"]
    avg_rating = sum(r * ratings.get(r, 0) for r in range(1, 6)) / total if total > 0 else 0
    pos_pct = sent.get("positive", 0) / total * 100
    neg_pct = sent.get("negative", 0) / total * 100

    lines = []
    lines.append(f"# {name.replace('_', ' ')} — Top Issues Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Version:** {VERSION_PREFIX}")
    lines.append(f"**Reviews Analyzed:** {total}")
    lines.append(f"**Average Rating:** {avg_rating:.2f} / 5.0")
    lines.append(f"**Positive Sentiment:** {pos_pct:.1f}% | **Negative:** {neg_pct:.1f}%")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Rating Distribution")
    lines.append("")
    lines.append("| Stars | Count | % |")
    lines.append("|-------|-------|---|")
    for r in range(5, 0, -1):
        c = ratings.get(r, 0)
        lines.append(f"| {'⭐' * r} | {c} | {c/total*100:.1f}% |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Top Issue Categories")
    lines.append("")
    lines.append("| Rank | Category | Mentions | % of Reviews | Neg % |")
    lines.append("|------|----------|----------|--------------|-------|")
    for rank, (cat_id, count) in enumerate(analysis["category_counts"].most_common(10), 1):
        if cat_id == "uncategorized":
            cat_name = "Other"
        else:
            cat_name = INSIGHT_CATEGORIES.get(cat_id, {}).get("name", cat_id)
        pct = count / total * 100
        cat_sent = analysis["category_sentiment"].get(cat_id, {})
        neg = cat_sent.get("negative", 0)
        neg_pct_cat = neg / count * 100 if count > 0 else 0
        lines.append(f"| {rank} | {cat_name} | {count} | {pct:.1f}% | {neg_pct_cat:.0f}% |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Priority Sub-Issues")
    lines.append("")
    lines.append("| Priority | Sub-Issue | Category | Mentions | Neg % | Severity |")
    lines.append("|----------|-----------|----------|----------|-------|----------|")

    subcategory_counts = analysis.get("subcategory_counts", {})
    subcategory_sentiment = analysis.get("subcategory_sentiment", {})
    priority_issues = []

    for cat_id in subcategory_counts:
        cat_info = INSIGHT_CATEGORIES.get(cat_id, {})
        subcats_info = cat_info.get("subcategories", {})
        for subcat_id, subcat_count in subcategory_counts[cat_id].items():
            if subcat_id == "other":
                continue
            subcat_def = subcats_info.get(subcat_id, {})
            severity = subcat_def.get("severity", "medium")
            subcat_name = subcat_def.get("name", subcat_id)
            subcat_sent = subcategory_sentiment.get(cat_id, {}).get(subcat_id, {})
            neg_count = subcat_sent.get("negative", 0)
            neg_ratio = neg_count / subcat_count if subcat_count > 0 else 0
            priority_issues.append({
                "category": cat_info.get("name", cat_id),
                "subcategory": subcat_name,
                "count": subcat_count,
                "severity": severity,
                "neg_ratio": neg_ratio,
            })

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    priority_issues.sort(key=lambda x: (severity_order.get(x["severity"], 4), -x["count"]))

    for i, issue in enumerate(priority_issues[:10], 1):
        sev_icon = "🔴" if issue["severity"] == "critical" else ("🟠" if issue["severity"] == "high" else "🟡")
        lines.append(
            f"| {i} | {issue['subcategory']} | {issue['category']} | "
            f"{issue['count']} | {issue['neg_ratio']*100:.0f}% | {sev_icon} {issue['severity'].upper()} |"
        )

    return "\n".join(lines)


for name, filepath in FILES.items():
    full_path = os.path.join(PROJECT_ROOT, filepath)
    with open(full_path) as f:
        data = json.load(f)

    filtered = [r for r in data if (r.get("version") or "").startswith(VERSION_PREFIX)]
    print(f"\n{name}: {len(filtered)} reviews on v{VERSION_PREFIX}")

    analysis = analyze_reviews(filtered)
    save_insights_json(analysis, os.path.join(PROJECT_ROOT, f"output/reports/{name}_Insights.json"), silent=True)

    md = generate_report(name, filtered, analysis)
    md_path = os.path.join(PROJECT_ROOT, f"output/insights/{name}_Insights.md")
    with open(md_path, "w") as f:
        f.write(md)
    print(f"Saved: {md_path}")

print("\nDone.")
