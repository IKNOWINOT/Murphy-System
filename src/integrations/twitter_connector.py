"""
Twitter / X Integration — Murphy System World Model Connector.

Uses X API v2.
Required credentials: TWITTER_BEARER_TOKEN (read-only) or
  TWITTER_API_KEY + TWITTER_API_SECRET + TWITTER_ACCESS_TOKEN + TWITTER_ACCESS_TOKEN_SECRET
Setup: https://developer.twitter.com/en/portal/dashboard
"""
from __future__ import annotations
import logging

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class TwitterConnector(BaseIntegrationConnector):
    """Twitter / X API v2 connector."""

    INTEGRATION_NAME = "Twitter / X"
    BASE_URL = "https://api.twitter.com/2"
    CREDENTIAL_KEYS = [
        "TWITTER_BEARER_TOKEN",
        "TWITTER_API_KEY",
        "TWITTER_API_SECRET",
        "TWITTER_ACCESS_TOKEN",
        "TWITTER_ACCESS_TOKEN_SECRET",
    ]
    FREE_TIER = True
    SETUP_URL = "https://developer.twitter.com/en/portal/dashboard"
    DOCUMENTATION_URL = "https://developer.twitter.com/en/docs/twitter-api"

    def is_configured(self) -> bool:
        return bool(
            self._credentials.get("TWITTER_BEARER_TOKEN")
            or (self._credentials.get("TWITTER_API_KEY")
                and self._credentials.get("TWITTER_API_SECRET"))
        )

    def _build_headers(self) -> Dict[str, str]:
        bearer = self._credentials.get("TWITTER_BEARER_TOKEN", "")
        if bearer:
            return {"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"}
        # OAuth 1.0a for write endpoints — simplified (requires requests-oauthlib for full support)
        return {"Content-Type": "application/json"}

    # -- Tweets --

    def get_tweet(self, tweet_id: str,
                  expansions: Optional[List[str]] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if expansions:
            params["expansions"] = ",".join(expansions)
        return self._get(f"/tweets/{tweet_id}", params=params)

    def search_recent_tweets(self, query: str, max_results: int = 10,
                             next_token: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "query": query,
            "max_results": min(max(max_results, 10), 100),
        }
        if next_token:
            params["next_token"] = next_token
        return self._get("/tweets/search/recent", params=params)

    def post_tweet(self, text: str,
                   reply_to: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"text": text}
        if reply_to:
            payload["reply"] = {"in_reply_to_tweet_id": reply_to}
        return self._post("/tweets", json=payload)

    def delete_tweet(self, tweet_id: str) -> Dict[str, Any]:
        return self._delete(f"/tweets/{tweet_id}")

    def like_tweet(self, user_id: str, tweet_id: str) -> Dict[str, Any]:
        return self._post(f"/users/{user_id}/likes", json={"tweet_id": tweet_id})

    def retweet(self, user_id: str, tweet_id: str) -> Dict[str, Any]:
        return self._post(f"/users/{user_id}/retweets", json={"tweet_id": tweet_id})

    # -- Users --

    def get_user_by_username(self, username: str) -> Dict[str, Any]:
        return self._get(f"/users/by/username/{username}",
                         params={"user.fields": "id,name,username,description,public_metrics"})

    def get_user(self, user_id: str) -> Dict[str, Any]:
        return self._get(f"/users/{user_id}",
                         params={"user.fields": "id,name,username,description,public_metrics"})

    def get_user_tweets(self, user_id: str, max_results: int = 10) -> Dict[str, Any]:
        return self._get(f"/users/{user_id}/tweets",
                         params={"max_results": min(max(max_results, 5), 100)})

    def get_user_followers(self, user_id: str, max_results: int = 100) -> Dict[str, Any]:
        return self._get(f"/users/{user_id}/followers",
                         params={"max_results": min(max_results, 1000)})

    def get_user_following(self, user_id: str, max_results: int = 100) -> Dict[str, Any]:
        return self._get(f"/users/{user_id}/following",
                         params={"max_results": min(max_results, 1000)})

    def follow_user(self, user_id: str, target_user_id: str) -> Dict[str, Any]:
        return self._post(f"/users/{user_id}/following",
                          json={"target_user_id": target_user_id})

    # -- Lists --

    def get_user_lists(self, user_id: str) -> Dict[str, Any]:
        return self._get(f"/users/{user_id}/owned_lists")

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self._get("/tweets/search/recent",
                           params={"query": "murphysystem", "max_results": 10})
        result["integration"] = self.INTEGRATION_NAME
        return result
