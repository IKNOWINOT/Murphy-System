"""
Media Handler for the Murphy Matrix Bridge.

Manages records of media artifacts that Murphy subsystems want to share
in Matrix rooms.  Actual upload to the Matrix media repository will be
performed by ``matrix-nio`` in a later PR.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum

from .config import MatrixBridgeConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Media type enum
# ---------------------------------------------------------------------------


class MediaType(str, Enum):
    """Describes the content category of a media upload.

    Attributes:
        IMAGE: Raster or vector image (JPEG, PNG, SVG, …).
        FILE: Generic binary or text file.
        AUDIO: Audio recording.
        VIDEO: Video clip.
        REPORT: Structured report document (PDF, HTML, Markdown).
    """

    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"
    REPORT = "report"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class MediaUpload:
    """Record of a media artifact prepared for Matrix upload.

    Attributes:
        upload_id: Unique identifier for this upload record.
        filename: Original file name.
        media_type: :class:`MediaType` category.
        size_bytes: Content length in bytes.
        matrix_mxc_uri: ``mxc://`` URI assigned after upload; ``None``
            until the SDK delivers the file to the homeserver.
        source_module: Murphy module that produced the artifact.
        uploaded_at: ISO-8601 UTC timestamp of when the record was created.
        metadata: Arbitrary key/value metadata (MIME type, dimensions, etc.).
    """

    upload_id: str
    filename: str
    media_type: MediaType
    size_bytes: int
    matrix_mxc_uri: str | None
    source_module: str
    uploaded_at: str
    metadata: dict


# ---------------------------------------------------------------------------
# MediaHandler
# ---------------------------------------------------------------------------


class MediaHandler:
    """Tracks Murphy media artifacts destined for Matrix rooms.

    Upload records are maintained in memory.  The ``matrix_mxc_uri`` field
    remains ``None`` until ``matrix-nio`` is integrated and the actual
    ``/_matrix/media/v3/upload`` request is made.

    Args:
        config: The active :class:`~config.MatrixBridgeConfig`.
    """

    def __init__(self, config: MatrixBridgeConfig) -> None:
        self._config = config
        self._uploads: dict[str, MediaUpload] = {}
        logger.debug("MediaHandler initialised")

    # ------------------------------------------------------------------
    # Upload lifecycle
    # ------------------------------------------------------------------

    def prepare_upload(
        self,
        filename: str,
        content: bytes,
        media_type: MediaType,
        source_module: str,
        extra_metadata: dict | None = None,
    ) -> MediaUpload:
        """Create a :class:`MediaUpload` record for *content*.

        The content is **not** sent to the homeserver here — that requires
        ``matrix-nio`` (pending PR).  The ``matrix_mxc_uri`` is set to
        ``None`` and a warning is logged.

        Args:
            filename: Original filename to report to Matrix clients.
            content: Raw bytes of the artifact.
            media_type: :class:`MediaType` category.
            source_module: Murphy module producing the artifact.
            extra_metadata: Optional additional metadata fields.

        Returns:
            A new :class:`MediaUpload` record stored in the handler.

        Raises:
            ValueError: If *content* exceeds
                :attr:`~config.MatrixBridgeConfig.media_upload_max_bytes`.
        """
        if len(content) > self._config.media_upload_max_bytes:
            raise ValueError(
                f"Content size {len(content)} bytes exceeds limit "
                f"{self._config.media_upload_max_bytes} bytes"
            )

        sha256 = hashlib.sha256(content).hexdigest()
        metadata: dict = {
            "sha256": sha256,
            "content_length": len(content),
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        upload = MediaUpload(
            upload_id=str(uuid.uuid4()),
            filename=filename,
            media_type=media_type,
            size_bytes=len(content),
            matrix_mxc_uri=None,
            source_module=source_module,
            uploaded_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata,
        )
        self._uploads[upload.upload_id] = upload

        logger.warning(
            "MediaHandler: upload record created for '%s' (id=%s) but "
            "matrix_mxc_uri is None — matrix-nio SDK upload pending",
            filename,
            upload.upload_id,
        )
        return upload

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_upload(self, upload_id: str) -> MediaUpload | None:
        """Return a :class:`MediaUpload` record by its ID.

        Args:
            upload_id: The :attr:`MediaUpload.upload_id` to look up.

        Returns:
            The :class:`MediaUpload`, or ``None`` if not found.
        """
        return self._uploads.get(upload_id)

    def list_uploads(self, source_module: str | None = None) -> list[MediaUpload]:
        """List all recorded uploads, optionally filtered by module.

        Args:
            source_module: If provided, only return uploads from this module.

        Returns:
            List of :class:`MediaUpload` records, ordered by upload time.
        """
        uploads = list(self._uploads.values())
        if source_module is not None:
            uploads = [u for u in uploads if u.source_module == source_module]
        uploads.sort(key=lambda u: u.uploaded_at)
        return uploads

    # ------------------------------------------------------------------
    # Matrix message builder
    # ------------------------------------------------------------------

    def build_matrix_message(self, upload: MediaUpload) -> dict:
        """Build the ``m.room.message`` content dict for a media upload.

        If the ``matrix_mxc_uri`` has not yet been populated, the message
        falls back to an ``m.text`` notice.

        Args:
            upload: The :class:`MediaUpload` to represent as a Matrix event.

        Returns:
            A dictionary suitable for use as Matrix event content.
        """
        if upload.matrix_mxc_uri is None:
            return {
                "msgtype": "m.notice",
                "body": (
                    f"⚠️ Media not yet uploaded: `{upload.filename}` "
                    f"({upload.size_bytes} bytes, {upload.media_type.value}) "
                    "— matrix-nio upload pending"
                ),
            }

        msgtype_map: dict[MediaType, str] = {
            MediaType.IMAGE: "m.image",
            MediaType.AUDIO: "m.audio",
            MediaType.VIDEO: "m.video",
            MediaType.FILE: "m.file",
            MediaType.REPORT: "m.file",
        }
        msgtype = msgtype_map.get(upload.media_type, "m.file")

        content: dict = {
            "msgtype": msgtype,
            "url": upload.matrix_mxc_uri,
            "body": upload.filename,
            "info": {
                "size": upload.size_bytes,
            },
        }
        return content

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise all upload records to a JSON-compatible dict.

        Returns:
            Dictionary keyed by ``upload_id``.
        """
        return {
            uid: {**asdict(u), "media_type": u.media_type.value}
            for uid, u in self._uploads.items()
        }
