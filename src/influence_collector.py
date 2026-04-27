"""
PATCH-115b — src/influence_collector.py
Murphy System — World Influence Collector
Written by Murphy LLM — unmodified output
"""
import urllib.request
import json
from dataclasses import dataclass
from datetime import datetime
import threading
from typing import List, Optional

@dataclass
class InfluenceSnapshot:
    timestamp: str
    trending_topics: list
    global_sentiment: float
    volatility_index: float
    top_domains: list

class InfluenceCollector:
    def __init__(self):
        self._snapshot: Optional[InfluenceSnapshot] = None

    def fetch_snapshot(self) -> InfluenceSnapshot:
        try:
            hacker_news_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
            req = urllib.request.Request(hacker_news_url, headers={"User-Agent": "Murphy/1.0"})
            hacker_news_response = urllib.request.urlopen(req, timeout=5)
            hacker_news_data = json.loads(hacker_news_response.read())
            hacker_news_stories = []
            for story_id in hacker_news_data[:10]:
                try:
                    story_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                    sreq = urllib.request.Request(story_url, headers={"User-Agent": "Murphy/1.0"})
                    story_response = urllib.request.urlopen(sreq, timeout=5)
                    story_data = json.loads(story_response.read())
                    hacker_news_stories.append({
                        "title": story_data.get("title", ""),
                        "url": story_data.get("url", "")
                    })
                except Exception:
                    continue

            reddit_urls = [
                "https://www.reddit.com/r/worldnews/top.json?limit=10",
                "https://www.reddit.com/r/technology/top.json?limit=10",
                "https://www.reddit.com/r/economics/top.json?limit=10"
            ]
            reddit_stories = []
            for url in reddit_urls:
                try:
                    rreq = urllib.request.Request(url, headers={"User-Agent": "Murphy/1.0"})
                    reddit_response = urllib.request.urlopen(rreq, timeout=5)
                    reddit_data = json.loads(reddit_response.read())
                    for story in reddit_data["data"]["children"]:
                        reddit_stories.append({
                            "title": story["data"]["title"],
                            "url": story["data"]["url"]
                        })
                except Exception:
                    continue

            demographic_segments = {
                "tech_early_adopter": ["tech", "startup", "innovation", "ai", "software"],
                "enterprise":         ["business", "corporate", "management", "enterprise", "market"],
                "consumer":           ["product", "review", "shopping", "price", "buy"],
                "policy_maker":       ["politics", "government", "regulation", "policy", "law"],
                "developer":          ["code", "programming", "development", "github", "api"]
            }
            trending_topics = []
            all_stories = hacker_news_stories + reddit_stories
            for story in all_stories:
                topic_score = {}
                title_lower = story["title"].lower()
                for segment, keywords in demographic_segments.items():
                    score = sum(1 for kw in keywords if kw in title_lower) / len(keywords)
                    topic_score[segment] = round(score, 3)
                trending_topics.append({
                    "topic": story["title"],
                    "url": story.get("url", ""),
                    "domain": max(topic_score, key=topic_score.get) if any(topic_score.values()) else "general",
                    "score": max(topic_score.values()) if topic_score.values() else 0.0,
                    "sentiment": "neutral",
                    "demographic_affinity": topic_score
                })

            positive_keywords = ["good", "great", "excellent", "growth", "success", "launch", "win"]
            negative_keywords = ["bad", "terrible", "awful", "crash", "fail", "breach", "attack", "down"]
            pos = sum(1 for s in all_stories for kw in positive_keywords if kw in s["title"].lower())
            neg = sum(1 for s in all_stories for kw in negative_keywords if kw in s["title"].lower())
            total = len(all_stories) or 1
            global_sentiment = (pos - neg) / total

            vol = sum(1 for s in all_stories for kw in negative_keywords if kw in s["title"].lower())
            volatility_index = min(1.0, vol / max(total, 1))

            top_domains = list(set(
                s["url"].split("//")[-1].split("/")[0]
                for s in all_stories if s.get("url")
            ))[:10]

            self._snapshot = InfluenceSnapshot(
                timestamp=datetime.utcnow().isoformat() + "Z",
                trending_topics=trending_topics[:20],
                global_sentiment=round(global_sentiment, 3),
                volatility_index=round(volatility_index, 3),
                top_domains=top_domains,
            )
            return self._snapshot

        except Exception as e:
            return InfluenceSnapshot(
                timestamp=datetime.utcnow().isoformat() + "Z",
                trending_topics=[],
                global_sentiment=0.0,
                volatility_index=0.0,
                top_domains=[],
            )

    def last_snapshot(self) -> Optional[InfluenceSnapshot]:
        return self._snapshot


_collector: Optional[InfluenceCollector] = None
_lock = threading.Lock()

def get_influence_collector() -> InfluenceCollector:
    global _collector
    if _collector is None:
        with _lock:
            if _collector is None:
                _collector = InfluenceCollector()
    return _collector
