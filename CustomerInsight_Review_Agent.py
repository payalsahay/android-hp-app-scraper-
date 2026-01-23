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
# WITH SUB-CATEGORIES FOR SECOND-LEVEL ANALYSIS
# ============================================================================

INSIGHT_CATEGORIES = {
    "connectivity": {
        "name": "Connectivity & Setup",
        "description": "WiFi connection, Bluetooth, network setup, printer discovery",
        "keywords": [
            "wifi", "wi-fi", "connect", "connection", "network", "bluetooth",
            "setup", "find printer", "discover", "pair", "pairing", "wireless",
            "reconnect", "disconnect", "offline", "online", "ip address", "router",
            "hotspot", "signal", "dns", "dhcp", "ssid", "wps", "lan", "ethernet"
        ],
        "pm_focus": "First-time user experience, connectivity reliability",
        "subcategories": {
            "wifi_issues": {
                "name": "WiFi Connection Problems",
                "keywords": ["wifi", "wi-fi", "wireless", "router", "signal", "ssid", "wps", "hotspot"],
                "severity": "critical"
            },
            "bluetooth_issues": {
                "name": "Bluetooth Pairing Issues",
                "keywords": ["bluetooth", "pair", "pairing", "unpair"],
                "severity": "high"
            },
            "printer_discovery": {
                "name": "Printer Not Found/Discovery",
                "keywords": ["find printer", "discover", "not found", "can't find", "cannot find", "search printer", "detect"],
                "severity": "critical"
            },
            "connection_drops": {
                "name": "Connection Drops/Unstable",
                "keywords": ["disconnect", "reconnect", "drops", "lost connection", "keeps disconnecting", "unstable"],
                "severity": "high"
            },
            "initial_setup": {
                "name": "First-Time Setup Issues",
                "keywords": ["setup", "set up", "first time", "initial", "configure", "configuration", "onboarding"],
                "severity": "high"
            }
        }
    },
    "printing": {
        "name": "Print Quality & Functionality",
        "description": "Print quality, speed, paper handling, print jobs",
        "keywords": [
            "print", "printing", "quality", "resolution", "color", "black and white",
            "b&w", "pages", "paper", "ink", "toner", "cartridge", "jam", "duplex",
            "double-sided", "borderless", "photo", "document", "pdf", "queue",
            "job", "spool", "margin", "blurry", "faded", "smudge", "streaks"
        ],
        "pm_focus": "Core value proposition, print reliability",
        "subcategories": {
            "print_quality": {
                "name": "Print Quality Issues",
                "keywords": ["quality", "blurry", "faded", "smudge", "streaks", "color", "resolution", "fuzzy", "pixelated"],
                "severity": "high"
            },
            "print_speed": {
                "name": "Print Speed/Performance",
                "keywords": ["slow print", "takes forever", "speed", "fast", "quick", "waiting"],
                "severity": "medium"
            },
            "paper_handling": {
                "name": "Paper Handling/Jams",
                "keywords": ["paper", "jam", "jammed", "stuck", "feed", "tray", "load"],
                "severity": "medium"
            },
            "ink_toner": {
                "name": "Ink/Toner Issues",
                "keywords": ["ink", "toner", "cartridge", "refill", "empty", "low ink", "ink level"],
                "severity": "medium"
            },
            "print_jobs": {
                "name": "Print Job Management",
                "keywords": ["queue", "job", "cancel", "stuck job", "pending", "spool"],
                "severity": "medium"
            },
            "document_types": {
                "name": "Document Type Support",
                "keywords": ["pdf", "photo", "document", "image", "file type", "format", "word", "excel"],
                "severity": "low"
            }
        }
    },
    "scanning": {
        "name": "Scanning Features",
        "description": "Scan quality, OCR, scan-to-email, document scanning",
        "keywords": [
            "scan", "scanning", "scanner", "ocr", "document", "scan to email",
            "scan to cloud", "image", "resolution", "quality", "pdf scan",
            "copy", "fax", "multipage", "batch scan", "scan quality"
        ],
        "pm_focus": "Secondary feature adoption, scan workflow",
        "subcategories": {
            "scan_quality": {
                "name": "Scan Quality Issues",
                "keywords": ["scan quality", "blurry scan", "resolution", "clarity", "dark scan", "light scan"],
                "severity": "high"
            },
            "scan_destinations": {
                "name": "Scan Destination Problems",
                "keywords": ["scan to email", "scan to cloud", "save scan", "destination", "send scan"],
                "severity": "medium"
            },
            "ocr_text": {
                "name": "OCR/Text Recognition",
                "keywords": ["ocr", "text recognition", "searchable", "text", "recognize"],
                "severity": "low"
            },
            "multipage_scanning": {
                "name": "Multi-page/Batch Scanning",
                "keywords": ["multipage", "multi-page", "batch", "multiple pages", "adf", "feeder"],
                "severity": "medium"
            }
        }
    },
    "mobile_experience": {
        "name": "Mobile App Experience",
        "description": "App usability, UI/UX, navigation, responsiveness",
        "keywords": [
            "app", "interface", "ui", "ux", "easy", "difficult", "confusing",
            "intuitive", "simple", "complicated", "navigate", "menu", "button",
            "screen", "layout", "design", "user friendly", "responsive",
            "clunky", "cluttered", "clean", "modern", "outdated design"
        ],
        "pm_focus": "App usability, user satisfaction",
        "subcategories": {
            "navigation": {
                "name": "Navigation/Menu Issues",
                "keywords": ["navigate", "navigation", "menu", "find", "where is", "can't find", "confusing", "lost"],
                "severity": "high"
            },
            "ui_design": {
                "name": "UI/Visual Design",
                "keywords": ["design", "layout", "interface", "ui", "look", "appearance", "ugly", "beautiful", "modern", "outdated"],
                "severity": "medium"
            },
            "ease_of_use": {
                "name": "Ease of Use",
                "keywords": ["easy", "simple", "intuitive", "difficult", "complicated", "hard to use", "user friendly", "straightforward"],
                "severity": "high"
            },
            "responsiveness": {
                "name": "App Responsiveness",
                "keywords": ["responsive", "lag", "delay", "slow app", "snappy", "quick", "smooth"],
                "severity": "medium"
            },
            "accessibility": {
                "name": "Accessibility Issues",
                "keywords": ["accessibility", "font size", "text size", "contrast", "dark mode", "visibility"],
                "severity": "low"
            }
        }
    },
    "reliability": {
        "name": "App Reliability & Stability",
        "description": "Crashes, bugs, freezing, performance issues",
        "keywords": [
            "crash", "bug", "freeze", "frozen", "stuck", "error", "fail",
            "not working", "doesn't work", "broken", "glitch", "slow",
            "lag", "hang", "unresponsive", "force close", "restart",
            "battery", "memory", "storage", "cpu", "overheating"
        ],
        "pm_focus": "Technical debt, app stability metrics",
        "subcategories": {
            "crashes": {
                "name": "App Crashes",
                "keywords": ["crash", "crashes", "force close", "closes", "shuts down", "restart"],
                "severity": "critical"
            },
            "freezing": {
                "name": "App Freezing/Hanging",
                "keywords": ["freeze", "frozen", "hang", "stuck", "unresponsive", "not responding"],
                "severity": "critical"
            },
            "bugs_glitches": {
                "name": "Bugs & Glitches",
                "keywords": ["bug", "glitch", "error", "issue", "problem", "broken"],
                "severity": "high"
            },
            "performance": {
                "name": "Performance/Speed Issues",
                "keywords": ["slow", "lag", "laggy", "performance", "speed", "loading"],
                "severity": "high"
            },
            "resource_usage": {
                "name": "Battery/Memory Usage",
                "keywords": ["battery", "drain", "memory", "storage", "space", "cpu", "overheating"],
                "severity": "medium"
            }
        }
    },
    "updates": {
        "name": "Updates & Compatibility",
        "description": "App updates, Android compatibility, version issues",
        "keywords": [
            "update", "version", "android", "phone", "tablet", "compatible",
            "compatibility", "upgrade", "new version", "old version",
            "after update", "latest", "outdated", "support", "samsung",
            "pixel", "oneplus", "xiaomi", "huawei"
        ],
        "pm_focus": "Release management, OS compatibility",
        "subcategories": {
            "update_breaks": {
                "name": "Updates Breaking Functionality",
                "keywords": ["after update", "since update", "new update", "latest update", "update broke", "worked before"],
                "severity": "critical"
            },
            "android_compatibility": {
                "name": "Android Version Compatibility",
                "keywords": ["android", "android 13", "android 14", "android version", "os version"],
                "severity": "high"
            },
            "device_compatibility": {
                "name": "Device-Specific Issues",
                "keywords": ["samsung", "pixel", "oneplus", "xiaomi", "huawei", "phone", "tablet", "device"],
                "severity": "medium"
            },
            "printer_compatibility": {
                "name": "Printer Model Compatibility",
                "keywords": ["printer model", "not supported", "my printer", "older printer", "new printer"],
                "severity": "high"
            }
        }
    },
    "features": {
        "name": "Feature Requests & Missing Features",
        "description": "Desired features, missing functionality, enhancements",
        "keywords": [
            "wish", "want", "need", "should", "could", "would be nice",
            "missing", "add", "feature", "option", "functionality", "ability",
            "please add", "hope", "request", "suggest", "improvement",
            "why can't", "used to", "bring back"
        ],
        "pm_focus": "Product roadmap, feature prioritization",
        "subcategories": {
            "missing_features": {
                "name": "Missing Core Features",
                "keywords": ["missing", "doesn't have", "no option", "can't do", "unable to", "not available"],
                "severity": "high"
            },
            "feature_requests": {
                "name": "New Feature Requests",
                "keywords": ["wish", "want", "please add", "would be nice", "hope", "request", "suggest"],
                "severity": "medium"
            },
            "removed_features": {
                "name": "Removed/Deprecated Features",
                "keywords": ["used to", "bring back", "removed", "gone", "where is", "no longer"],
                "severity": "high"
            },
            "enhancement_requests": {
                "name": "Enhancement/Improvement Requests",
                "keywords": ["improve", "better", "enhancement", "should be", "could be better"],
                "severity": "medium"
            }
        }
    },
    "account_cloud": {
        "name": "Account & Cloud Services",
        "description": "Login, account management, cloud printing, storage",
        "keywords": [
            "login", "sign in", "account", "password", "register", "cloud",
            "google drive", "dropbox", "icloud", "email", "storage", "sync",
            "authentication", "credentials", "hp+", "hp account", "instant ink"
        ],
        "pm_focus": "Account funnel, cloud integration",
        "subcategories": {
            "login_issues": {
                "name": "Login/Authentication Problems",
                "keywords": ["login", "sign in", "sign-in", "log in", "can't login", "authentication", "password"],
                "severity": "critical"
            },
            "account_management": {
                "name": "Account Management",
                "keywords": ["account", "register", "registration", "profile", "settings", "credentials"],
                "severity": "high"
            },
            "cloud_integration": {
                "name": "Cloud Storage Integration",
                "keywords": ["google drive", "dropbox", "cloud", "icloud", "onedrive", "cloud storage"],
                "severity": "medium"
            },
            "hp_services": {
                "name": "HP+ / Instant Ink Issues",
                "keywords": ["hp+", "hp plus", "instant ink", "subscription", "hp account", "hp service"],
                "severity": "high"
            },
            "sync_issues": {
                "name": "Sync/Data Issues",
                "keywords": ["sync", "synchronize", "data", "lost", "not saving", "backup"],
                "severity": "medium"
            }
        }
    },
    "support": {
        "name": "Customer Support & Help",
        "description": "Support experience, documentation, troubleshooting",
        "keywords": [
            "support", "help", "customer service", "contact", "call",
            "troubleshoot", "guide", "manual", "instructions", "tutorial",
            "faq", "documentation", "assistance", "chat", "response"
        ],
        "pm_focus": "Support deflection, self-service success",
        "subcategories": {
            "support_quality": {
                "name": "Support Quality/Experience",
                "keywords": ["support", "customer service", "help", "assistance", "representative", "agent"],
                "severity": "high"
            },
            "response_time": {
                "name": "Support Response Time",
                "keywords": ["response", "waiting", "reply", "took long", "no response", "quick response"],
                "severity": "medium"
            },
            "self_help": {
                "name": "Self-Help/Documentation",
                "keywords": ["guide", "manual", "instructions", "tutorial", "faq", "documentation", "how to"],
                "severity": "low"
            },
            "troubleshooting": {
                "name": "Troubleshooting Effectiveness",
                "keywords": ["troubleshoot", "fix", "resolve", "solution", "steps", "didn't help"],
                "severity": "medium"
            }
        }
    },
    "value": {
        "name": "Value & Pricing",
        "description": "Free vs paid, subscriptions, in-app purchases, worth",
        "keywords": [
            "free", "paid", "subscription", "purchase", "buy", "cost",
            "price", "worth", "value", "money", "expensive", "cheap",
            "ads", "advertisement", "premium", "pro", "trial", "refund"
        ],
        "pm_focus": "Monetization, value perception",
        "subcategories": {
            "subscription_model": {
                "name": "Subscription Complaints",
                "keywords": ["subscription", "monthly", "yearly", "recurring", "cancel subscription"],
                "severity": "high"
            },
            "pricing_concerns": {
                "name": "Pricing Too High",
                "keywords": ["expensive", "cost", "price", "overpriced", "too much", "not worth"],
                "severity": "high"
            },
            "ads_complaints": {
                "name": "Excessive Ads",
                "keywords": ["ads", "advertisement", "commercials", "popup", "ad-free", "too many ads"],
                "severity": "medium"
            },
            "free_vs_paid": {
                "name": "Free vs Paid Feature Gaps",
                "keywords": ["free", "paid", "premium", "pro", "unlock", "paywall", "trial"],
                "severity": "medium"
            },
            "value_perception": {
                "name": "Value for Money",
                "keywords": ["worth", "value", "money", "worthless", "great value", "good deal"],
                "severity": "medium"
            }
        }
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


def categorize_subcategory(text, category_id):
    """Get sub-categories for a given category from review text"""
    text_lower = text.lower()
    subcategories = []

    cat_info = INSIGHT_CATEGORIES.get(category_id, {})
    subcats = cat_info.get("subcategories", {})

    for subcat_id, subcat_info in subcats.items():
        for keyword in subcat_info["keywords"]:
            if keyword in text_lower:
                subcategories.append(subcat_id)
                break

    return subcategories if subcategories else ["other"]


def analyze_reviews(reviews):
    """Main analysis function with sub-category drill-down"""

    # Initialize counters
    category_counts = Counter()
    category_sentiment = defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0})
    category_reviews = defaultdict(list)
    sentiment_counts = Counter()
    rating_distribution = Counter()

    # Sub-category tracking
    subcategory_counts = defaultdict(Counter)  # {category: {subcategory: count}}
    subcategory_sentiment = defaultdict(lambda: defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0}))
    subcategory_reviews = defaultdict(lambda: defaultdict(list))  # {category: {subcategory: [reviews]}}

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

            # Sub-category analysis
            if cat != "uncategorized":
                subcats = categorize_subcategory(full_text, cat)
                for subcat in subcats:
                    subcategory_counts[cat][subcat] += 1
                    subcategory_sentiment[cat][subcat][sentiment] += 1
                    if len(subcategory_reviews[cat][subcat]) < 3:  # Keep top 3 examples per subcategory
                        subcategory_reviews[cat][subcat].append({
                            "rating": rating,
                            "title": title[:50],
                            "snippet": content[:200],
                            "sentiment": sentiment
                        })

    return {
        "total_reviews": len(reviews),
        "category_counts": category_counts,
        "category_sentiment": dict(category_sentiment),
        "category_reviews": dict(category_reviews),
        "sentiment_counts": sentiment_counts,
        "rating_distribution": rating_distribution,
        # New sub-category data
        "subcategory_counts": dict(subcategory_counts),
        "subcategory_sentiment": {cat: dict(subs) for cat, subs in subcategory_sentiment.items()},
        "subcategory_reviews": {cat: dict(subs) for cat, subs in subcategory_reviews.items()}
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

    # ==========================================================================
    # SECOND-LEVEL ANALYSIS - Sub-category drill-down for top 5 categories
    # ==========================================================================
    print("\n" + "="*70)
    print("  SECOND-LEVEL ANALYSIS: SUB-CATEGORY BREAKDOWN")
    print("="*70)
    print("\n  Drilling down into top categories to identify specific issues...\n")

    subcategory_counts = analysis.get("subcategory_counts", {})
    subcategory_sentiment = analysis.get("subcategory_sentiment", {})
    subcategory_reviews = analysis.get("subcategory_reviews", {})

    for rank, (cat_id, count) in enumerate(top_categories[:5], 1):
        if cat_id == "uncategorized":
            continue

        cat_info = INSIGHT_CATEGORIES.get(cat_id, {})
        cat_name = cat_info.get("name", cat_id)
        subcats_info = cat_info.get("subcategories", {})

        print("-"*70)
        print(f"  {rank}. {cat_name.upper()} ({count} mentions)")
        print("-"*70)

        # Get sub-category breakdown
        cat_subcats = subcategory_counts.get(cat_id, {})
        if cat_subcats:
            sorted_subcats = sorted(cat_subcats.items(), key=lambda x: -x[1])

            print("\n  Sub-category Breakdown:")
            print("  " + "-"*40)

            for subcat_id, subcat_count in sorted_subcats[:6]:  # Top 6 sub-categories
                if subcat_id == "other":
                    subcat_name = "Other/Unspecified"
                    severity = "low"
                else:
                    subcat_def = subcats_info.get(subcat_id, {})
                    subcat_name = subcat_def.get("name", subcat_id)
                    severity = subcat_def.get("severity", "medium")

                subcat_pct = subcat_count / count * 100 if count > 0 else 0

                # Get sub-category sentiment
                subcat_sent = subcategory_sentiment.get(cat_id, {}).get(subcat_id, {})
                sub_pos = subcat_sent.get("positive", 0)
                sub_neg = subcat_sent.get("negative", 0)

                # Severity indicator
                sev_icon = "🔴" if severity == "critical" else ("🟠" if severity == "high" else ("🟡" if severity == "medium" else "🟢"))

                print(f"\n    {sev_icon} {subcat_name}")
                print(f"       Count: {subcat_count} ({subcat_pct:.1f}% of category)")
                print(f"       Sentiment: +{sub_pos} / -{sub_neg}")
                print(f"       Severity: {severity.upper()}")

                # Show sample reviews for this sub-category
                samples = subcategory_reviews.get(cat_id, {}).get(subcat_id, [])[:2]
                if samples:
                    print(f"       Sample reviews:")
                    for sample in samples:
                        sent_icon = "+" if sample["sentiment"] == "positive" else ("-" if sample["sentiment"] == "negative" else "~")
                        print(f"         {sent_icon} [{sample['rating']}*] \"{sample['snippet'][:80]}...\"")
        else:
            print("\n  No sub-category breakdown available.")

        print()

    # ==========================================================================
    # PRIORITY ISSUES SUMMARY (from sub-category analysis)
    # ==========================================================================
    print("\n" + "="*70)
    print("  PRIORITY ISSUES SUMMARY")
    print("="*70)

    # Collect all critical and high severity sub-category issues
    priority_issues = []
    for cat_id in subcategory_counts:
        cat_info = INSIGHT_CATEGORIES.get(cat_id, {})
        cat_name = cat_info.get("name", cat_id)
        subcats_info = cat_info.get("subcategories", {})

        for subcat_id, subcat_count in subcategory_counts[cat_id].items():
            if subcat_id == "other":
                continue
            subcat_def = subcats_info.get(subcat_id, {})
            severity = subcat_def.get("severity", "medium")
            subcat_name = subcat_def.get("name", subcat_id)

            # Get sentiment for this sub-category
            subcat_sent = subcategory_sentiment.get(cat_id, {}).get(subcat_id, {})
            neg_count = subcat_sent.get("negative", 0)
            neg_ratio = neg_count / subcat_count if subcat_count > 0 else 0

            if severity in ["critical", "high"] or neg_ratio > 0.5:
                priority_issues.append({
                    "category": cat_name,
                    "subcategory": subcat_name,
                    "count": subcat_count,
                    "severity": severity,
                    "neg_ratio": neg_ratio,
                    "neg_count": neg_count
                })

    # Sort by severity (critical first), then by count
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    priority_issues.sort(key=lambda x: (severity_order.get(x["severity"], 4), -x["count"]))

    print("\n  Top Priority Issues to Address:\n")
    for i, issue in enumerate(priority_issues[:10], 1):
        sev_icon = "🔴" if issue["severity"] == "critical" else ("🟠" if issue["severity"] == "high" else "🟡")
        print(f"  {i:2d}. {sev_icon} {issue['subcategory']}")
        print(f"       Category: {issue['category']}")
        print(f"       Mentions: {issue['count']} | Negative: {issue['neg_count']} ({issue['neg_ratio']*100:.0f}%)")
        print(f"       Severity: {issue['severity'].upper()}")
        print()

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

    subcategory_counts = analysis.get("subcategory_counts", {})
    subcategory_sentiment = analysis.get("subcategory_sentiment", {})
    subcategory_reviews = analysis.get("subcategory_reviews", {})

    for cat_id, count in analysis["category_counts"].most_common(10):
        cat_info = INSIGHT_CATEGORIES.get(cat_id, {"name": cat_id, "pm_focus": ""})
        subcats_info = cat_info.get("subcategories", {})

        # Build sub-category breakdown
        subcat_breakdown = {}
        cat_subcats = subcategory_counts.get(cat_id, {})
        for subcat_id, subcat_count in cat_subcats.items():
            if subcat_id == "other":
                subcat_name = "Other/Unspecified"
                severity = "low"
            else:
                subcat_def = subcats_info.get(subcat_id, {})
                subcat_name = subcat_def.get("name", subcat_id)
                severity = subcat_def.get("severity", "medium")

            subcat_breakdown[subcat_id] = {
                "name": subcat_name,
                "count": subcat_count,
                "percentage_of_category": round(subcat_count / count * 100, 1) if count > 0 else 0,
                "severity": severity,
                "sentiment": subcategory_sentiment.get(cat_id, {}).get(subcat_id, {}),
                "sample_reviews": subcategory_reviews.get(cat_id, {}).get(subcat_id, [])[:3]
            }

        output["categories"][cat_id] = {
            "name": cat_info.get("name", cat_id),
            "mention_count": count,
            "percentage_of_total": round(count / analysis["total_reviews"] * 100, 1) if analysis["total_reviews"] > 0 else 0,
            "sentiment": analysis["category_sentiment"].get(cat_id, {}),
            "pm_focus": cat_info.get("pm_focus", ""),
            "sample_reviews": analysis["category_reviews"].get(cat_id, [])[:5],
            "subcategory_breakdown": subcat_breakdown
        }

    # Sort sub-categories by count within each category
    for cat_id in output["categories"]:
        subcat_data = output["categories"][cat_id].get("subcategory_breakdown", {})
        sorted_subcats = dict(sorted(subcat_data.items(), key=lambda x: -x[1].get("count", 0)))
        output["categories"][cat_id]["subcategory_breakdown"] = sorted_subcats

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
