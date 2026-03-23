"""
================================================================================
Weekly Android Scraper - HP App Google Play Reviews
================================================================================

Runs every Friday at 8AM PST via GitHub Actions.

COLLECTS:
1. Android US - Last 30 days rolling
2. Android All Countries - Last 30 days rolling
3. Android US - Last 500 reviews

FEATURES:
- Deduplication: Appends new reviews, removes duplicates by review ID
- Rolling window: Keeps only reviews within date range for 30-day data
- Runs CustomerInsight_Review_Agent for analysis
- Commits all changes to GitHub

Author: Payal
Version: 1.0
Created: January 2026

================================================================================
"""

import json
import csv
import os
import sys
from datetime import datetime, timedelta
from collections import Counter
import time

# ============================================================================
# CONFIGURATION
# ============================================================================

APP_CONFIG = {
    "package_id": "com.hp.printercontrol",
    "app_name": "HP Smart",
    "display_name": "HP App",
}

# Countries for multi-country scraping
ALL_COUNTRIES = [
    "us", "gb", "ca", "au", "in", "de", "fr", "jp", "br", "mx",
    "es", "it", "nl", "se", "sg"
]

# Language mapping for Google Play
COUNTRY_LANGUAGE_MAP = {
    "us": "en", "gb": "en", "ca": "en", "au": "en", "in": "en",
    "de": "de", "fr": "fr", "jp": "ja", "br": "pt", "mx": "es",
    "es": "es", "it": "it", "nl": "nl", "se": "sv", "sg": "en",
}

# Rate limiting
REQUEST_DELAY = 1.0

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
INSIGHTS_DIR = os.path.join(OUTPUT_DIR, "insights")
REPORTS_DIR = os.path.join(OUTPUT_DIR, "reports")

