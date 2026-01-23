"""
================================================================================
CustomerInsight_Review_Agent
================================================================================

A Product Manager's AI Agent for analyzing App Store reviews and extracting
actionable customer insights.

Author: Payal
Version: 1.1
Created: January 2026

================================================================================
REPORT FORMAT: Insight_Appstore
================================================================================

When invoked, this agent MUST generate a PM-focused report containing:

1. EXECUTIVE ANALYSIS
   - Bottom line summary (1-2 sentences)
   - Key business risks with impact/urgency
   - Opportunity cost of inaction

2. CUSTOMER SENTIMENT TABLE
   - Overall: Positive %, Negative %, Neutral % with trends
   - Rating distribution (1-5 stars) with visual bars
   - Average rating

3. TOP ISSUES TABLE (Priority Ranked)
   - Issue name
   - % of reviews mentioning
   - Sentiment breakdown (Positive/Negative/Neutral %)
   - Severity (Critical/High/Medium/Low)
   - User impact
   - Root causes
   - Sample customer quotes
   - PM recommendation

4. DETAILED ISSUE ANALYSIS
   - For each top issue: What customers say, root causes, quotes
   - PM recommendations with success metrics

5. COMPETITIVE INTELLIGENCE
   - Competitor mentions and sentiment
   - Opportunities

6. POSITIVE SIGNALS
   - What's working (themes from positive reviews)

7. PM ACTION PLAN
   - Phase 1 (0-30 days): Stabilization
   - Phase 2 (30-90 days): Core Experience
   - Phase 3 (90-180 days): Delight

8. KEY METRICS TO TRACK
   - Current vs Target (30-day, 90-day)

9. EXEC SUMMARY ONE-PAGER
   - Problem, Impact, Root Causes, Fix, Ask

10. VOICE OF CUSTOMER APPENDIX
    - Most impactful negative quotes
    - Most impactful positive quotes

================================================================================
USAGE:
    python CustomerInsight_Review_Agent.py [reviews_file.json]

OUTPUT FILES:
    - Insight_Appstore.md   (Full PM report)
    - Insight_Appstore.json (Structured data)

CUSTOMIZATION:
    - Edit INSIGHT_CATEGORIES to add/modify categories
    - Edit SENTIMENT_KEYWORDS to tune sentiment detection
    - Modify generate_pm_insights_report() for custom reporting
================================================================================
"""

import json
import csv
import re
from collections import Counter, defaultdict
from datetime import datetime

# ============================================================================
# TOP 10 CATEGORIES FOR PRINTER/CONSUMER APP
# (Defined from a Product Manager perspective)
# ============================================================================

