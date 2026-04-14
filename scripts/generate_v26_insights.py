"""
Generate v26.0_US_Insights.json — all v26.0 reviews from Deep file.
Matches the schema of HP_App_v26.0.1_US_Insights.json used by Lovable Sheet 3.
"""

import json
import os
import sys
from datetime import datetime
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from CustomerInsight_Review_Agent import analyze_reviews, INSIGHT_CATEGORIES

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT_PATH = os.path.join(PROJECT_ROOT, "output/reports/v26.0_US_Insights.json")


def load_version(filepath, prefix):
    with open(filepath) as f:
        data = json.load(f)
    return [r for r in data if (r.get("version") or "").startswith(prefix)]


def sample_reviews(reviews, cat_id, analysis, n=4):
    """Pick sample reviews that were tagged to this category."""
    samples = []
    for r in reviews:
        cats = r.get("_categories", [])
        if cat_id in cats:
            samples.append({
                "rating":    r.get("rating", 0),
                "title":     r.get("title", ""),
                "snippet":   (r.get("content") or "")[:200],
                "sentiment": r.get("_sentiment", "neutral"),
                "version":   r.get("version", ""),
                "date":      (r.get("date") or "")[:10],
            })
    random.shuffle(samples)
    return samples[:n]


def run():
    us_deep = os.path.join(PROJECT_ROOT, "data/HP_App_Android_US_Deep.json")
    reviews = load_version(us_deep, "26.0")
    print(f"v26.0 US reviews: {len(reviews)}")

    from collections import Counter
    versions = Counter(r.get("version") for r in reviews)
    print("Version breakdown:", versions.most_common())

    analysis = analyze_reviews(reviews)
    total    = analysis["total_reviews"]
    dist     = analysis["rating_distribution"]
    sent     = analysis["sentiment_counts"]

    avg_rating = sum(r * dist.get(r, 0) for r in range(1, 6)) / total if total else 0

    # Build categories block matching existing schema
    categories = {}
    for cat_id, cat_info in INSIGHT_CATEGORIES.items():
        count = analysis["category_counts"].get(cat_id, 0)
        if count == 0:
            continue
        cat_sent = analysis["category_sentiment"].get(cat_id, {})

        # Sub-issues for this category
        sub_issues = {}
        for subcat_id, subcat_def in cat_info.get("subcategories", {}).items():
            sc_count = analysis.get("subcategory_counts", {}).get(cat_id, {}).get(subcat_id, 0)
            if sc_count == 0:
                continue
            sc_sent = analysis.get("subcategory_sentiment", {}).get(cat_id, {}).get(subcat_id, {})
            sub_issues[subcat_id] = {
                "name":       subcat_def.get("name", subcat_id),
                "severity":   subcat_def.get("severity", "medium"),
                "count":      sc_count,
                "pct":        round(sc_count / total * 100, 1),
                "neg_pct":    round(sc_sent.get("negative", 0) / sc_count * 100, 1) if sc_count else 0,
            }

        categories[cat_id] = {
            "name":               cat_info.get("name", cat_id),
            "mention_count":      count,
            "percentage_of_total": round(count / total * 100, 1),
            "sentiment": {
                "positive": cat_sent.get("positive", 0),
                "negative": cat_sent.get("negative", 0),
                "neutral":  cat_sent.get("neutral",  0),
            },
            "neg_pct": round(cat_sent.get("negative", 0) / count * 100, 1) if count else 0,
            "sub_issues": sub_issues,
        }

    output = {
        "generated_at":   datetime.now().isoformat(),
        "version":        "26.0 (all sub-versions)",
        "version_breakdown": {v: c for v, c in versions.most_common()},
        "scope":          "US",
        "total_reviews":  total,
        "avg_rating":     round(avg_rating, 2),
        "sentiment_summary": {
            "positive": sent.get("positive", 0),
            "negative": sent.get("negative", 0),
            "neutral":  sent.get("neutral",  0),
            "positive_pct": round(sent.get("positive", 0) / total * 100, 1) if total else 0,
            "negative_pct": round(sent.get("negative", 0) / total * 100, 1) if total else 0,
        },
        "rating_distribution": {
            str(r): {"count": dist.get(r, 0), "pct": round(dist.get(r, 0) / total * 100, 1)}
            for r in range(5, 0, -1)
        },
        "one_star_pct":  round(dist.get(1, 0) / total * 100, 1) if total else 0,
        "five_star_pct": round(dist.get(5, 0) / total * 100, 1) if total else 0,
        "categories": categories,
    }

    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {os.path.basename(OUT_PATH)}")
    print(f"  Total reviews : {total}")
    print(f"  Avg rating    : {output['avg_rating']}⭐")
    print(f"  1-star %      : {output['one_star_pct']}%")
    print(f"  Negative %    : {output['sentiment_summary']['negative_pct']}%")


if __name__ == "__main__":
    run()
