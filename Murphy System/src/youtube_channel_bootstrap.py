"""
YouTube Channel Bootstrap — First-time setup guide for The Murphy System channel.

Design Label: YT-007 — YouTube Channel Setup & Verification
Owner: Platform Engineering / Content Team
Dependencies:
  - youtube_uploader (credential paths)

Note: YouTube does NOT allow programmatic channel creation.
      This module detects missing setup and provides step-by-step instructions.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_MURPHY_DIR = Path.home() / ".murphy"
_CREDENTIALS_FILE = _MURPHY_DIR / "youtube_credentials.json"
_CLIENT_SECRETS_FILE = _MURPHY_DIR / "client_secrets.json"
_QUOTA_FILE = _MURPHY_DIR / "youtube_quota.json"
_DAILY_QUOTA_LIMIT = 10_000

_SETUP_INSTRUCTIONS = """
# Murphy System — YouTube Channel Setup Guide

## Step 1: Create a Google Cloud Project
1. Go to https://console.cloud.google.com
2. Click "New Project"
3. Name it "Murphy System Publishing" (or any name you prefer)
4. Note your Project ID

## Step 2: Enable YouTube Data API v3
1. In Google Cloud Console, go to "APIs & Services" → "Library"
2. Search for "YouTube Data API v3"
3. Click "Enable"

## Step 3: Create OAuth2 Credentials
1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Application type: **Desktop app**
4. Name: "Murphy System"
5. Click "Create" then "Download JSON"

## Step 4: Place client_secrets.json
Move the downloaded file to:
  {credentials_path}

## Step 5: Connect Murphy System
Run in your terminal:
  murphy youtube connect

Or in Python:
  from youtube_channel_bootstrap import YouTubeChannelBootstrap
  bootstrap = YouTubeChannelBootstrap()
  bootstrap.initiate_oauth_flow()

## Step 6: Create "The Murphy System" Channel (Manual)
YouTube does NOT allow programmatic channel creation.
1. Go to https://studio.youtube.com
2. Sign in with the same Google account
3. Click your profile → "Create a channel"
4. Name it: **The Murphy System**
5. Add description: "Murphy System — AI agent run recordings. Alpha software. Inoni LLC."

## Step 7: Verify Setup
  murphy youtube status

Or in Python:
  status = bootstrap.check_youtube_setup()
  logger.info("Setup status: %s", status)

