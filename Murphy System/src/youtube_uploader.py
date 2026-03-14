"""
YouTube Uploader — YouTube Data API v3 integration with OAuth2 & graceful degradation.

Design Label: YT-004 — YouTube Upload Engine
Owner: Platform Engineering / Content Team
Dependencies:
  - youtube_metadata_generator (YouTubeMetadata)
  - env_manager (credential paths)

Features:
  - OAuth2 with token persistence in ~/.murphy/youtube_credentials.json
  - Resumable upload support for large files
  - Daily quota tracking (10,000 units/day)
  - Graceful degradation: saves locally with upload instructions if API unavailable

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Bounded: upload history max 500 entries
  - No credentials logged or stored in plain text beyond the credentials file

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

_MURPHY_DIR = Path.home() / ".murphy"
_CREDENTIALS_FILE = _MURPHY_DIR / "youtube_credentials.json"
_CLIENT_SECRETS_FILE = _MURPHY_DIR / "client_secrets.json"
_QUOTA_FILE = _MURPHY_DIR / "youtube_quota.json"

_YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
_YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
_DAILY_QUOTA_LIMIT = 10_000
_UPLOAD_QUOTA_COST = 1_600  # YouTube charges 1600 units per video upload
_MAX_HISTORY = 500
_CHUNK_SIZE = 1024 * 1024 * 8  # 8 MB resumable upload chunks

_MANUAL_UPLOAD_INSTRUCTIONS = """
╔══════════════════════════════════════════════════════════╗
║          MURPHY SYSTEM — MANUAL YOUTUBE UPLOAD           ║
╚══════════════════════════════════════════════════════════╝

The YouTube API packages are not installed or credentials are unavailable.
Your video package has been saved locally for manual upload.

To upload manually:
1. Open https://studio.youtube.com
2. Click "Create" → "Upload videos"
3. Select the video file from: {video_path}
4. Use this title:
   {title}
5. Paste the description from: {summary_path}
6. Set privacy to: {privacy}
7. After upload, record the video URL here for archival.

To enable automatic upload, install the required packages:
  pip install google-api-python-client google-auth-oauthlib

