"""
Free, keyless financial news fetching via RSS — same "free tool grounding"
principle as AgentX's DuckDuckGo search: the LLM never invents headlines,
it only tags/summarizes real ones pulled from these feeds.
"""

import feedparser

RSS_FEEDS = {
    "Economic Times Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "Moneycontrol Business": "https://www.moneycontrol.com/rss/business.xml",
    "LiveMint Markets": "https://www.livemint.com/rss/markets",
    "Business Standard Markets": "https://www.business-standard.com/rss/markets-106.rss",
}


def fetch_news(max_per_feed: int = 10) -> list[dict]:
    """Pull recent headlines+summaries from each feed. Fails soft per feed."""
    items = []
    for source, url in RSS_FEEDS.items():
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[:max_per_feed]:
                items.append(
                    {
                        "source": source,
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", entry.get("description", ""))[:400],
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                    }
                )
        except Exception as e:
            items.append({"source": source, "title": "feed_error", "summary": str(e), "link": "", "published": ""})
    return items
