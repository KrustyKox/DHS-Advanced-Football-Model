"""Exact sportsbook threshold matching. Never infer or manufacture sportsbook prices."""
from datetime import datetime, timezone


def _key(s):
    return "".join(ch for ch in str(s).casefold() if ch.isalnum())


def qualify_market_trends(trends, market_payload, scan_date, minimum_odds=-500):
    """Only retain exact threshold offers priced >= minimum_odds.

    Feed contract:
    {"date":"YYYY-MM-DD","fetched_utc":"ISO timestamp","offers":[
      {"player":"...", "team":"...", "stat":"REB", "threshold":10,
       "american_odds":-125,"sportsbook":"...", "market":"10+ rebounds"}]}
    Offers MUST be real sportsbook quotes collected by a licensed/authorized
    feed. Threshold represents an integer 'N+' outcome, not an over-N.5 line.
    """
    if not isinstance(market_payload, dict) or market_payload.get("date") != str(scan_date):
        raise ValueError("Sportsbook feed missing or date does not match scan")
    stamp = datetime.fromisoformat(str(market_payload["fetched_utc"]).replace("Z", "+00:00"))
    if stamp.tzinfo is None or abs((datetime.now(timezone.utc) - stamp).total_seconds()) > 12 * 3600:
        raise ValueError("Sportsbook odds are stale or lack timezone")
    offers = market_payload.get("offers")
    if not isinstance(offers, list):
        raise ValueError("Sportsbook feed has no offers list")
    lookup = {}
    for offer in offers:
        try:
            price = int(offer["american_odds"])
            threshold = int(offer["threshold"])
            book = str(offer["sportsbook"]).strip()
            if not book or not (price <= -100 or price >= 100) or price < minimum_odds:
                continue
            if float(offer["threshold"]) != threshold:
                continue
            key = (_key(offer["player"]), _key(offer["team"]),
                   str(offer["stat"]).upper(), threshold)
            current = lookup.get(key)
            if current is None or price > current["american_odds"]:
                lookup[key] = {"american_odds": price, "sportsbook": book,
                               "market": str(offer.get("market") or "")}
        except (KeyError, ValueError, TypeError):
            continue
    qualified = []
    for row in trends:
        key = (_key(row["Player"]), _key(row["Team"]), row["Stat"], row["Threshold"])
        quote = lookup.get(key)
        if quote:
            qualified.append({**row, "American Odds": quote["american_odds"],
                              "Sportsbook": quote["sportsbook"],
                              "Market": quote["market"], "Odds Checked UTC": stamp.isoformat()})
    return qualified