# Ensure directories exist
for d in [DATA_DIR, INSIGHTS_DIR, REPORTS_DIR]:
    os.makedirs(d, exist_ok=True)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def load_existing_reviews(filepath):
    """Load existing reviews from JSON file"""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_reviews(reviews, filepath):
    """Save reviews to JSON file"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(reviews, f, indent=2, ensure_ascii=False, default=str)
    print(f"  Saved {len(reviews)} reviews to {os.path.basename(filepath)}")


def save_to_csv(reviews, filepath):
    """Save reviews to CSV file"""
    if not reviews:
        return

    fieldnames = ["id", "author", "rating", "title", "content", "version",
                  "date", "country", "platform", "vote_count"]

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(reviews)
    print(f"  Saved CSV to {os.path.basename(filepath)}")


def deduplicate_reviews(existing, new_reviews):
    """
    Merge reviews: add new, keep unique by ID.
    Returns deduplicated list sorted by date (newest first).
    """
    reviews_by_id = {}

    # Add existing reviews
    for review in existing:
        review_id = str(review.get('id', ''))
        if review_id:
            reviews_by_id[review_id] = review

    # Add/update with new reviews
    added_count = 0
    for review in new_reviews:
        review_id = str(review.get('id', ''))
        if review_id and review_id not in reviews_by_id:
            added_count += 1
        if review_id:
            reviews_by_id[review_id] = review

    # Sort by date (newest first)
    all_reviews = list(reviews_by_id.values())
    all_reviews.sort(key=lambda x: x.get('date', ''), reverse=True)

    print(f"  Added {added_count} new reviews, total: {len(all_reviews)}")
    return all_reviews


def filter_reviews_by_date(reviews, days_back):
    """Filter reviews to only include those within the date range"""
    cutoff_date = datetime.now() - timedelta(days=days_back)
    filtered = []

    for review in reviews:
        date_str = review.get('date', '')
        if date_str:
            try:
                if 'T' in date_str:
                    review_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    if review_date.tzinfo:
                        review_date = review_date.replace(tzinfo=None)
                else:
                    review_date = datetime.strptime(date_str[:10], '%Y-%m-%d')

                if review_date >= cutoff_date:
                    filtered.append(review)
            except (ValueError, TypeError):
                filtered.append(review)

    print(f"  Filtered to {len(filtered)} reviews (last {days_back} days)")
    return filtered


def generate_analytics(reviews, country, days=None):
    """Generate analytics summary"""
    if not reviews:
        return None

    total = len(reviews)
    ratings = [r.get('rating', 0) for r in reviews if r.get('rating')]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0

    rating_dist = Counter(ratings)
    version_dist = Counter(r.get('version', 'unknown') for r in reviews if r.get('version'))
    country_dist = Counter(r.get('country', 'unknown') for r in reviews)

    dates = [r.get('date', '')[:10] for r in reviews if r.get('date')]

    analytics = {
        "scrape_date": datetime.now().isoformat(),
        "total_reviews": total,
        "avg_rating": round(avg_rating, 2),
        "rating_distribution": dict(sorted(rating_dist.items(), reverse=True)),
        "version_distribution": dict(version_dist.most_common(10)),
        "country_distribution": dict(country_dist.most_common(15)),
        "one_star_count": rating_dist.get(1, 0),
        "one_star_pct": round(rating_dist.get(1, 0) / total * 100, 1) if total > 0 else 0,
        "five_star_count": rating_dist.get(5, 0),
        "five_star_pct": round(rating_dist.get(5, 0) / total * 100, 1) if total > 0 else 0,
        "platform": "Google Play",
        "country": country,
        "date_range": {
            "from": min(dates) if dates else None,
            "to": max(dates) if dates else None,
        }
    }

    if days:
        analytics["days"] = days

    return analytics


# ============================================================================
# ANDROID SCRAPERS
# ============================================================================

def scrape_android_reviews(country="us", max_reviews=500):
    """Scrape Google Play Store reviews"""
    print(f"\n  Scraping Android reviews for {country.upper()}...")

    try:
        from google_play_scraper import reviews, Sort
    except ImportError:
        print("  ERROR: google-play-scraper not installed")
        return []

    lang = COUNTRY_LANGUAGE_MAP.get(country, "en")
    all_reviews = []
    continuation_token = None
    batch_size = 100

    try:
        fetched = 0
        while fetched < max_reviews:
            result, continuation_token = reviews(
                APP_CONFIG["package_id"],
                lang=lang,
                country=country,
                sort=Sort.NEWEST,
                count=min(batch_size, max_reviews - fetched),
                continuation_token=continuation_token
            )

            if not result:
                break

            for review in result:
                review_date = review.get('at')
                all_reviews.append({
                    "id": review.get("reviewId", ""),
                    "author": review.get("userName", "Unknown"),
                    "rating": review.get("score", 0),
                    "title": "",
                    "content": review.get("content", ""),
                    "version": review.get("reviewCreatedVersion", ""),
                    "date": review_date.isoformat() if review_date else "",
                    "country": country,
                    "platform": "Google Play",
                    "vote_count": review.get("thumbsUpCount", 0),
                    "reply_content": review.get("replyContent", ""),
                })

            fetched += len(result)

            if continuation_token is None:
                break

            time.sleep(REQUEST_DELAY)

        print(f"  Fetched {len(all_reviews)} Android reviews from {country.upper()}")
        return all_reviews

    except Exception as e:
        print(f"  Error scraping Android {country}: {e}")
        return all_reviews


def scrape_android_all_countries(max_reviews_per_country=500):
    """Scrape Android reviews from all configured countries"""
    all_reviews = []

    for country in ALL_COUNTRIES:
        reviews = scrape_android_reviews(country, max_reviews=max_reviews_per_country)
        all_reviews.extend(reviews)
        time.sleep(REQUEST_DELAY)

    return all_reviews


# ============================================================================
# INSIGHTS AGENT
# ============================================================================

def run_insights_agent(reviews_file, output_name):
    """Run the CustomerInsight_Review_Agent on a data file"""
    print(f"\n  Running Insights Agent on {os.path.basename(reviews_file)}...")

    sys.path.insert(0, PROJECT_ROOT)
    try:
        from CustomerInsight_Review_Agent import load_reviews, analyze_reviews, save_insights_json, INSIGHT_CATEGORIES
    except ImportError:
        print("  ERROR: CustomerInsight_Review_Agent not found")
        return None

    reviews = load_reviews(reviews_file)
    if not reviews:
        print("  No reviews to analyze")
        return None

    analysis = analyze_reviews(reviews)

    json_output = os.path.join(REPORTS_DIR, f"{output_name}_Insights.json")
    save_insights_json(analysis, json_output)

    md_output = os.path.join(INSIGHTS_DIR, f"{output_name}_Insights.md")
    generate_insights_markdown(analysis, reviews_file, md_output, output_name)

    return analysis


def generate_insights_markdown(analysis, source_file, output_file, title):
    """Generate a markdown insights report"""
    total = analysis["total_reviews"]
    sent = analysis["sentiment_counts"]
    ratings = analysis["rating_distribution"]

    pos_pct = sent.get("positive", 0) / total * 100 if total > 0 else 0
    neg_pct = sent.get("negative", 0) / total * 100 if total > 0 else 0

    avg_rating = sum(r * c for r, c in ratings.items()) / total if total > 0 else 0

    report = f"""# {title} - Customer Insights Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Source:** {os.path.basename(source_file)}
