"""
Generate baseline comparison file for a given version.

Uses ALL reviews for the version from the Deep file (no date cap),
so the baseline remains valid even after the next release ships.

Includes:
- Overall metrics (avg rating, star distribution, sentiment)
- Category breakdown with neg%
- Sub-issue breakdown with severity
- Country volume breakdown
- Pass/fail thresholds for next release scoring
- Lovable-ready JSON in the same schema as v20.2_issues_all_time.json
"""

import json
import os
import sys
from datetime import datetime
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from CustomerInsight_Review_Agent import analyze_reviews, INSIGHT_CATEGORIES

# ── Config ────────────────────────────────────────────────────────────────────
VERSION_PREFIX = "20.2"          # filters reviews starting with this string
VERSION_LABEL  = "20.2.0.6076"  # display label

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT_DIR = os.path.join(PROJECT_ROOT, "output/insights/v20.2_baseline")
os.makedirs(OUT_DIR, exist_ok=True)

FILES = {
    "us":     os.path.join(PROJECT_ROOT, "data/HP_App_Android_US_Deep.json"),
    "global": os.path.join(PROJECT_ROOT, "data/HP_App_Android_AllCountries_Deep.json"),
}

# Thresholds: new release must beat baseline by at least this delta to be 🟢
IMPROVEMENT_DELTA = {
    "avg_rating":    0.15,
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


def avg_rating(analysis):
    total = analysis["total_reviews"]
    dist  = analysis["rating_distribution"]
    return sum(r * dist.get(r, 0) for r in range(1, 6)) / total if total > 0 else 0


def country_breakdown(reviews):
    counts = Counter(r.get("country", "unknown") for r in reviews)
    total  = len(reviews)
    return {
        country: {"count": count, "pct": round(count / total * 100, 1)}
        for country, count in counts.most_common()
    }


def build_scope_block(reviews, analysis, scope_label):
    total = analysis["total_reviews"]
    dist  = analysis["rating_distribution"]
    sent  = analysis["sentiment_counts"]

    ar        = avg_rating(analysis)
    one_star  = dist.get(1, 0) / total * 100
    five_star = dist.get(5, 0) / total * 100
    pos_pct   = sent.get("positive", 0) / total * 100
    neg_pct   = sent.get("negative", 0) / total * 100
    neu_pct   = sent.get("neutral",  0) / total * 100

    # Categories
    categories = []
    for cat_id, cat_info in INSIGHT_CATEGORIES.items():
        count = analysis["category_counts"].get(cat_id, 0)
        if count == 0:
            continue
        pct     = count / total * 100
        cat_sent = analysis["category_sentiment"].get(cat_id, {})
        neg      = cat_sent.get("negative", 0)
        pos      = cat_sent.get("positive", 0)
        categories.append({
            "id":      cat_id,
            "name":    cat_info.get("name", cat_id),
            "count":   count,
            "pct":     round(pct, 1),
            "neg_pct": round(neg / count * 100, 1) if count else 0,
            "pos_pct": round(pos / count * 100, 1) if count else 0,
        })
    categories.sort(key=lambda x: -x["count"])

    # Sub-issues
    sub_issues = []
    for cat_id, cat_info in INSIGHT_CATEGORIES.items():
        for subcat_id, subcat_def in cat_info.get("subcategories", {}).items():
            count = analysis.get("subcategory_counts", {}).get(cat_id, {}).get(subcat_id, 0)
            if count == 0:
                continue
            pct      = count / total * 100
            sub_sent = analysis.get("subcategory_sentiment", {}).get(cat_id, {}).get(subcat_id, {})
            neg      = sub_sent.get("negative", 0)
            pos      = sub_sent.get("positive", 0)
            sub_issues.append({
                "id":        subcat_id,
                "name":      subcat_def.get("name", subcat_id),
                "category":  cat_info.get("name", cat_id),
                "category_id": cat_id,
                "severity":  subcat_def.get("severity", "medium"),
                "count":     count,
                "pct":       round(pct, 1),
                "neg_pct":   round(neg / count * 100, 1) if count else 0,
                "pos_pct":   round(pos / count * 100, 1) if count else 0,
            })
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sub_issues.sort(key=lambda x: (sev_order.get(x["severity"], 4), -x["count"]))

    # Thresholds for next release
    thresholds = {
        "avg_rating_must_exceed":      round(ar, 2),
        "one_star_pct_must_be_below":  round(one_star, 1),
        "negative_pct_must_be_below":  round(neg_pct, 1),
        "improvement_target": {
            "avg_rating":    round(ar + IMPROVEMENT_DELTA["avg_rating"], 2),
            "one_star_pct":  round(one_star + IMPROVEMENT_DELTA["one_star_pct"], 1),
            "negative_pct":  round(neg_pct  + IMPROVEMENT_DELTA["negative_pct"], 1),
        },
        "category_thresholds": {
            cat["id"]: {
                "name":               cat["name"],
                "pct_must_be_below":  round(cat["pct"] + abs(IMPROVEMENT_DELTA["category_pct"]), 1),
                "neg_pct_must_be_below": round(cat["neg_pct"] + abs(IMPROVEMENT_DELTA["neg_pct"]), 1),
            }
            for cat in categories
        },
    }

    return {
        "scope":        scope_label,
        "total_reviews": total,
        "date_range":   "All-time (no date cap — full version lifecycle)",
        "avg_rating":   round(ar, 2),
        "one_star_pct": round(one_star, 1),
        "five_star_pct": round(five_star, 1),
        "sentiment": {
            "positive_pct": round(pos_pct, 1),
            "negative_pct": round(neg_pct, 1),
            "neutral_pct":  round(neu_pct, 1),
        },
        "rating_distribution": {
            str(r): {"count": dist.get(r, 0), "pct": round(dist.get(r, 0) / total * 100, 1)}
            for r in range(5, 0, -1)
        },
        "country_breakdown": country_breakdown(reviews),
        "thresholds":   thresholds,
        "categories":   categories,
        "sub_issues":   sub_issues,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    print(f"\nGenerating baseline for v{VERSION_LABEL} (all-time reviews)\n")

    scope_blocks = {}
    review_sets  = {}

    for scope, filepath in FILES.items():
        reviews = load_version(filepath, VERSION_PREFIX)
        review_sets[scope] = reviews
        print(f"  {scope.upper()}: {len(reviews)} reviews for v{VERSION_PREFIX}*")

        if not reviews:
            print(f"  WARNING: no reviews found for {scope}, skipping")
            continue

        analysis = analyze_reviews(reviews)
        scope_blocks[scope] = build_scope_block(reviews, analysis, scope.upper())

    # ── 1. Baseline comparison template (for scoring next release) ────────────
    template = {
        "meta": {
            "baseline_version": VERSION_LABEL,
            "baseline_type":    "all_time",
            "note":             (
                "Baseline uses ALL reviews for this version (no date cap). "
                "This remains valid after the next release ships because version "
                "reviews don't age out of the Deep file."
            ),
            "generated_at": datetime.now().isoformat(),
            "how_to_use": {
                "green":  "next_release_value better than threshold",
                "yellow": "next_release_value within 5% of threshold",
                "red":    "next_release_value worse than threshold — regression",
            },
        },
        "us":     scope_blocks.get("us", {}),
        "global": scope_blocks.get("global", {}),
        "next_release": {
            "version":     None,
            "scored_at":   None,
            "us":          {},
            "global":      {},
        },
    }

    template_path = os.path.join(OUT_DIR, "v20.2_baseline_comparison_template.json")
    with open(template_path, "w") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {os.path.basename(template_path)}")

    # ── 2. Lovable-ready JSON (same schema as v20.2_issues_all_time.json) ─────
    lovable = {
        "version":        VERSION_LABEL,
        "scenario_id":    "all_time",
        "scenario_label": "All Time (full version lifecycle)",
        "baseline_type":  "all_time",
        "generated_at":   datetime.now().isoformat(),
        "us":             scope_blocks.get("us", {}),
        "global":         scope_blocks.get("global", {}),
    }

    lovable_path = os.path.join(OUT_DIR, "v20.2_issues_all_time.json")
    with open(lovable_path, "w") as f:
        json.dump(lovable, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {os.path.basename(lovable_path)}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    for scope, block in scope_blocks.items():
        print(f"\n  {scope.upper()} — {block['total_reviews']} reviews")
        print(f"    Avg rating : {block['avg_rating']}⭐")
        print(f"    1-star %   : {block['one_star_pct']}%")
        print(f"    Negative % : {block['sentiment']['negative_pct']}%")
        print(f"    Countries  : {list(block['country_breakdown'].keys())}")
    print("\n  Done.\n")


if __name__ == "__main__":
    run()
