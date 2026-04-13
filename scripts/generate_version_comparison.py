"""
Generate v20.2_vs_v26.0_comparison.json — Lovable-ready side-by-side comparison.

Structure:
  {
    "v20_2": { "us": {...}, "global": {...} },
    "v26_0": { "us": {...}, "global": {...} },
    "delta":  { "us": {...}, "global": {...} }  ← change between versions
  }

Uses ALL reviews for each version from the Deep file (no date cap).
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from CustomerInsight_Review_Agent import analyze_reviews, INSIGHT_CATEGORIES

# ── Config ────────────────────────────────────────────────────────────────────
VERSIONS = {
    "v20_2": {"prefix": "20.2",  "label": "20.2.0.6076"},
    "v26_0": {"prefix": "26.0",  "label": "26.0 (all)"},
}

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT_DIR      = os.path.join(PROJECT_ROOT, "output/insights")
os.makedirs(OUT_DIR, exist_ok=True)

FILES = {
    "us":     os.path.join(PROJECT_ROOT, "data/HP_App_Android_US_Deep.json"),
    "global": os.path.join(PROJECT_ROOT, "data/HP_App_Android_AllCountries_Deep.json"),
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


def build_scope(reviews):
    analysis   = analyze_reviews(reviews)
    metrics    = build_metrics(analysis)
    categories = build_categories(analysis)
    sub_issues = build_sub_issues(analysis)
    return {**metrics, "categories": categories, "sub_issues": sub_issues}


def trend_arrow(delta, metric):
    """Return trend label: improved / worsened / stable."""
    if metric in ("avg_rating", "five_star_pct", "positive_pct"):
        if delta > 0.1:  return "improved"
        if delta < -0.1: return "worsened"
    else:
        if delta < -1:   return "improved"
        if delta > 1:    return "worsened"
    return "stable"


def build_delta(b1, b2):
    """Build delta block comparing two scope blocks (v20.2 → v26.0)."""
    d = {}

    # Top-level metrics
    for key in ("avg_rating", "one_star_pct", "five_star_pct"):
        v1 = b1.get(key, 0)
        v2 = b2.get(key, 0)
        delta = round(v2 - v1, 2)
        d[key] = {"v20_2": v1, "v26_0": v2, "delta": delta,
                  "trend": trend_arrow(delta, key)}

    for sent_key in ("positive_pct", "negative_pct"):
        v1 = b1["sentiment"].get(sent_key, 0)
        v2 = b2["sentiment"].get(sent_key, 0)
        delta = round(v2 - v1, 2)
        d[sent_key] = {"v20_2": v1, "v26_0": v2, "delta": delta,
                       "trend": trend_arrow(delta, sent_key)}

    # Categories
    cats1 = {c["id"]: c for c in b1.get("categories", [])}
    cats2 = {c["id"]: c for c in b2.get("categories", [])}
    all_cat_ids = set(cats1) | set(cats2)
    cat_deltas = []
    for cat_id in all_cat_ids:
        c1 = cats1.get(cat_id, {"pct": 0, "neg_pct": 0, "name": cat_id})
        c2 = cats2.get(cat_id, {"pct": 0, "neg_pct": 0, "name": c1.get("name", cat_id)})
        dpct     = round(c2["pct"]     - c1["pct"],     1)
        dneg_pct = round(c2["neg_pct"] - c1["neg_pct"], 1)
        cat_deltas.append({
            "id":          cat_id,
            "name":        c2.get("name") or c1.get("name", cat_id),
            "v20_2_pct":   c1["pct"],
            "v26_0_pct":   c2["pct"],
            "delta_pct":   dpct,
            "v20_2_neg_pct": c1["neg_pct"],
            "v26_0_neg_pct": c2["neg_pct"],
            "delta_neg_pct": dneg_pct,
            "trend": trend_arrow(dpct, "one_star_pct"),
        })
    cat_deltas.sort(key=lambda x: -max(x["v20_2_pct"], x["v26_0_pct"]))
    d["categories"] = cat_deltas

    # Sub-issues
    subs1 = {s["id"]: s for s in b1.get("sub_issues", [])}
    subs2 = {s["id"]: s for s in b2.get("sub_issues", [])}
    all_sub_ids = set(subs1) | set(subs2)
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sub_deltas = []
    for sub_id in all_sub_ids:
        s1 = subs1.get(sub_id, {"pct": 0, "neg_pct": 0, "severity": "medium"})
        s2 = subs2.get(sub_id, {"pct": 0, "neg_pct": 0, "severity": s1.get("severity", "medium")})
        dpct = round(s2["pct"] - s1["pct"], 1)
        ref  = subs1.get(sub_id) or subs2.get(sub_id)
        sub_deltas.append({
            "id":            sub_id,
            "name":          ref.get("name", sub_id),
            "category":      ref.get("category", ""),
            "category_id":   ref.get("category_id", ""),
            "severity":      ref.get("severity", "medium"),
            "v20_2_pct":     s1["pct"],
            "v26_0_pct":     s2["pct"],
            "delta_pct":     dpct,
            "v20_2_neg_pct": s1["neg_pct"],
            "v26_0_neg_pct": s2["neg_pct"],
            "trend":         trend_arrow(dpct, "one_star_pct"),
        })
    sub_deltas.sort(key=lambda x: (sev_order.get(x["severity"], 4),
                                   -max(x["v20_2_pct"], x["v26_0_pct"])))
    d["sub_issues"] = sub_deltas

    return d


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    print(f"\nGenerating v20.2 vs v26.0 comparison JSON\n")

    scopes = {}  # scopes["v20_2"]["us"] = scope block

    for ver_key, ver_cfg in VERSIONS.items():
        scopes[ver_key] = {}
        for scope, filepath in FILES.items():
            reviews = load_version(filepath, ver_cfg["prefix"])
            print(f"  {ver_key} {scope.upper()}: {len(reviews)} reviews")
            scopes[ver_key][scope] = build_scope(reviews)

    output = {
        "generated_at": datetime.now().isoformat(),
        "note": "All-time reviews per version (no date cap)",
        "versions": {
            "v20_2": VERSIONS["v20_2"]["label"],
            "v26_0": VERSIONS["v26_0"]["label"],
        },
        "v20_2": {
            "us":     scopes["v20_2"]["us"],
            "global": scopes["v20_2"]["global"],
        },
        "v26_0": {
            "us":     scopes["v26_0"]["us"],
            "global": scopes["v26_0"]["global"],
        },
        "delta": {
            "us":     build_delta(scopes["v20_2"]["us"],     scopes["v26_0"]["us"]),
            "global": build_delta(scopes["v20_2"]["global"], scopes["v26_0"]["global"]),
        },
    }

    out_path = os.path.join(OUT_DIR, "v20.2_vs_v26.0_comparison.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {os.path.basename(out_path)}")

    # Summary
    print("\n" + "=" * 60)
    for scope in ("us", "global"):
        d = output["delta"][scope]
        print(f"\n  {scope.upper()} delta (v20.2 → v26.0):")
        print(f"    Avg rating   : {d['avg_rating']['v20_2']}⭐ → {d['avg_rating']['v26_0']}⭐  ({d['avg_rating']['delta']:+.2f})  {d['avg_rating']['trend']}")
        print(f"    1-star %     : {d['one_star_pct']['v20_2']}% → {d['one_star_pct']['v26_0']}%  ({d['one_star_pct']['delta']:+.1f}%)  {d['one_star_pct']['trend']}")
        print(f"    Negative %   : {d['negative_pct']['v20_2']}% → {d['negative_pct']['v26_0']}%  ({d['negative_pct']['delta']:+.1f}%)  {d['negative_pct']['trend']}")

    print("\n  Done.\n")


if __name__ == "__main__":
    run()