**Platform:** Google Play Store
**Total Reviews:** {total}

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Reviews | {total} |
| Average Rating | {avg_rating:.2f} / 5.0 |
| Positive Sentiment | {pos_pct:.1f}% |
| Negative Sentiment | {neg_pct:.1f}% |
| 1-Star Reviews | {ratings.get(1, 0)} ({ratings.get(1, 0)/total*100:.1f}%) |
| 5-Star Reviews | {ratings.get(5, 0)} ({ratings.get(5, 0)/total*100:.1f}%) |

---

## Rating Distribution

| Stars | Count | Percentage |
|-------|-------|------------|
"""

    for star in range(5, 0, -1):
        count = ratings.get(star, 0)
        pct = count / total * 100 if total > 0 else 0
        report += f"| {star} | {count} | {pct:.1f}% |\n"

    report += """
---

## Top Issue Categories

| Rank | Category | Mentions | % of Reviews |
|------|----------|----------|--------------|
"""

    sys.path.insert(0, PROJECT_ROOT)
    try:
        from CustomerInsight_Review_Agent import INSIGHT_CATEGORIES
    except ImportError:
        INSIGHT_CATEGORIES = {}

    for rank, (cat_id, count) in enumerate(analysis["category_counts"].most_common(10), 1):
        if cat_id == "uncategorized":
            cat_name = "Other"
        else:
            cat_name = INSIGHT_CATEGORIES.get(cat_id, {}).get("name", cat_id)
        pct = count / total * 100 if total > 0 else 0
        report += f"| {rank} | {cat_name} | {count} | {pct:.1f}% |\n"

    report += f"""
---

## Critical Pain Points

"""

    for cat_id, count in analysis["category_counts"].most_common(10):
        if cat_id != "uncategorized":
            cat_sent = analysis["category_sentiment"].get(cat_id, {})
            neg_ratio = cat_sent.get("negative", 0) / count if count > 0 else 0
            if neg_ratio > 0.4:
                cat_name = INSIGHT_CATEGORIES.get(cat_id, {}).get("name", cat_id)
                report += f"- **{cat_name}**: {neg_ratio*100:.0f}% negative sentiment ({count} mentions)\n"

    report += """
---

*Generated by CustomerInsight_Review_Agent v1.1*
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"  Saved insights report to {os.path.basename(output_file)}")


# ============================================================================
# MAIN WEEKLY SCRAPER
# ============================================================================

