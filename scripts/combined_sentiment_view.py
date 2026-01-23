#!/usr/bin/env python3
"""
================================================================================
Combined Sentiment View Generator
================================================================================

Generates a combined sentiment analysis comparing:
1. Global App Ratings (all users who rated - including silent raters)
2. Recent Reviews (last 30 days - users who wrote reviews)

This reveals the gap between the "silent majority" and "vocal minority"

Usage:
    python scripts/combined_sentiment_view.py

Output:
    - output/HP_App_Combined_Sentiment_View.md
    - output/HP_App_Combined_Sentiment_View.json

================================================================================
"""

import json
import os
from datetime import datetime, timedelta
from collections import Counter
from google_play_scraper import app, Sort, reviews

# HP Smart App ID
APP_ID = "com.hp.printercontrol"

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")


def fetch_global_app_data():
    """Fetch global app ratings and metadata from Google Play Store"""
    print("Fetching global app data from Google Play Store...")

    try:
        app_data = app(APP_ID, lang='en', country='us')

        # Extract relevant data
        global_data = {
            "app_name": app_data.get("title", "HP Smart"),
            "app_id": APP_ID,
            "fetched_at": datetime.now().isoformat(),

            # Rating data
            "overall_rating": app_data.get("score", 0),
            "total_ratings": app_data.get("ratings", 0),
            "total_reviews": app_data.get("reviews", 0),

            # Rating histogram [1-star, 2-star, 3-star, 4-star, 5-star]
            "histogram": app_data.get("histogram", [0, 0, 0, 0, 0]),

            # App metadata
            "installs": app_data.get("installs", "Unknown"),
            "version": app_data.get("version", "Unknown"),
            "updated": app_data.get("updated", "Unknown"),
            "developer": app_data.get("developer", "HP Inc."),
        }

        # Calculate percentages from histogram
        total = sum(global_data["histogram"])
        if total > 0:
            global_data["histogram_pct"] = [
                round(count / total * 100, 1) for count in global_data["histogram"]
            ]
        else:
            global_data["histogram_pct"] = [0, 0, 0, 0, 0]

        print(f"  Overall Rating: {global_data['overall_rating']:.2f}")
        print(f"  Total Ratings: {global_data['total_ratings']:,}")
        print(f"  Total Reviews: {global_data['total_reviews']:,}")

        return global_data

    except Exception as e:
        print(f"Error fetching app data: {e}")
        return None


def load_recent_reviews():
    """Load recent reviews from existing scraped data"""
    print("\nLoading recent reviews (Last 30 Days US)...")

    reviews_file = os.path.join(DATA_DIR, "HP_App_Android_US_Last30Days.json")

    if not os.path.exists(reviews_file):
        print(f"  Warning: {reviews_file} not found")
        print("  Run the weekly scraper first to generate review data")
        return None

    with open(reviews_file, 'r', encoding='utf-8') as f:
        reviews_data = json.load(f)

    print(f"  Loaded {len(reviews_data)} reviews")

    # Calculate stats from reviews
    ratings = [r.get('score') or r.get('rating') for r in reviews_data]
    rating_counts = Counter(ratings)

    total = len(ratings)
    avg_rating = sum(ratings) / total if total > 0 else 0

    # Build histogram [1-star, 2-star, 3-star, 4-star, 5-star]
    histogram = [rating_counts.get(i, 0) for i in range(1, 6)]
    histogram_pct = [round(count / total * 100, 1) if total > 0 else 0 for count in histogram]

    # Get date range
    dates = []
    for r in reviews_data:
        date_str = r.get('at') or r.get('date')
        if date_str:
            try:
                if isinstance(date_str, str):
                    date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    date = date_str
                dates.append(date)
            except:
                pass

    date_range = {
        "earliest": min(dates).strftime('%Y-%m-%d') if dates else "Unknown",
        "latest": max(dates).strftime('%Y-%m-%d') if dates else "Unknown"
    }

    recent_data = {
        "source_file": reviews_file,
        "loaded_at": datetime.now().isoformat(),
        "total_reviews": total,
        "average_rating": round(avg_rating, 2),
        "histogram": histogram,
        "histogram_pct": histogram_pct,
        "date_range": date_range,
        "rating_counts": dict(rating_counts)
    }

    print(f"  Average Rating: {avg_rating:.2f}")
    print(f"  Date Range: {date_range['earliest']} to {date_range['latest']}")

    return recent_data


