"""
Deep historical scrape — no date filter, high volume.
Used to capture full version history (e.g. v20.2 reviews from launch).
"""

import json
import os
import sys
import time
from datetime import datetime
from collections import Counter

APP_ID = "com.hp.printercontrol"
MAX_REVIEWS = 10000
REQUEST_DELAY = 1.0

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

COUNTRIES = {
    "us": "en",
    "global": None,  # handled separately as multi-country
}

ALL_COUNTRIES = ["us", "gb", "ca", "au", "in", "de", "fr", "jp", "br", "mx", "es", "it", "nl", "se", "sg"]
COUNTRY_LANG = {
    "us": "en", "gb": "en", "ca": "en", "au": "en", "in": "en",
    "de": "de", "fr": "fr", "jp": "ja", "br": "pt", "mx": "es",
    "es": "es", "it": "it", "nl": "nl", "se": "sv", "sg": "en",
}


def scrape_reviews(country, lang, max_reviews):
    from google_play_scraper import reviews, Sort

    all_reviews = []
    continuation_token = None
    batch_size = 200

    print(f"  Scraping {country.upper()} (target: {max_reviews})...")

    try:
        while len(all_reviews) < max_reviews:
            result, continuation_token = reviews(
                APP_ID,
                lang=lang,
                country=country,
                sort=Sort.NEWEST,
                count=min(batch_size, max_reviews - len(all_reviews)),
                continuation_token=continuation_token,
            )
            if not result:
                break

            for r in result:
                review_date = r.get("at")
                all_reviews.append({
                    "id": r.get("reviewId", ""),
                    "author": r.get("userName", "Unknown"),
                    "rating": r.get("score", 0),
                    "content": r.get("content", ""),
                    "version": r.get("reviewCreatedVersion", "") or "",
                    "date": review_date.isoformat() if review_date else "",
                    "country": country,
                    "platform": "Google Play",
                    "vote_count": r.get("thumbsUpCount", 0),
                    "reply_content": r.get("replyContent", ""),
                })

            if continuation_token is None:
                break

            time.sleep(REQUEST_DELAY)

        print(f"  Fetched {len(all_reviews)} reviews from {country.upper()}")
        return all_reviews

    except Exception as e:
        print(f"  Error scraping {country}: {e}")
        return all_reviews


def version_summary(reviews):
    versions = Counter((r.get("version") or "unknown") for r in reviews)
    return dict(versions.most_common(15))


def run():
    print("=" * 60)
    print("  DEEP HISTORICAL SCRAPE — HP App")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Target: {MAX_REVIEWS:,} reviews per scope")
    print("=" * 60)

    # --- US Deep Scrape ---
    print("\n[1/2] US — Deep Scrape")
    us_reviews = scrape_reviews("us", "en", MAX_REVIEWS)

    us_file = os.path.join(DATA_DIR, "HP_App_Android_US_Deep.json")
    with open(us_file, "w") as f:
        json.dump(us_reviews, f, indent=2, ensure_ascii=False, default=str)
    print(f"  Saved {len(us_reviews)} reviews → {os.path.basename(us_file)}")
    print(f"  Version breakdown: {version_summary(us_reviews)}")

    # --- All Countries Deep Scrape ---
    print("\n[2/2] All Countries — Deep Scrape")
    all_reviews = list(us_reviews)  # start with US

    for country in ALL_COUNTRIES:
        if country == "us":
            continue  # already done
        lang = COUNTRY_LANG[country]
        country_reviews = scrape_reviews(country, lang, 1000)
        all_reviews.extend(country_reviews)
        time.sleep(REQUEST_DELAY)

    # Deduplicate by review ID
    reviews_by_id = {}
    for r in all_reviews:
        rid = r.get("id", "")
        if rid:
            reviews_by_id[rid] = r
    all_reviews = list(reviews_by_id.values())
    all_reviews.sort(key=lambda x: x.get("date", ""), reverse=True)

    global_file = os.path.join(DATA_DIR, "HP_App_Android_AllCountries_Deep.json")
    with open(global_file, "w") as f:
        json.dump(all_reviews, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  Saved {len(all_reviews)} reviews → {os.path.basename(global_file)}")
    print(f"  Version breakdown: {version_summary(all_reviews)}")

    print("\n" + "=" * 60)
    print("  DEEP SCRAPE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    run()