def run_weekly_scrape():
    """
    Main weekly scraping function.

    Collects:
    1. Android US - Last 30 days rolling
    2. Android All Countries - Last 30 days rolling
    3. Android US - Last 500 reviews
    """
    print("\n" + "="*70)
    print("  WEEKLY ANDROID SCRAPER - HP App (Google Play)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*70)

    results = {}

    # -------------------------------------------------------------------------
    # 1. Android US - Last 30 Days Rolling
    # -------------------------------------------------------------------------
    print("\n" + "-"*70)
    print("  [1/4] Android US - Last 30 Days Rolling")
    print("-"*70)

    android_us_30d_file = os.path.join(DATA_DIR, "HP_App_Android_US_Last30Days.json")
    existing_android_us_30d = load_existing_reviews(android_us_30d_file)

    new_android_us = scrape_android_reviews(country="us", max_reviews=3000)

    if new_android_us:
        merged = deduplicate_reviews(existing_android_us_30d, new_android_us)
        filtered = filter_reviews_by_date(merged, 30)
        save_reviews(filtered, android_us_30d_file)
        save_to_csv(filtered, android_us_30d_file.replace('.json', '.csv'))
        analytics = generate_analytics(filtered, "US", days=30)
        save_reviews(analytics, android_us_30d_file.replace('.json', '_Analytics.json'))
        results['android_us_30d'] = len(filtered)

    # -------------------------------------------------------------------------
    # 2. Android All Countries - Last 30 Days Rolling
    # -------------------------------------------------------------------------
    print("\n" + "-"*70)
    print("  [2/4] Android All Countries - Last 30 Days Rolling")
    print("-"*70)

    android_all_30d_file = os.path.join(DATA_DIR, "HP_App_Android_AllCountries_Last30Days.json")
    existing_android_all_30d = load_existing_reviews(android_all_30d_file)

    new_android_all = scrape_android_all_countries(max_reviews_per_country=500)

    # Merge with US data to ensure US is included
    if new_android_us:
        new_android_all.extend(new_android_us)

    if new_android_all:
        merged = deduplicate_reviews(existing_android_all_30d, new_android_all)
        filtered = filter_reviews_by_date(merged, 30)
        save_reviews(filtered, android_all_30d_file)
        save_to_csv(filtered, android_all_30d_file.replace('.json', '.csv'))
        analytics = generate_analytics(filtered, "AllCountries", days=30)
        save_reviews(analytics, android_all_30d_file.replace('.json', '_Analytics.json'))
        results['android_all_30d'] = len(filtered)

    # -------------------------------------------------------------------------
    # 3. Android US - Last 500 Reviews
    # -------------------------------------------------------------------------
    print("\n" + "-"*70)
    print("  [3/4] Android US - Last 500 Reviews")
    print("-"*70)

    android_us_500_file = os.path.join(DATA_DIR, "HP_App_Android_US_Last500.json")
    existing_android_500 = load_existing_reviews(android_us_500_file)

    if new_android_us:
        merged = deduplicate_reviews(existing_android_500, new_android_us)
        latest_500 = merged[:500]
        save_reviews(latest_500, android_us_500_file)
        save_to_csv(latest_500, android_us_500_file.replace('.json', '.csv'))
        analytics = generate_analytics(latest_500, "US")
        save_reviews(analytics, android_us_500_file.replace('.json', '_Analytics.json'))
        results['android_us_500'] = len(latest_500)

    # -------------------------------------------------------------------------
    # 4. Run Insights Agent on All Data
    # -------------------------------------------------------------------------
    print("\n" + "-"*70)
    print("  [4/4] Running CustomerInsight_Review_Agent")
    print("-"*70)

    if os.path.exists(android_us_30d_file):
        run_insights_agent(android_us_30d_file, "HP_App_Android_US_Last30Days")

    if os.path.exists(android_all_30d_file):
        run_insights_agent(android_all_30d_file, "HP_App_Android_AllCountries_Last30Days")

    if os.path.exists(android_us_500_file):
        run_insights_agent(android_us_500_file, "HP_App_Android_US_Last500")

    # -------------------------------------------------------------------------
    # 5. Update Deep Files (no date filter — used for version comparisons)
    # -------------------------------------------------------------------------
    print("\n" + "-"*70)
    print("  [5/5] Updating Deep Files")
    print("-"*70)

    deep_us_file = os.path.join(DATA_DIR, "HP_App_Android_US_Deep.json")
    if new_android_us:
        existing_deep_us = load_existing_reviews(deep_us_file)
        merged_deep_us = deduplicate_reviews(existing_deep_us, new_android_us)
        save_reviews(merged_deep_us, deep_us_file)

    deep_all_file = os.path.join(DATA_DIR, "HP_App_Android_AllCountries_Deep.json")
    if new_android_all:
        existing_deep_all = load_existing_reviews(deep_all_file)
        merged_deep_all = deduplicate_reviews(existing_deep_all, new_android_all)
        save_reviews(merged_deep_all, deep_all_file)

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "="*70)
    print("  WEEKLY SCRAPE COMPLETE")
    print("="*70)

    print("\n  Results Summary:")
    for key, count in results.items():
        print(f"    {key}: {count} reviews")

    summary = {
        "scrape_date": datetime.now().isoformat(),
        "results": results,
        "total_reviews": sum(results.values()),
    }
    summary_file = os.path.join(REPORTS_DIR, "weekly_summary.json")
    save_reviews(summary, summary_file)

    print(f"\n  Total reviews collected: {sum(results.values())}")
    print(f"  Summary saved to: {summary_file}")

    return results


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Weekly Android Scraper - HP App")
    parser.add_argument("--all", action="store_true", help="Run full weekly scrape")
    parser.add_argument("--insights-only", action="store_true", help="Run insights only (no scraping)")

    args = parser.parse_args()

    if args.insights_only:
        print("Running insights only...")
        data_files = [
            os.path.join(DATA_DIR, "HP_App_Android_US_Last30Days.json"),
            os.path.join(DATA_DIR, "HP_App_Android_AllCountries_Last30Days.json"),
            os.path.join(DATA_DIR, "HP_App_Android_US_Last500.json"),
        ]
        for data_file in data_files:
            if os.path.exists(data_file):
                name = os.path.basename(data_file).replace('.json', '')
                run_insights_agent(data_file, name)
    else:
        run_weekly_scrape()