Then run: murphy youtube connect
"""


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class UploadResult:
    """Result of a YouTube upload attempt."""

    upload_id: str
    run_id: str
    video_id: Optional[str]
    video_url: Optional[str]
    upload_status: str
    quota_used: int
    manual_package_path: Optional[str]
    message: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "upload_id": self.upload_id,
            "run_id": self.run_id,
            "video_id": self.video_id,
            "video_url": self.video_url,
            "upload_status": self.upload_status,
            "quota_used": self.quota_used,
            "manual_package_path": self.manual_package_path,
            "message": self.message,
            "created_at": self.created_at,
            "extra": dict(self.extra),
        }


# ---------------------------------------------------------------------------
# Quota tracker
# ---------------------------------------------------------------------------

class _QuotaTracker:
    """Persist daily YouTube API quota usage."""

    def __init__(self, quota_path: Path) -> None:
        self._path = quota_path
        self._lock = threading.Lock()

    def _load(self) -> Dict[str, Any]:
        try:
            if self._path.exists():
                with open(str(self._path), encoding="utf-8") as fh:
                    return json.load(fh)
        except Exception as exc:
            logger.debug("Could not load quota file: %s", exc)
        return {"date": str(date.today()), "used": 0}

    def _save(self, data: Dict[str, Any]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(str(self._path), "w", encoding="utf-8") as fh:
                json.dump(data, fh)
        except Exception as exc:
            logger.warning("Could not save quota file: %s", exc)

    def get_remaining(self) -> int:
        with self._lock:
            data = self._load()
            today = str(date.today())
            if data.get("date") != today:
                return _DAILY_QUOTA_LIMIT
            used = int(data.get("used", 0))
            return max(0, _DAILY_QUOTA_LIMIT - used)

    def consume(self, units: int) -> int:
        """Consume quota units and return remaining. Returns -1 on overflow."""
        with self._lock:
            data = self._load()
            today = str(date.today())
            if data.get("date") != today:
                data = {"date": today, "used": 0}
            used = int(data.get("used", 0))
            if used + units > _DAILY_QUOTA_LIMIT:
                return -1
            data["used"] = used + units
            self._save(data)
            return max(0, _DAILY_QUOTA_LIMIT - data["used"])


# ---------------------------------------------------------------------------
# Main uploader
# ---------------------------------------------------------------------------

class YouTubeUploader:
    """
    YouTube Data API v3 uploader with OAuth2 flow and graceful degradation.

    If google-api-python-client is not installed, saves the package locally
    and logs manual upload instructions.

    Usage::

        uploader = YouTubeUploader()
        result = uploader.upload_video(
            file_path="/tmp/agent_run.mp4",
            metadata=youtube_metadata,
        )
        logger.info("Uploaded: %s", result.video_url)
    """

    def __init__(
        self,
        credentials_path: Optional[Path] = None,
        client_secrets_path: Optional[Path] = None,
        quota_path: Optional[Path] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._credentials_path = credentials_path or _CREDENTIALS_FILE
        self._client_secrets_path = client_secrets_path or _CLIENT_SECRETS_FILE
        self._quota = _QuotaTracker(quota_path or _QUOTA_FILE)
        self._history: List[Dict[str, Any]] = []
        self._api_available = self._check_api_available()
        logger.info(
            "YouTubeUploader initialised (api_available=%s)", self._api_available
        )

    def _check_api_available(self) -> bool:
        """Check whether google-api-python-client is installed."""
        try:
            import google_auth_oauthlib  # noqa: F401
            import googleapiclient  # noqa: F401
            return True
        except ImportError:
            return False

    def is_authenticated(self) -> bool:
        """Return True if valid credentials are stored."""
        if not self._credentials_path.exists():
            return False
        try:
            with open(str(self._credentials_path), encoding="utf-8") as fh:
                creds = json.load(fh)
            return bool(creds.get("token") or creds.get("access_token"))
        except Exception as exc:
            logger.debug("Credentials file unreadable: %s", exc)
            return False

    def initiate_oauth_flow(self) -> bool:
        """
        Run the OAuth2 consent flow. Opens browser and waits for callback.
        Returns True on success, False on failure.
        """
        if not self._api_available:
            logger.warning(
                "Cannot initiate OAuth: google-api-python-client not installed. "
                "Run: pip install google-api-python-client google-auth-oauthlib"
            )
            return False

        if not self._client_secrets_path.exists():
            logger.warning(
                "client_secrets.json not found at %s. "
                "Download it from Google Cloud Console and place it there.",
                self._client_secrets_path,
            )
            return False

        try:
            from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: F401

            flow = InstalledAppFlow.from_client_secrets_file(
                str(self._client_secrets_path),
                scopes=[_YOUTUBE_UPLOAD_SCOPE, _YOUTUBE_READONLY_SCOPE],
            )
            credentials = flow.run_local_server(port=0)
            self._save_credentials(credentials)
            logger.info("OAuth flow completed — credentials saved to %s", self._credentials_path)
            return True
        except Exception as exc:
            logger.error("OAuth flow failed: %s", exc)
            return False

    def _save_credentials(self, credentials: Any) -> None:
        """Persist OAuth2 credentials to disk."""
        try:
            self._credentials_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": list(credentials.scopes or []),
            }
            with open(str(self._credentials_path), "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except Exception as exc:
            logger.error("Failed to save credentials: %s", exc)

    def _load_credentials(self) -> Optional[Any]:
        """Load and refresh stored OAuth2 credentials."""
        if not self._api_available:
            return None
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
                scopes=data.get("scopes", [_YOUTUBE_UPLOAD_SCOPE]),
            )
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self._save_credentials(creds)
            return creds
        except Exception as exc:
            logger.error("Failed to load credentials: %s", exc)
            return None

    def upload_video(
        self,
        file_path: str,
        metadata: Any,
    ) -> UploadResult:
        """
        Upload a video to YouTube with the given metadata.
        Gracefully degrades to local save if API unavailable.
        """
        upload_id = str(uuid.uuid4())

        remaining = self._quota.get_remaining()
        if remaining < _UPLOAD_QUOTA_COST:
            logger.warning(
                "YouTube quota nearly exhausted (remaining=%d, needed=%d). "
                "Saving locally instead.",
                remaining,
                _UPLOAD_QUOTA_COST,
            )
            return self._save_locally(upload_id, metadata, file_path, reason="quota_exhausted")

        if not self._api_available:
            logger.info("YouTube API packages not installed — saving locally for manual upload")
            return self._save_locally(upload_id, metadata, file_path, reason="api_unavailable")

        if not self.is_authenticated():
            logger.info("No YouTube credentials — saving locally for manual upload")
            return self._save_locally(upload_id, metadata, file_path, reason="not_authenticated")

        return self._do_upload(upload_id, file_path, metadata)

    def _do_upload(self, upload_id: str, file_path: str, metadata: Any) -> UploadResult:
        """Perform the actual YouTube API upload with resumable support."""
        try:
            from googleapiclient.discovery import build  # noqa: F401
            from googleapiclient.http import MediaFileUpload  # noqa: F401

            creds = self._load_credentials()
            if creds is None:
                return self._save_locally(upload_id, metadata, file_path, reason="credential_load_failed")

            youtube = build("youtube", "v3", credentials=creds)

            body = {
                "snippet": {
                    "title": metadata.title,
                    "description": metadata.description,
                    "tags": list(metadata.tags),
                    "categoryId": metadata.category_id,
                },
                "status": {
                    "privacyStatus": metadata.privacy,
                    "selfDeclaredMadeForKids": False,
                },
            }

            if os.path.exists(file_path):
                media = MediaFileUpload(
                    file_path,
                    chunksize=_CHUNK_SIZE,
                    resumable=True,
                    mimetype="video/*",
                )
            else:
                return self._save_locally(
                    upload_id, metadata, file_path, reason="file_not_found"
                )

            request = youtube.videos().insert(
                part=",".join(body.keys()),
                body=body,
                media_body=media,
            )

            response = None
            while response is None:
                _status, response = request.next_chunk()

            video_id = response.get("id", "")
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            quota_after = self._quota.consume(_UPLOAD_QUOTA_COST)
            if quota_after < _UPLOAD_QUOTA_COST * 2:
                logger.warning(
                    "YouTube quota low — %d units remaining today", quota_after
                )

            result = UploadResult(
                upload_id=upload_id,
                run_id=metadata.run_id,
                video_id=video_id,
                video_url=video_url,
                upload_status="uploaded",
                quota_used=_UPLOAD_QUOTA_COST,
                manual_package_path=None,
                message=f"Successfully uploaded video_id={video_id}",
            )

            with self._lock:
                capped_append(self._history, result.to_dict(), max_size=_MAX_HISTORY)

            logger.info("Uploaded video_id=%s url=%s", video_id, video_url)
            return result

        except Exception as exc:
            logger.error("YouTube upload failed: %s", exc)
            return self._save_locally(upload_id, metadata, file_path, reason=f"upload_error: {exc!s}"[:80])

    def _save_locally(
        self, upload_id: str, metadata: Any, file_path: str, reason: str
    ) -> UploadResult:
        """Fallback: save manifest locally and log manual upload instructions."""
        manifest_dir = _MURPHY_DIR / "pending_uploads"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = manifest_dir / f"{upload_id}.json"

        manifest = {
            "upload_id": upload_id,
            "run_id": metadata.run_id,
            "file_path": file_path,
            "title": metadata.title,
            "description": metadata.description,
            "privacy": metadata.privacy,
            "reason": reason,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with open(str(manifest_path), "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, indent=2)
        except Exception as exc:
            logger.warning("Could not write manifest: %s", exc)

        instructions = _MANUAL_UPLOAD_INSTRUCTIONS.format(
            video_path=file_path,
            title=metadata.title,
            summary_path=str(manifest_path),
            privacy=metadata.privacy,
        )
        logger.info(instructions)

        result = UploadResult(
            upload_id=upload_id,
            run_id=metadata.run_id,
            video_id=None,
            video_url=None,
            upload_status="saved_locally",
            quota_used=0,
            manual_package_path=str(manifest_path),
            message=f"Saved locally for manual upload. Reason: {reason}",
        )

        with self._lock:
            capped_append(self._history, result.to_dict(), max_size=_MAX_HISTORY)

        return result

    def get_quota_status(self) -> Dict[str, Any]:
        """Return current quota status."""
        remaining = self._quota.get_remaining()
        return {
            "daily_limit": _DAILY_QUOTA_LIMIT,
            "remaining": remaining,
            "used": _DAILY_QUOTA_LIMIT - remaining,
            "upload_cost": _UPLOAD_QUOTA_COST,
            "uploads_remaining_today": remaining // _UPLOAD_QUOTA_COST,
        }

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent upload history."""
        with self._lock:
            return list(self._history[-limit:])
