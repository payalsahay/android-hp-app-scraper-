"""
Generate v20.2_baseline.json — single source of truth for Lovable baseline dashboard.

Contains:
- All-time metrics (avg rating, star distribution, sentiment)
- Category breakdown
- Sub-issue breakdown (by severity)
- Monthly trend (Dec 2025 → Apr 2026)
- Pass/fail thresholds for next release scoring
- Empty new_release slot (populated when next version ships)

Run this script to regenerate after each fresh scrape.
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from CustomerInsight_Review_Agent import analyze_reviews, INSIGHT_CATEGORIES

# ── Config ────────────────────────────────────────────────────────────────────
VERSION_PREFIX = "20.2"
VERSION_LABEL  = "20.2.0.6076"

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT_DIR      = os.path.join(PROJECT_ROOT, "output/insights/v20.2_baseline")
os.makedirs(OUT_DIR, exist_ok=True)

FILES = {
    "us":     os.path.join(PROJECT_ROOT, "data/HP_App_Android_US_Deep.json"),
    "global": os.path.join(PROJECT_ROOT, "data/HP_App_Android_AllCountries_Deep.json"),
}

MONTHS = [
    ("dec_2025", "Dec 2025", "2025-12"),
    ("jan_2026", "Jan 2026", "2026-01"),
    ("feb_2026", "Feb 2026", "2026-02"),
    ("mar_2026", "Mar 2026", "2026-03"),
    ("apr_2026", "Apr 2026", "2026-04"),
]

# New release must beat baseline by this delta to score 🟢
IMPROVEMENT_DELTA = {
    "avg_rating":   0.15,
    "one_star_pct": -5.0,
    "negative_pct": -5.0,
    "category_pct": -3.0,
    "neg_pct":      -5.0,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_version(filepath, prefix):
    with open(filepath) as f:
        data = json.load(f)
    return [r for r in data if (r.get("version") or "").startswith(prefix)]


def calc_avg_rating(analysis):
    total = analysis["total_reviews"]
    dist  = analysis["rating_distribution"]
    return round(sum(r * dist.get(r, 0) for r in range(1, 6)) / total, 2) if total else 0


def build_metrics(analysis):
    total = analysis["total_reviews"]
    dist  = analysis["rating_distribution"]
    sent  = analysis["sentiment_counts"]
    return {
        "total_reviews":  total,
        "avg_rating":     calc_avg_rating(analysis),
        "one_star_pct":   round(dist.get(1, 0) / total * 100, 1) if total else 0,
        "five_star_pct":  round(dist.get(5, 0) / total * 100, 1) if total else 0,
        "sentiment": {
            "positive_pct": round(sent.get("positive", 0) / total * 100, 1) if total else 0,
            "negative_pct": round(sent.get("negative", 0) / total * 100, 1) if total else 0,
            "neutral_pct":  round(sent.get("neutral",  0) / total * 100, 1) if total else 0,
        },
        "rating_distribution": {
            str(r): {"count": dist.get(r, 0), "pct": round(dist.get(r, 0) / total * 100, 1)}
            for r in range(5, 0, -1)
        },
    }


def build_categories(analysis):
    total = analysis["total_reviews"]
    rows  = []
    for cat_id, cat_info in INSIGHT_CATEGORIES.items():
        count = analysis["category_counts"].get(cat_id, 0)
        if count == 0:
            continue
        cat_sent = analysis["category_sentiment"].get(cat_id, {})
        neg = cat_sent.get("negative", 0)
        pos = cat_sent.get("positive", 0)
        rows.append({
            "id":      cat_id,
            "name":    cat_info.get("name", cat_id),
            "count":   count,
            "pct":     round(count / total * 100, 1),
            "neg_pct": round(neg / count * 100, 1) if count else 0,
            "pos_pct": round(pos / count * 100, 1) if count else 0,
        })
    rows.sort(key=lambda x: -x["count"])
    return rows


def build_sub_issues(analysis):
    total = analysis["total_reviews"]
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    rows = []
    for cat_id, cat_info in INSIGHT_CATEGORIES.items():
        for subcat_id, subcat_def in cat_info.get("subcategories", {}).items():
            count = analysis.get("subcategory_counts", {}).get(cat_id, {}).get(subcat_id, 0)
            if count == 0:
                continue
            sub_sent = analysis.get("subcategory_sentiment", {}).get(cat_id, {}).get(subcat_id, {})
            neg = sub_sent.get("negative", 0)
            pos = sub_sent.get("positive", 0)
            rows.append({
                "id":          subcat_id,
                "name":        subcat_def.get("name", subcat_id),
                "category":    cat_info.get("name", cat_id),
                "category_id": cat_id,
                "severity":    subcat_def.get("severity", "medium"),
                "count":       count,
                "pct":         round(count / total * 100, 1),
                "neg_pct":     round(neg / count * 100, 1) if count else 0,
                "pos_pct":     round(pos / count * 100, 1) if count else 0,
            })
    rows.sort(key=lambda x: (sev_order.get(x["severity"], 4), -x["count"]))
    return rows


def build_monthly_trend(all_reviews):
    trend = []
    for scenario_id, label, month_prefix in MONTHS:
        month_reviews = [r for r in all_reviews if r.get("date", "").startswith(month_prefix)]
        if not month_reviews:
            trend.append({"month": scenario_id, "label": label, "total": 0})
            continue
        analysis = analyze_reviews(month_reviews)
        metrics  = build_metrics(analysis)
        trend.append({
            "month":        scenario_id,
            "label":        label,
            "total":        metrics["total_reviews"],
            "avg_rating":   metrics["avg_rating"],
            "one_star_pct": metrics["one_star_pct"],
            "five_star_pct": metrics["five_star_pct"],
            "sentiment":    metrics["sentiment"],
        })
    return trend


def build_thresholds(metrics, categories):
    return {
        "note": "New release must exceed these values to avoid regression (🔴)",
        "avg_rating_must_exceed":     metrics["avg_rating"],
        "one_star_pct_must_be_below": metrics["one_star_pct"],
        "negative_pct_must_be_below": metrics["sentiment"]["negative_pct"],
        "improvement_target": {
            "avg_rating":    round(metrics["avg_rating"]              + IMPROVEMENT_DELTA["avg_rating"],   2),
            "one_star_pct":  round(metrics["one_star_pct"]            + IMPROVEMENT_DELTA["one_star_pct"], 1),
            "negative_pct":  round(metrics["sentiment"]["negative_pct"] + IMPROVEMENT_DELTA["negative_pct"], 1),
        },
        "category_thresholds": {
            cat["id"]: {
                "name":                  cat["name"],
                "pct_must_be_below":     round(cat["pct"]     + abs(IMPROVEMENT_DELTA["category_pct"]), 1),
                "neg_pct_must_be_below": round(cat["neg_pct"] + abs(IMPROVEMENT_DELTA["neg_pct"]),      1),
            }
            for cat in categories
        },
    }


def build_scope_block(reviews):
    analysis   = analyze_reviews(reviews)
    metrics    = build_metrics(analysis)
    categories = build_categories(analysis)
    sub_issues = build_sub_issues(analysis)
    trend      = build_monthly_trend(reviews)
    thresholds = build_thresholds(metrics, categories)

    return {
        **metrics,
        "categories":    categories,
        "sub_issues":    sub_issues,
        "monthly_trend": trend,
        "thresholds":    thresholds,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    print(f"\nGenerating v20.2_baseline.json for v{VERSION_LABEL}\n")

    scope_blocks = {}
    for scope, filepath in FILES.items():
        reviews = load_version(filepath, VERSION_PREFIX)
        print(f"  {scope.upper()}: {len(reviews)} reviews")
        scope_blocks[scope] = build_scope_block(reviews)

    output = {
        "version":      VERSION_LABEL,
        "generated_at": datetime.now().isoformat(),
        "note":         (
            "All-time reviews for this version (no date cap). "
            "Remains valid after next release ships."
        ),
        "us":     scope_blocks["us"],
        "global": scope_blocks["global"],
        "new_release": {
            "version": None,
            "scored_at": None,
            "note": "Populated when next release ships — run score_release.py",
            "us":     {},
            "global": {},
        },
    }

    out_path = os.path.join(OUT_DIR, "v20.2_baseline.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {os.path.basename(out_path)}")

    # Print summary
    print("\n" + "=" * 60)
    for scope, block in scope_blocks.items():
        print(f"\n  {scope.upper()} — {block['total_reviews']} reviews")
        print(f"    Avg rating  : {block['avg_rating']}⭐")
        print(f"    1-star %    : {block['one_star_pct']}%")
        print(f"    Negative %  : {block['sentiment']['negative_pct']}%")
        print(f"    Monthly trend:")
        for m in block["monthly_trend"]:
            if m["total"] > 0:
                print(f"      {m['label']:10} {m['total']:4} reviews  {m['avg_rating']}⭐  {m['one_star_pct']}% 1-star")
    print("\n  Done.\n")


if __name__ == "__main__":
    run()
