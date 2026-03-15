"""
EQEmu Asset Manager — Discovery, Download Tracking, and Validation

Manages upstream EQEmu GitHub repository assets used by the Murphy System:
  - EQEmu server source and pre-built binaries (EQEmu/EQEmu)
  - akk-stack Docker environment (EQEmu/akk-stack)
  - Spire web toolkit (EQEmu/spire)
  - PEQ database and quest files (ProjectEQ)
  - Zone map utilities

Provides structured metadata for every fetchable component, tracks download
status, and generates the shell commands required to retrieve each asset.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class EQEmuComponent(Enum):
    """Identifiers for each fetchable EQEmu asset."""

    SERVER_SOURCE = "server_source"
    SERVER_BINARY = "server_binary"
    DATABASE = "database"
    QUESTS = "quests"
    MAPS = "maps"
    SPIRE = "spire"
    AKK_STACK = "akk_stack"


class DownloadMethod(Enum):
    """Strategy used to retrieve an asset."""

    GIT_CLONE = "git_clone"
    RELEASE_ZIP = "release_zip"
    DOCKER_COMPOSE = "docker_compose"


class AssetStatus(Enum):
    """Lifecycle state of a tracked asset."""

    NOT_DOWNLOADED = "not_downloaded"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    VERIFIED = "verified"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AssetSource:
    """Upstream location metadata for a single EQEmu component."""

    component: EQEmuComponent
    repo_url: str
    repo_owner: str
    repo_name: str
    branch: str
    release_tag: Optional[str] = None
    description: str = ""


@dataclass
class AssetRecord:
    """Local download state for a single EQEmu component."""

    component: EQEmuComponent
    status: AssetStatus = AssetStatus.NOT_DOWNLOADED
    local_path: str = ""
    downloaded_at: Optional[float] = None
    size_bytes: int = 0
    version: str = ""
    checksum: Optional[str] = None
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Canonical upstream sources
# ---------------------------------------------------------------------------

EQEMU_ASSET_SOURCES: Dict[EQEmuComponent, AssetSource] = {
    EQEmuComponent.SERVER_SOURCE: AssetSource(
        component=EQEmuComponent.SERVER_SOURCE,
        repo_url="https://github.com/EQEmu/EQEmu.git",
        repo_owner="EQEmu",
        repo_name="EQEmu",
        branch="master",
        description="EQEmu C++ server source code",
    ),
    EQEmuComponent.SERVER_BINARY: AssetSource(
        component=EQEmuComponent.SERVER_BINARY,
        repo_url="https://github.com/EQEmu/EQEmu.git",
        repo_owner="EQEmu",
        repo_name="EQEmu",
        branch="master",
        release_tag="v23.10.3",
        description="Pre-built EQEmu server binaries (Linux x64)",
    ),
    EQEmuComponent.DATABASE: AssetSource(
        component=EQEmuComponent.DATABASE,
        repo_url="https://github.com/ProjectEQ/peqphpeditor.git",
        repo_owner="ProjectEQ",
        repo_name="peqphpeditor",
        branch="master",
        description="PEQ database — standard EverQuest content database",
    ),
    EQEmuComponent.QUESTS: AssetSource(
        component=EQEmuComponent.QUESTS,
        repo_url="https://github.com/ProjectEQ/projecteqquests.git",
        repo_owner="ProjectEQ",
        repo_name="projecteqquests",
        branch="master",
        description="PEQ quest scripts (Perl/Lua)",
    ),
    EQEmuComponent.MAPS: AssetSource(
        component=EQEmuComponent.MAPS,
        repo_url="https://github.com/EQEmu/zone-utilities.git",
        repo_owner="EQEmu",
        repo_name="zone-utilities",
        branch="master",
        description="Zone map files and map-editing utilities",
    ),
    EQEmuComponent.SPIRE: AssetSource(
        component=EQEmuComponent.SPIRE,
        repo_url="https://github.com/EQEmu/spire.git",
        repo_owner="EQEmu",
        repo_name="spire",
        branch="master",
        description="Spire — TypeScript web toolkit and quest editor",
    ),
    EQEmuComponent.AKK_STACK: AssetSource(
        component=EQEmuComponent.AKK_STACK,
        repo_url="https://github.com/EQEmu/akk-stack.git",
        repo_owner="EQEmu",
        repo_name="akk-stack",
        branch="master",
        description="akk-stack — containerized EQEmu environment (docker-compose)",
    ),
}

# Release binary download URL template
_RELEASE_URL_TEMPLATE = (
    "https://github.com/{owner}/{repo}/releases/download/{tag}/{asset}"
)

# Platform-specific release asset filenames
PLATFORM_RELEASE_ASSETS = {
    "linux-x64": "eqemu-server-linux-x64.zip",
    "windows-x64": "eqemu-server-windows-x64.zip",
}


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class EQEmuAssetManager:
    """Track, validate, and generate fetch commands for EQEmu assets.

    Parameters
    ----------
    install_dir:
        Root directory where assets are stored.  Defaults to
        ``~/eqemu-server`` and is expanded at init time.
    """

    def __init__(self, install_dir: str = "~/eqemu-server") -> None:
        self._install_dir: str = os.path.expanduser(install_dir)
        self._records: Dict[EQEmuComponent, AssetRecord] = {
            comp: AssetRecord(component=comp)
            for comp in EQEmuComponent
        }

    # -- properties ---------------------------------------------------------

    @property
    def install_dir(self) -> str:
        """Resolved installation directory path."""
        return self._install_dir

    @property
    def total_components(self) -> int:
        """Total number of trackable components."""
        return len(EQEmuComponent)

    @property
    def downloaded_count(self) -> int:
        """Number of components that have been downloaded (or verified)."""
        return sum(
            1
            for r in self._records.values()
            if r.status in (AssetStatus.DOWNLOADED, AssetStatus.VERIFIED)
        )

    @property
    def verified_count(self) -> int:
        """Number of components whose downloads have been verified."""
        return sum(
            1 for r in self._records.values() if r.status is AssetStatus.VERIFIED
        )

    # -- source lookups -----------------------------------------------------

    def get_asset_source(self, component: EQEmuComponent) -> AssetSource:
        """Return the canonical upstream source for *component*."""
        return EQEMU_ASSET_SOURCES[component]

    # -- record management --------------------------------------------------

    def get_asset_status(self, component: EQEmuComponent) -> AssetRecord:
        """Return the current download record for *component*."""
        return self._records[component]

    def get_all_statuses(self) -> Dict[EQEmuComponent, AssetRecord]:
        """Return a snapshot of all asset records."""
        return dict(self._records)

    def register_download(
        self,
        component: EQEmuComponent,
        local_path: str,
        version: str,
        size_bytes: int,
    ) -> AssetRecord:
        """Record a successful download for *component*.

        Parameters
        ----------
        component:
            The component that was downloaded.
        local_path:
            Filesystem path where the asset is stored.
        version:
            Version string (e.g. branch name, release tag).
        size_bytes:
            Total size of the downloaded asset in bytes.

        Returns
        -------
        AssetRecord
            The updated record.
        """
        record = self._records[component]
        record.status = AssetStatus.DOWNLOADED
        record.local_path = local_path
        record.version = version
        record.size_bytes = size_bytes
        record.downloaded_at = time.time()
        record.error_message = None
        return record

    def mark_verified(self, component: EQEmuComponent) -> None:
        """Promote *component* to the VERIFIED state."""
        record = self._records[component]
        if record.status not in (AssetStatus.DOWNLOADED, AssetStatus.VERIFIED):
            raise ValueError(
                f"Cannot verify {component.value}: current status is "
                f"{record.status.value}"
            )
        record.status = AssetStatus.VERIFIED

    def mark_error(self, component: EQEmuComponent, error_msg: str) -> None:
        """Move *component* to the ERROR state with a diagnostic message."""
        record = self._records[component]
        record.status = AssetStatus.ERROR
        record.error_message = error_msg

    # -- command generation -------------------------------------------------

    def get_download_command(
        self,
        component: EQEmuComponent,
        method: DownloadMethod = DownloadMethod.GIT_CLONE,
    ) -> str:
        """Return the shell command that would download *component*.

        Parameters
        ----------
        component:
            The component to generate a download command for.
        method:
            The download strategy to use.

        Returns
        -------
        str
            A single shell command string.
        """
        source = EQEMU_ASSET_SOURCES[component]
        dest = os.path.join(self._install_dir, component.value)

        if method is DownloadMethod.GIT_CLONE:
            return (
                f"git clone --depth 1 --branch {source.branch} "
                f"{source.repo_url} {dest}"
            )

        if method is DownloadMethod.RELEASE_ZIP:
            url = self.get_release_url(component)
            if url is None:
                return f"echo 'No release URL available for {component.value}'"
            return (
                f"curl -fSL -o {dest}.zip {url} "
                f"&& unzip -qo {dest}.zip -d {dest} "
                f"&& rm -f {dest}.zip"
            )

        if method is DownloadMethod.DOCKER_COMPOSE:
            return (
                f"git clone --depth 1 {source.repo_url} {dest} "
                f"&& cd {dest} && docker-compose pull"
            )

        return f"echo 'Unsupported method for {component.value}'"

    def get_release_url(
        self,
        component: EQEmuComponent,
        platform: str = "linux-x64",
    ) -> Optional[str]:
        """Return the GitHub release download URL for *component*, if any.

        Only components with a ``release_tag`` on their ``AssetSource``
        produce a URL.  Currently this applies to ``SERVER_BINARY``.

        *platform* selects the binary variant (``linux-x64`` or
        ``windows-x64``).
        """
        source = EQEMU_ASSET_SOURCES[component]
        if source.release_tag is None:
            return None

        asset_name = PLATFORM_RELEASE_ASSETS.get(
            platform,
            PLATFORM_RELEASE_ASSETS["linux-x64"],
        )
        return _RELEASE_URL_TEMPLATE.format(
            owner=source.repo_owner,
            repo=source.repo_name,
            tag=source.release_tag,
            asset=asset_name,
        )