---
*For support: {github_url}*
*License: BSL 1.1 — © 2020 Inoni LLC*
"""

_GITHUB_URL = "https://github.com/IKNOWINOT/Murphy-System"


class YouTubeChannelBootstrap:
    """
    First-time setup guide and verification for the Murphy System YouTube channel.

    YouTube does NOT support programmatic channel creation.
    This module detects configuration state and guides users through manual setup.

    Usage::

        bootstrap = YouTubeChannelBootstrap()
        status = bootstrap.check_youtube_setup()
        if not status["ready"]:
            logger.info(bootstrap.get_setup_instructions())
        else:
            bootstrap.verify_channel_access()
    """

    def __init__(
        self,
        credentials_path: Optional[Path] = None,
        client_secrets_path: Optional[Path] = None,
    ) -> None:
        self._credentials_path = credentials_path or _CREDENTIALS_FILE
        self._client_secrets_path = client_secrets_path or _CLIENT_SECRETS_FILE

    def check_youtube_setup(self) -> Dict[str, Any]:
        """
        Return a status dict describing the current setup state.

        Keys:
          credentials_exist: bool
          client_secrets_exist: bool
          api_packages_installed: bool
          authenticated: bool
          quota_remaining: int
          channel_connected: Optional[bool]  (None if unchecked)
          ready: bool  (all required conditions met)
          missing_steps: List[str]
        """
        credentials_exist = self._credentials_path.exists()
        client_secrets_exist = self._client_secrets_path.exists()
        api_packages_installed = self._check_api_packages()
        authenticated = self._check_authenticated()
        quota_remaining = self._get_quota_remaining()

        missing: list = []
        if not client_secrets_exist:
            missing.append("client_secrets.json not found in ~/.murphy/")
        if not api_packages_installed:
            missing.append("pip install google-api-python-client google-auth-oauthlib")
        if not authenticated:
            missing.append("Run: murphy youtube connect")

        ready = (
            credentials_exist
            and client_secrets_exist
            and api_packages_installed
            and authenticated
        )

        return {
            "credentials_exist": credentials_exist,
            "client_secrets_exist": client_secrets_exist,
            "api_packages_installed": api_packages_installed,
            "authenticated": authenticated,
            "quota_remaining": quota_remaining,
            "channel_connected": None,
            "ready": ready,
            "missing_steps": missing,
        }

    def get_setup_instructions(self) -> str:
        """Return step-by-step Markdown setup instructions."""
        return _SETUP_INSTRUCTIONS.format(
            credentials_path=str(self._client_secrets_path),
            github_url=_GITHUB_URL,
        )

    def initiate_oauth_flow(self) -> bool:
        """
        Run the OAuth2 consent flow. Opens browser, waits for callback.
        Returns True on success, False on failure/unavailability.
        """
        if not self._check_api_packages():
            logger.warning(
                "Cannot initiate OAuth: google-api-python-client not installed. "
                "Run: pip install google-api-python-client google-auth-oauthlib"
            )
            return False

        if not self._client_secrets_path.exists():
            logger.warning(
                "client_secrets.json not found at %s. "
                "Follow setup instructions to download it first.",
                self._client_secrets_path,
            )
            return False

        try:
            from google.auth.transport.requests import Request  # noqa: F401
            from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: F401

            scopes = [
                "https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube.readonly",
            ]
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self._client_secrets_path),
                scopes=scopes,
            )
            credentials = flow.run_local_server(port=0)
            self._save_credentials(credentials)
            logger.info("OAuth flow completed — credentials saved")
            return True
        except Exception as exc:
            logger.error("OAuth flow failed: %s", exc)
            return False

    def verify_channel_access(self) -> Dict[str, Any]:
        """
        Verify that credentials work and can list the channel's videos.
        Returns dict with success flag and channel info.
        """
        if not self._check_api_packages():
            return {
                "success": False,
                "error": "API packages not installed",
                "channel_id": None,
                "channel_title": None,
                "video_count": 0,
            }

        if not self._check_authenticated():
            return {
                "success": False,
                "error": "Not authenticated — run: murphy youtube connect",
                "channel_id": None,
                "channel_title": None,
                "video_count": 0,
            }

        try:
            creds = self._load_credentials()
            if creds is None:
                return {
                    "success": False,
                    "error": "Failed to load credentials",
                    "channel_id": None,
                    "channel_title": None,
                    "video_count": 0,
                }

            from googleapiclient.discovery import build  # noqa: F401

            youtube = build("youtube", "v3", credentials=creds)
            response = youtube.channels().list(part="snippet,statistics", mine=True).execute()
            items = response.get("items", [])
            if not items:
                return {
                    "success": False,
                    "error": "No channel found for this account. Create one at studio.youtube.com",
                    "channel_id": None,
                    "channel_title": None,
                    "video_count": 0,
                }

            channel = items[0]
            stats = channel.get("statistics", {})
            return {
                "success": True,
                "error": None,
                "channel_id": channel.get("id"),
                "channel_title": channel.get("snippet", {}).get("title"),
                "video_count": int(stats.get("videoCount", 0)),
            }
        except Exception as exc:
            logger.error("Channel verification failed: %s", exc)
            return {
                "success": False,
                "error": str(exc)[:120],
                "channel_id": None,
                "channel_title": None,
                "video_count": 0,
            }

    def _check_api_packages(self) -> bool:
        try:
            import google_auth_oauthlib  # noqa: F401
            import googleapiclient  # noqa: F401
            return True
        except ImportError:
            return False

    def _check_authenticated(self) -> bool:
        if not self._credentials_path.exists():
            return False
        try:
            with open(str(self._credentials_path), encoding="utf-8") as fh:
                data = json.load(fh)
            return bool(data.get("token") or data.get("access_token") or data.get("refresh_token"))
        except Exception as exc:
            logger.debug("Could not read credentials: %s", exc)
            return False

    def _get_quota_remaining(self) -> int:
        try:
            if not _QUOTA_FILE.exists():
                return _DAILY_QUOTA_LIMIT
            with open(str(_QUOTA_FILE), encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("date") != str(date.today()):
                return _DAILY_QUOTA_LIMIT
            used = int(data.get("used", 0))
            return max(0, _DAILY_QUOTA_LIMIT - used)
        except Exception as exc:
            logger.debug("Could not read quota file: %s", exc)
            return _DAILY_QUOTA_LIMIT

    def _save_credentials(self, credentials: Any) -> None:
        try:
            self._credentials_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": list(credentials.scopes or []),
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
            with open(str(self._credentials_path), "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except Exception as exc:
            logger.error("Failed to save credentials: %s", exc)

    def _load_credentials(self) -> Optional[Any]:
        try:
            from google.auth.transport.requests import Request  # noqa: F401
            from google.oauth2.credentials import Credentials  # noqa: F401

            with open(str(self._credentials_path), encoding="utf-8") as fh:
                data = json.load(fh)

            creds = Credentials(
                token=data.get("token"),
                refresh_token=data.get("refresh_token"),
                token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=data.get("client_id"),
                client_secret=data.get("client_secret"),
                scopes=data.get("scopes", []),
            )
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self._save_credentials(creds)
            return creds
        except Exception as exc:
            logger.error("Credential load error: %s", exc)
            return None

    def get_channel_url(self) -> str:
        """Return the YouTube channel URL (constant for The Murphy System)."""
        return "https://www.youtube.com/@TheMurphySystem"