INSIGHT_CATEGORIES = {
    "connectivity": {
        "name": "Connectivity & Setup",
        "description": "WiFi connection, Bluetooth, network setup, printer discovery",
        "keywords": [
            "wifi", "wi-fi", "connect", "connection", "network", "bluetooth",
            "setup", "find printer", "discover", "pair", "pairing", "wireless",
            "reconnect", "disconnect", "offline", "online", "ip address", "router"
        ],
        "pm_focus": "First-time user experience, connectivity reliability"
    },
    "printing": {
        "name": "Print Quality & Functionality",
        "description": "Print quality, speed, paper handling, print jobs",
        "keywords": [
            "print", "printing", "quality", "resolution", "color", "black and white",
            "b&w", "pages", "paper", "ink", "toner", "cartridge", "jam", "duplex",
            "double-sided", "borderless", "photo", "document", "pdf"
        ],
        "pm_focus": "Core value proposition, print reliability"
    },
    "scanning": {
        "name": "Scanning Features",
        "description": "Scan quality, OCR, scan-to-email, document scanning",
        "keywords": [
            "scan", "scanning", "scanner", "ocr", "document", "scan to email",
            "scan to cloud", "image", "resolution", "quality", "pdf scan"
        ],
        "pm_focus": "Secondary feature adoption, scan workflow"
    },
    "mobile_experience": {
        "name": "Mobile App Experience",
        "description": "App usability, UI/UX, navigation, responsiveness",
        "keywords": [
            "app", "interface", "ui", "ux", "easy", "difficult", "confusing",
            "intuitive", "simple", "complicated", "navigate", "menu", "button",
            "screen", "layout", "design", "user friendly", "responsive"
        ],
        "pm_focus": "App usability, user satisfaction"
    },
    "reliability": {
        "name": "App Reliability & Stability",
        "description": "Crashes, bugs, freezing, performance issues",
        "keywords": [
            "crash", "bug", "freeze", "frozen", "stuck", "error", "fail",
            "not working", "doesn't work", "broken", "glitch", "slow",
            "lag", "hang", "unresponsive", "force close", "restart"
        ],
        "pm_focus": "Technical debt, app stability metrics"
    },
    "updates": {
        "name": "Updates & Compatibility",
        "description": "App updates, iOS compatibility, version issues",
        "keywords": [
            "update", "version", "ios", "iphone", "ipad", "compatible",
            "compatibility", "upgrade", "new version", "old version",
            "after update", "latest", "outdated", "support"
        ],
        "pm_focus": "Release management, OS compatibility"
    },
    "features": {
        "name": "Feature Requests & Missing Features",
        "description": "Desired features, missing functionality, enhancements",
        "keywords": [
            "wish", "want", "need", "should", "could", "would be nice",
            "missing", "add", "feature", "option", "functionality", "ability",
            "please add", "hope", "request", "suggest", "improvement"
        ],
        "pm_focus": "Product roadmap, feature prioritization"
    },
    "account_cloud": {
        "name": "Account & Cloud Services",
        "description": "Login, account management, cloud printing, storage",
        "keywords": [
            "login", "sign in", "account", "password", "register", "cloud",
            "google drive", "dropbox", "icloud", "email", "storage", "sync",
            "authentication", "credentials"
        ],
        "pm_focus": "Account funnel, cloud integration"
    },
    "support": {
        "name": "Customer Support & Help",
        "description": "Support experience, documentation, troubleshooting",
        "keywords": [
            "support", "help", "customer service", "contact", "call",
            "troubleshoot", "guide", "manual", "instructions", "tutorial",
            "faq", "documentation", "assistance"
        ],
        "pm_focus": "Support deflection, self-service success"
    },
    "value": {
        "name": "Value & Pricing",
        "description": "Free vs paid, subscriptions, in-app purchases, worth",
        "keywords": [
            "free", "paid", "subscription", "purchase", "buy", "cost",
            "price", "worth", "value", "money", "expensive", "cheap",
            "ads", "advertisement", "premium", "pro"
        ],
        "pm_focus": "Monetization, value perception"
    }
}

# ============================================================================
# SENTIMENT KEYWORDS
# ============================================================================

SENTIMENT_KEYWORDS = {
    "positive": [
        "love", "great", "excellent", "amazing", "awesome", "perfect",
        "best", "fantastic", "wonderful", "easy", "simple", "works great",
        "highly recommend", "good", "nice", "helpful", "brilliant", "superb",
        "impressed", "satisfied", "reliable", "seamless", "smooth", "fast"
    ],
    "negative": [
        "hate", "terrible", "awful", "worst", "horrible", "bad", "poor",
        "useless", "waste", "frustrating", "annoying", "disappointing",
        "doesn't work", "not working", "broken", "fail", "crash", "bug",
        "difficult", "complicated", "confusing", "slow", "unreliable",
        "garbage", "trash", "ridiculous", "pathetic", "disaster"
    ],
    "neutral": [
        "okay", "ok", "average", "decent", "fine", "works", "basic",
        "standard", "normal", "acceptable"
    ]
}


def load_reviews(filepath):
    """Load reviews from CSV or JSON file"""
    reviews = []

    if filepath.endswith('.json'):
        with open(filepath, 'r', encoding='utf-8') as f:
            reviews = json.load(f)
    elif filepath.endswith('.csv'):
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            reviews = list(reader)

    return reviews


def analyze_sentiment(text):
    """Analyze sentiment of review text"""
    text_lower = text.lower()

    pos_count = sum(1 for word in SENTIMENT_KEYWORDS["positive"] if word in text_lower)
    neg_count = sum(1 for word in SENTIMENT_KEYWORDS["negative"] if word in text_lower)

    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    else:
        return "neutral"


def categorize_review(text):
    """Categorize review into insight categories"""
    text_lower = text.lower()
    categories = []

    for cat_id, cat_info in INSIGHT_CATEGORIES.items():
        for keyword in cat_info["keywords"]:
            if keyword in text_lower:
                categories.append(cat_id)
                break

    return categories if categories else ["uncategorized"]