def analyze_sentiment_gap(global_data, recent_data):
    """Analyze the gap between global ratings and recent reviews"""
    print("\nAnalyzing sentiment gap...")

    analysis = {
        "generated_at": datetime.now().isoformat(),
        "comparison_period": "Last 30 Days vs All-Time"
    }

    # Rating comparison
    global_rating = global_data["overall_rating"]
    recent_rating = recent_data["average_rating"]
    rating_delta = recent_rating - global_rating

    analysis["rating_comparison"] = {
        "global_rating": global_rating,
        "recent_rating": recent_rating,
        "delta": round(rating_delta, 2),
        "trend": "improving" if rating_delta > 0.1 else ("declining" if rating_delta < -0.1 else "stable")
    }

    # Distribution comparison
    global_hist = global_data["histogram_pct"]
    recent_hist = recent_data["histogram_pct"]

    analysis["distribution_comparison"] = {
        "5_star": {"global": global_hist[4], "recent": recent_hist[4], "delta": round(recent_hist[4] - global_hist[4], 1)},
        "4_star": {"global": global_hist[3], "recent": recent_hist[3], "delta": round(recent_hist[3] - global_hist[3], 1)},
        "3_star": {"global": global_hist[2], "recent": recent_hist[2], "delta": round(recent_hist[2] - global_hist[2], 1)},
        "2_star": {"global": global_hist[1], "recent": recent_hist[1], "delta": round(recent_hist[1] - global_hist[1], 1)},
        "1_star": {"global": global_hist[0], "recent": recent_hist[0], "delta": round(recent_hist[0] - global_hist[0], 1)},
    }

    # Positive vs Negative comparison
    global_positive = global_hist[3] + global_hist[4]  # 4-5 stars
    global_negative = global_hist[0] + global_hist[1]  # 1-2 stars
    recent_positive = recent_hist[3] + recent_hist[4]
    recent_negative = recent_hist[0] + recent_hist[1]

    analysis["sentiment_summary"] = {
        "global_positive_pct": round(global_positive, 1),
        "global_negative_pct": round(global_negative, 1),
        "recent_positive_pct": round(recent_positive, 1),
        "recent_negative_pct": round(recent_negative, 1),
        "positive_delta": round(recent_positive - global_positive, 1),
        "negative_delta": round(recent_negative - global_negative, 1)
    }

    # Review engagement rate
    total_ratings = global_data["total_ratings"]
    total_reviews = global_data["total_reviews"]
    review_rate = (total_reviews / total_ratings * 100) if total_ratings > 0 else 0

    analysis["engagement"] = {
        "total_ratings": total_ratings,
        "total_reviews": total_reviews,
        "review_rate_pct": round(review_rate, 2),
        "silent_raters_pct": round(100 - review_rate, 2)
    }

    # Trend indicator
    if rating_delta < -0.3:
        trend_status = "critical_decline"
        trend_icon = "🔴"
        trend_message = f"Recent reviews {abs(rating_delta):.1f} stars LOWER than global average - Critical attention needed"
    elif rating_delta < -0.1:
        trend_status = "declining"
        trend_icon = "🟠"
        trend_message = f"Recent reviews {abs(rating_delta):.1f} stars lower than global average - Monitor closely"
    elif rating_delta > 0.1:
        trend_status = "improving"
        trend_icon = "🟢"
        trend_message = f"Recent reviews {rating_delta:.1f} stars HIGHER than global average - Positive trend"
    else:
        trend_status = "stable"
        trend_icon = "🟡"
        trend_message = "Recent reviews aligned with global average - Stable"

    analysis["trend"] = {
        "status": trend_status,
        "icon": trend_icon,
        "message": trend_message
    }

    print(f"  Rating Delta: {rating_delta:+.2f}")
    print(f"  Trend: {trend_icon} {trend_status.upper()}")

    return analysis


