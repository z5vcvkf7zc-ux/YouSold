"""
eBay sealed-electronics deal scanner.
"""

import os
import re
import json
import base64
import smtplib
import statistics
from email.mime.text import MIMEText
from collections import defaultdict

import requests

import config

EBAY_ENV = os.environ.get("EBAY_ENV", "production")
TOKEN_URL = (
    "https://api.ebay.com/identity/v1/oauth2/token"
    if EBAY_ENV == "production"
    else "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
)
SEARCH_URL = (
    "https://api.ebay.com/buy/browse/v1/item_summary/search"
    if EBAY_ENV == "production"
    else "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
)


def get_access_token():
    client_id = os.environ["EBAY_CLIENT_ID"]
    client_secret = os.environ["EBAY_CLIENT_SECRET"]
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    resp = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope",
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def search_listings(token, target):
    params = {
        "q": target["keywords"],
        "filter": config.CONDITION_FILTER,
        "limit": config.RESULTS_PER_SEARCH,
    }
    if target.get("category_id"):
        params["category_ids"] = target["category_id"]

    resp = requests.get(
        SEARCH_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
        },
        params=params,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get("itemSummaries", [])


def normalize_title(title):
    title = title.lower()
    title = re.sub(r"[^a-z0-9 ]", " ", title)
    noise = {
        "new", "sealed", "factory", "brand", "retail", "box", "packaging",
        "us", "usa", "model", "fast", "shipping", "free", "genuine", "authentic",
    }
    tokens = [t for t in title.split() if t not in noise and len(t) > 1]
    return " ".join(sorted(tokens))


def build_item(raw, label):
    price = float(raw.get("price", {}).get("value", 0))
    seller = raw.get("seller", {})
    buying_options = raw.get("buyingOptions", [])

    return {
        "id": raw.get("itemId"),
        "title": raw.get("title"),
        "category": label,
        "price": price,
        "condition": raw.get("condition", "New"),
        "listingType": "Auction" if "AUCTION" in buying_options else "Buy It Now",
        "bestOffer": "BEST_OFFER" in buying_options,
        "watchers": raw.get("watchCount", 0),
        "seller": {
            "feedbackPct": float(seller.get("feedbackPercentage", 0) or 0),
            "feedbackCount": int(seller.get("feedbackScore", 0) or 0),
        },
        "itemWebUrl": raw.get("itemWebUrl"),
        "_cluster_key": normalize_title(raw.get("title", "")),
    }


def score_items(items):
    clusters = defaultdict(list)
    for item in items:
        clusters[item["_cluster_key"]].append(item["price"])

    results = []
    for item in items:
        prices_in_cluster = clusters[item["_cluster_key"]]
        if len(prices_in_cluster) < 2:
            continue
        cluster_median = statistics.median(prices_in_cluster)
        if item["price"] <= 0 or cluster_median <= 0:
            continue

        spread_pct = (cluster_median - item["price"]) / cluster_median
        net_proceeds = cluster_median * (1 - config.EBAY_FEE_RATE) - config.SHIPPING_ESTIMATE
        margin = net_proceeds - item["price"]
        margin_pct = margin / item["price"]

        signals = []
        if spread_pct >= config.MIN_SPREAD_PCT:
            signals.append("below_cluster")
        if item["bestOffer"]:
            signals.append("best_offer")

        seller_ok = (
            item["seller"]["feedbackPct"] >= config.MIN_SELLER_FEEDBACK_PCT
            and item["seller"]["feedbackCount"] >= config.MIN_SELLER_FEEDBACK_COUNT
        )

        item["clusterMedian"] = round(cluster_median, 2)
        item["spreadPct"] = round(spread_pct, 3)
        item["marginPct"] = round(margin_pct, 3)
        item["margin"] = round(margin, 2)
        item["signals"] = signals
        item["sellerOk"] = seller_ok
        del item["_cluster_key"]
        results.append(item)

    results.sort(key=lambda x: x["marginPct"], reverse=True)
    return results


def send_alert_email(candidates):
    if not candidates:
        return
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
    to_email = os.environ.get("ALERT_TO_EMAIL")
    if not (gmail_address and gmail_password and to_email):
        print("Email env vars not set — skipping alert email (results still saved to data.json).")
        return

    lines = []
    for c in candidates[:15]:
        lines.append(
            f"${c['price']:.0f} -> comp ${c['clusterMedian']:.0f} "
            f"({c['marginPct']*100:.0f}% margin) — {c['title'][:70]}\n{c['itemWebUrl']}\n"
        )
    body = "\n".join(lines)

    msg = MIMEText(body)
    msg["Subject"] = f"eBay Deal Scanner: {len(candidates)} candidate(s) above threshold"
    msg["From"] = gmail_address
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_password)
        server.sendmail(gmail_address, [to_email], msg.as_string())
    print(f"Alert email sent to {to_email}.")


def main():
    token = get_access_token()

    all_items = []
    for target in config.TARGETS:
        raw_items = search_listings(token, target)
        all_items.extend(build_item(raw, target["label"]) for raw in raw_items)

    scored = score_items(all_items)

    with open("data.json", "w") as f:
        json.dump(scored, f, indent=2)
    print(f"Scanned {len(all_items)} listings, {len(scored)} had enough comps to score.")

    alert_candidates = [
        item for item in scored
        if item["marginPct"] >= config.MIN_MARGIN_PCT and item["sellerOk"]
    ]
    print(f"{len(alert_candidates)} candidate(s) cleared the alert threshold.")
    send_alert_email(alert_candidates)


if __name__ == "__main__":
    main()