def analyze_reviews(reviews):
    """Main analysis function"""

    # Initialize counters
    category_counts = Counter()
    category_sentiment = defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0})
    category_reviews = defaultdict(list)
    sentiment_counts = Counter()
    rating_distribution = Counter()

    for review in reviews:
        # Get review content
        content = review.get("content", "") or review.get("review", "") or ""
        title = review.get("title", "") or ""
        full_text = f"{title} {content}"

        # Get rating
        rating = int(review.get("rating", 3))
        rating_distribution[rating] += 1

        # Analyze sentiment
        sentiment = analyze_sentiment(full_text)
        sentiment_counts[sentiment] += 1

        # Categorize
        categories = categorize_review(full_text)
        for cat in categories:
            category_counts[cat] += 1
            category_sentiment[cat][sentiment] += 1
            if len(category_reviews[cat]) < 5:  # Keep top 5 examples
                category_reviews[cat].append({
                    "rating": rating,
                    "title": title[:50],
                    "snippet": content[:150],
                    "sentiment": sentiment
                })

    return {
        "total_reviews": len(reviews),
        "category_counts": category_counts,
        "category_sentiment": dict(category_sentiment),
        "category_reviews": dict(category_reviews),
        "sentiment_counts": sentiment_counts,
        "rating_distribution": rating_distribution
    }


def generate_pm_insights_report(analysis):
    """Generate Product Manager insights report"""

    total = analysis["total_reviews"]

    print("\n" + "="*70)
    print("  PRINTER APP INSIGHTS REPORT")
    print("  Product Manager Analysis - HP Perspective")
    print("="*70)

    # Executive Summary
    print("\n" + "-"*70)
    print("  EXECUTIVE SUMMARY")
    print("-"*70)
    print(f"\n  Total Reviews Analyzed: {total}")

    # Sentiment Overview
    sent = analysis["sentiment_counts"]
    pos_pct = sent["positive"] / total * 100 if total > 0 else 0
    neg_pct = sent["negative"] / total * 100 if total > 0 else 0
    neu_pct = sent["neutral"] / total * 100 if total > 0 else 0

    print(f"\n  Overall Sentiment:")
    print(f"    Positive: {sent['positive']:5d} ({pos_pct:5.1f}%)")
    print(f"    Negative: {sent['negative']:5d} ({neg_pct:5.1f}%)")
    print(f"    Neutral:  {sent['neutral']:5d} ({neu_pct:5.1f}%)")

    # NPS-style indicator
    nps_indicator = pos_pct - neg_pct
    print(f"\n  Sentiment Score: {nps_indicator:+.1f}")

    # Rating Distribution
    print("\n  Rating Distribution:")
    ratings = analysis["rating_distribution"]
    for r in range(5, 0, -1):
        count = ratings.get(r, 0)
        pct = count / total * 100 if total > 0 else 0
        bar = "*" * int(pct / 2)
        print(f"    {r} stars: {count:5d} ({pct:5.1f}%) {bar}")

    # Top 10 Categories
    print("\n" + "-"*70)
    print("  TOP 10 INSIGHT CATEGORIES")
    print("-"*70)

    top_categories = analysis["category_counts"].most_common(10)

    for rank, (cat_id, count) in enumerate(top_categories, 1):
        if cat_id == "uncategorized":
            cat_name = "Other/Uncategorized"
            pm_focus = "Requires manual review"
        else:
            cat_info = INSIGHT_CATEGORIES.get(cat_id, {})
            cat_name = cat_info.get("name", cat_id)
            pm_focus = cat_info.get("pm_focus", "")

        pct = count / total * 100 if total > 0 else 0

        # Get sentiment for this category
        cat_sent = analysis["category_sentiment"].get(cat_id, {})
        cat_pos = cat_sent.get("positive", 0)
        cat_neg = cat_sent.get("negative", 0)

        print(f"\n  {rank:2d}. {cat_name}")
        print(f"      Mentions: {count} ({pct:.1f}%)")
        print(f"      Sentiment: +{cat_pos} positive, -{cat_neg} negative")
        print(f"      PM Focus: {pm_focus}")

    # Actionable Insights
    print("\n" + "-"*70)
    print("  ACTIONABLE PM INSIGHTS")
    print("-"*70)

    # Find pain points (high mention + negative sentiment)
    pain_points = []
    for cat_id, count in top_categories[:10]:
        if cat_id != "uncategorized":
            cat_sent = analysis["category_sentiment"].get(cat_id, {})
            neg_ratio = cat_sent.get("negative", 0) / count if count > 0 else 0
            if neg_ratio > 0.4:  # More than 40% negative
                pain_points.append((cat_id, count, neg_ratio))

    print("\n  Critical Pain Points (High negative sentiment):")
    if pain_points:
        for cat_id, count, ratio in sorted(pain_points, key=lambda x: -x[2])[:5]:
            cat_name = INSIGHT_CATEGORIES.get(cat_id, {}).get("name", cat_id)
            print(f"    - {cat_name}: {ratio*100:.0f}% negative ({count} mentions)")
    else:
        print("    No critical pain points identified")

    # Feature opportunities
    feat_count = analysis["category_counts"].get("features", 0)
    print(f"\n  Feature Request Volume: {feat_count} mentions")

    # Connectivity focus (usually #1 for printer apps)
    conn_count = analysis["category_counts"].get("connectivity", 0)
    print(f"  Connectivity Issues: {conn_count} mentions (industry-wide challenge)")

    # Recommendations
    print("\n" + "-"*70)
    print("  PM RECOMMENDATIONS")
    print("-"*70)

    recommendations = []

    if analysis["category_counts"].get("connectivity", 0) > total * 0.2:
        recommendations.append("PRIORITY: Improve WiFi/Bluetooth connectivity flow - biggest user pain point")

    if analysis["category_counts"].get("reliability", 0) > total * 0.15:
        recommendations.append("Stability Sprint: Address crash/freeze issues to improve ratings")

    if analysis["category_counts"].get("mobile_experience", 0) > total * 0.1:
        recommendations.append("UX Audit: Simplify navigation and core workflows")

    if analysis["category_counts"].get("updates", 0) > total * 0.1:
        recommendations.append("Release QA: More thorough testing before iOS updates")

    if neg_pct > 40:
        recommendations.append("URGENT: High negative sentiment - requires immediate attention")

    if not recommendations:
        recommendations.append("Continue monitoring user feedback for emerging patterns")

    for i, rec in enumerate(recommendations, 1):
        print(f"\n  {i}. {rec}")

    # Sample Reviews by Category
    print("\n" + "-"*70)
    print("  SAMPLE REVIEWS BY CATEGORY")
    print("-"*70)

    for cat_id, count in top_categories[:5]:
        if cat_id == "uncategorized":
            continue
        cat_name = INSIGHT_CATEGORIES.get(cat_id, {}).get("name", cat_id)
        print(f"\n  [{cat_name}]")

        samples = analysis["category_reviews"].get(cat_id, [])[:3]
        for sample in samples:
            sent_icon = "+" if sample["sentiment"] == "positive" else ("-" if sample["sentiment"] == "negative" else "~")
            print(f"    {sent_icon} [{sample['rating']}*] {sample['snippet'][:80]}...")

    print("\n" + "="*70)
    print("  END OF REPORT")
    print("="*70 + "\n")