def generate_markdown_report(global_data, recent_data, analysis):
    """Generate markdown report"""

    lines = []

    def add(text=""):
        lines.append(text)

    # Header
    add("# HP Smart App - Combined Sentiment View")
    add("")
    add(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    add(f"**App:** {global_data['app_name']} ({global_data['app_id']})")
    add("")

    # Trend Banner
    trend = analysis["trend"]
    add("---")
    add("")
    add(f"## {trend['icon']} Sentiment Trend: {trend['status'].upper().replace('_', ' ')}")
    add("")
    add(f"> **{trend['message']}**")
    add("")

    # Quick Stats Comparison
    add("---")
    add("")
    add("## Quick Comparison")
    add("")
    add("| Metric | Global (All-Time) | Last 30 Days | Delta |")
    add("|--------|-------------------|--------------|-------|")

    rc = analysis["rating_comparison"]
    add(f"| **Average Rating** | {rc['global_rating']:.2f} ⭐ | {rc['recent_rating']:.2f} ⭐ | {rc['delta']:+.2f} |")

    ss = analysis["sentiment_summary"]
    add(f"| **Positive (4-5★)** | {ss['global_positive_pct']}% | {ss['recent_positive_pct']}% | {ss['positive_delta']:+.1f}% |")
    add(f"| **Negative (1-2★)** | {ss['global_negative_pct']}% | {ss['recent_negative_pct']}% | {ss['negative_delta']:+.1f}% |")

    add(f"| **Total Count** | {global_data['total_ratings']:,} ratings | {recent_data['total_reviews']} reviews | - |")
    add("")

    # Rating Distribution Comparison
    add("---")
    add("")
    add("## Rating Distribution Comparison")
    add("")
    add("| Rating | Global % | Last 30 Days % | Delta | Trend |")
    add("|--------|----------|----------------|-------|-------|")

    dc = analysis["distribution_comparison"]
    for stars in ["5_star", "4_star", "3_star", "2_star", "1_star"]:
        star_label = stars.replace("_", " ").replace("star", "⭐")
        data = dc[stars]
        trend_arrow = "📈" if data["delta"] > 2 else ("📉" if data["delta"] < -2 else "➡️")
        add(f"| {star_label} | {data['global']:.1f}% | {data['recent']:.1f}% | {data['delta']:+.1f}% | {trend_arrow} |")
    add("")

    # Visual Distribution
    add("### Visual Distribution")
    add("")
    add("**Global (All-Time):**")
    add("```")
    gh = global_data["histogram_pct"]
    for i in range(4, -1, -1):
        bar = "█" * int(gh[i] / 2.5) + "░" * (40 - int(gh[i] / 2.5))
        add(f"{i+1}⭐ {bar} {gh[i]:.1f}%")
    add("```")
    add("")
    add("**Last 30 Days (Written Reviews):**")
    add("```")
    rh = recent_data["histogram_pct"]
    for i in range(4, -1, -1):
        bar = "█" * int(rh[i] / 2.5) + "░" * (40 - int(rh[i] / 2.5))
        add(f"{i+1}⭐ {bar} {rh[i]:.1f}%")
    add("```")
    add("")

    # Engagement Analysis
    add("---")
    add("")
    add("## User Engagement Analysis")
    add("")
    eng = analysis["engagement"]
    add("| Metric | Value |")
    add("|--------|-------|")
    add(f"| Total Ratings (All-Time) | {eng['total_ratings']:,} |")
    add(f"| Total Written Reviews | {eng['total_reviews']:,} |")
    add(f"| Review Rate | {eng['review_rate_pct']:.1f}% |")
    add(f"| Silent Raters | {eng['silent_raters_pct']:.1f}% |")
    add("")
    add(f"> **{eng['silent_raters_pct']:.0f}%** of users rate without writing a review (silent majority)")
    add("")

    # Key Insights
    add("---")
    add("")
    add("## Key Insights")
    add("")

    # Generate insights based on analysis
    insights = []

    if rc["delta"] < -0.3:
        insights.append(f"🔴 **Critical:** Recent sentiment ({rc['recent_rating']:.1f}⭐) is significantly worse than historical average ({rc['global_rating']:.1f}⭐)")

    if ss["negative_delta"] > 10:
        insights.append(f"🔴 **Warning:** 1-2 star reviews increased by {ss['negative_delta']:.0f}% in the last 30 days")

    if ss["positive_delta"] < -10:
        insights.append(f"🟠 **Concern:** 4-5 star reviews decreased by {abs(ss['positive_delta']):.0f}% compared to global average")

    if recent_data["histogram_pct"][0] > 50:
        insights.append(f"🔴 **Alert:** {recent_data['histogram_pct'][0]:.0f}% of recent reviews are 1-star")

    if eng["review_rate_pct"] < 5:
        insights.append(f"📊 **Note:** Only {eng['review_rate_pct']:.1f}% of raters write reviews - vocal minority may not represent all users")

    if rc["delta"] > 0.1:
        insights.append(f"🟢 **Positive:** Recent reviews trending {rc['delta']:.1f} stars higher than global average")

    if not insights:
        insights.append("🟡 Sentiment patterns are within normal ranges")

    for insight in insights:
        add(f"- {insight}")
    add("")

    # App Metadata
    add("---")
    add("")
    add("## App Information")
    add("")
    add("| Property | Value |")
    add("|----------|-------|")
    add(f"| App Name | {global_data['app_name']} |")
    add(f"| Package ID | {global_data['app_id']} |")
    add(f"| Current Version | {global_data['version']} |")
    add(f"| Installs | {global_data['installs']} |")
    add(f"| Last Updated | {global_data['updated']} |")
    add(f"| Developer | {global_data['developer']} |")
    add("")

    # Data Sources
    add("---")
    add("")
    add("## Data Sources")
    add("")
    add(f"- **Global Data:** Google Play Store API (fetched {datetime.now().strftime('%Y-%m-%d')})")
    add(f"- **Recent Reviews:** {recent_data['date_range']['earliest']} to {recent_data['date_range']['latest']} (US)")
    add("")
    add("---")
    add("*Generated by Combined Sentiment View Script*")

    return "\n".join(lines)


def save_outputs(global_data, recent_data, analysis, markdown_report):
    """Save all outputs"""

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Save JSON
    json_output = {
        "generated_at": datetime.now().isoformat(),
        "global_app_data": global_data,
        "recent_reviews_data": recent_data,
        "analysis": analysis
    }

    json_file = os.path.join(OUTPUT_DIR, "HP_App_Combined_Sentiment_View.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {json_file}")

    # Save Markdown
    md_file = os.path.join(OUTPUT_DIR, "HP_App_Combined_Sentiment_View.md")
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(markdown_report)
    print(f"Saved: {md_file}")

    return json_file, md_file


def main():
    """Main entry point"""
    print("=" * 60)
    print("  HP Smart App - Combined Sentiment View Generator")
    print("=" * 60)
    print()

    # Step 1: Fetch global app data
    global_data = fetch_global_app_data()
    if not global_data:
        print("Failed to fetch global app data. Exiting.")
        return

    # Step 2: Load recent reviews
    recent_data = load_recent_reviews()
    if not recent_data:
        print("Failed to load recent reviews. Exiting.")
        return

    # Step 3: Analyze sentiment gap
    analysis = analyze_sentiment_gap(global_data, recent_data)

    # Step 4: Generate report
    print("\nGenerating combined sentiment report...")
    markdown_report = generate_markdown_report(global_data, recent_data, analysis)

    # Step 5: Save outputs
    json_file, md_file = save_outputs(global_data, recent_data, analysis, markdown_report)

    # Print summary
    print()
    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print()
    trend = analysis["trend"]
    print(f"  {trend['icon']} {trend['message']}")
    print()
    print(f"  Global Rating:     {global_data['overall_rating']:.2f} ⭐ ({global_data['total_ratings']:,} ratings)")
    print(f"  Last 30 Days:      {recent_data['average_rating']:.2f} ⭐ ({recent_data['total_reviews']} reviews)")
    print(f"  Delta:             {analysis['rating_comparison']['delta']:+.2f}")
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