def save_insights_json(analysis, filepath="pm_insights.json"):
    """Save insights to JSON for further processing"""

    # Prepare serializable data
    output = {
        "generated_at": datetime.now().isoformat(),
        "total_reviews": analysis["total_reviews"],
        "sentiment_summary": dict(analysis["sentiment_counts"]),
        "rating_distribution": dict(analysis["rating_distribution"]),
        "categories": {}
    }

    for cat_id, count in analysis["category_counts"].most_common(10):
        cat_info = INSIGHT_CATEGORIES.get(cat_id, {"name": cat_id, "pm_focus": ""})
        output["categories"][cat_id] = {
            "name": cat_info.get("name", cat_id),
            "mention_count": count,
            "sentiment": analysis["category_sentiment"].get(cat_id, {}),
            "pm_focus": cat_info.get("pm_focus", ""),
            "sample_reviews": analysis["category_reviews"].get(cat_id, [])[:5]
        }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Insights saved to {filepath}")


def main():
    """Main entry point"""
    import sys
    import os

    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Default file path - look in same directory as script
    default_file = os.path.join(script_dir, "brother_print_reviews.json")

    # Check for command line argument
    if len(sys.argv) > 1:
        review_file = sys.argv[1]
    else:
        review_file = default_file

    print(f"\nLoading reviews from: {review_file}")

    try:
        reviews = load_reviews(review_file)
        print(f"Loaded {len(reviews)} reviews")
    except FileNotFoundError:
        print(f"Error: File not found: {review_file}")
        print("\nPlease run app_store_scraper.py first to collect reviews.")
        print("Usage: python pm_insights_agent.py [reviews_file.json]")
        return

    if not reviews:
        print("No reviews found in file.")
        return

    # Analyze
    print("Analyzing reviews...")
    analysis = analyze_reviews(reviews)

    # Generate report
    generate_pm_insights_report(analysis)

    # Save JSON insights to same directory
    insights_file = os.path.join(script_dir, "pm_insights.json")
    save_insights_json(analysis, insights_file)


if __name__ == "__main__":
    main()
