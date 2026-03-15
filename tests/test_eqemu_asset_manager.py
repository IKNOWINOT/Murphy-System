"""
Tests for the EQEmu asset manager module.

Validates:
  - Asset source registry (all 7 upstream EQEmu repos mapped)
  - Download command generation for git clone and release methods
  - Asset status tracking (register, verify, error)
  - Release URL resolution for binary components
"""

import pytest

from src.eq.eqemu_asset_manager import (
    AssetRecord,
    AssetSource,
    AssetStatus,
    DownloadMethod,
    EQEMU_ASSET_SOURCES,
    EQEmuAssetManager,
    EQEmuComponent,
)


# ===================================================================
# Asset Source Registry Tests
# ===================================================================

class TestAssetSourceRegistry:

    def test_seven_sources_registered(self):
        assert len(EQEMU_ASSET_SOURCES) == 7

    def test_server_source_points_to_eqemu(self):
        src = EQEMU_ASSET_SOURCES[EQEmuComponent.SERVER_SOURCE]
        assert src.repo_owner == "EQEmu"
        assert src.repo_name == "EQEmu"
        assert "github.com" in src.repo_url

    def test_server_binary_has_release_tag(self):
        src = EQEMU_ASSET_SOURCES[EQEmuComponent.SERVER_BINARY]
        assert src.release_tag is not None
        assert src.release_tag.startswith("v")

    def test_akk_stack_source(self):
        src = EQEMU_ASSET_SOURCES[EQEmuComponent.AKK_STACK]
        assert src.repo_name == "akk-stack"

    def test_spire_source(self):
        src = EQEMU_ASSET_SOURCES[EQEmuComponent.SPIRE]
        assert src.repo_name == "spire"

    def test_all_sources_have_urls(self):
        for comp, src in EQEMU_ASSET_SOURCES.items():
            assert src.repo_url, f"Missing URL for {comp}"
            assert src.repo_owner, f"Missing owner for {comp}"
            assert src.repo_name, f"Missing name for {comp}"

    def test_all_sources_have_descriptions(self):
        for comp, src in EQEMU_ASSET_SOURCES.items():
            assert src.description, f"Missing description for {comp}"


# ===================================================================
# Asset Manager Core Tests
# ===================================================================

class TestEQEmuAssetManager:

    def test_default_install_dir(self):
        mgr = EQEmuAssetManager()
        assert "eqemu-server" in mgr.install_dir

    def test_custom_install_dir(self):
        mgr = EQEmuAssetManager(install_dir="/opt/eq")
        assert mgr.install_dir == "/opt/eq"

    def test_total_components(self):
        mgr = EQEmuAssetManager()
        assert mgr.total_components == 7

    def test_initial_downloaded_count_zero(self):
        mgr = EQEmuAssetManager()
        assert mgr.downloaded_count == 0

    def test_initial_verified_count_zero(self):
        mgr = EQEmuAssetManager()
        assert mgr.verified_count == 0

    def test_get_asset_source(self):
        mgr = EQEmuAssetManager()
        src = mgr.get_asset_source(EQEmuComponent.SERVER_SOURCE)
        assert src.repo_owner == "EQEmu"

    def test_get_asset_status_initial(self):
        mgr = EQEmuAssetManager()
        record = mgr.get_asset_status(EQEmuComponent.SERVER_SOURCE)
        assert record.status == AssetStatus.NOT_DOWNLOADED

    def test_register_download(self):
        mgr = EQEmuAssetManager()
        record = mgr.register_download(
            EQEmuComponent.SERVER_SOURCE,
            local_path="/opt/eq/server",
            version="v23.10.3",
            size_bytes=159580483,
        )
        assert record.status == AssetStatus.DOWNLOADED
        assert record.local_path == "/opt/eq/server"
        assert record.version == "v23.10.3"
        assert mgr.downloaded_count == 1

    def test_mark_verified(self):
        mgr = EQEmuAssetManager()
        mgr.register_download(
            EQEmuComponent.SERVER_BINARY,
            local_path="/opt/eq/bin",
            version="v23.10.3",
            size_bytes=100,
        )
        mgr.mark_verified(EQEmuComponent.SERVER_BINARY)
        record = mgr.get_asset_status(EQEmuComponent.SERVER_BINARY)
        assert record.status == AssetStatus.VERIFIED
        assert mgr.verified_count == 1

    def test_mark_error(self):
        mgr = EQEmuAssetManager()
        mgr.mark_error(EQEmuComponent.DATABASE, "Connection refused")
        record = mgr.get_asset_status(EQEmuComponent.DATABASE)
        assert record.status == AssetStatus.ERROR

    def test_get_all_statuses(self):
        mgr = EQEmuAssetManager()
        statuses = mgr.get_all_statuses()
        assert len(statuses) == 7
        assert all(isinstance(r, AssetRecord) for r in statuses.values())


# ===================================================================
# Download Command Generation Tests
# ===================================================================

class TestDownloadCommands:

    def test_git_clone_command(self):
        mgr = EQEmuAssetManager()
        cmd = mgr.get_download_command(EQEmuComponent.SERVER_SOURCE, DownloadMethod.GIT_CLONE)
        assert "git clone" in cmd
        assert "EQEmu/EQEmu" in cmd
        assert "--depth 1" in cmd

    def test_release_zip_command_for_binary(self):
        mgr = EQEmuAssetManager()
        cmd = mgr.get_download_command(EQEmuComponent.SERVER_BINARY, DownloadMethod.RELEASE_ZIP)
        assert "curl" in cmd or "wget" in cmd

    def test_release_url_for_binary(self):
        mgr = EQEmuAssetManager()
        url = mgr.get_release_url(EQEmuComponent.SERVER_BINARY)
        assert url is not None
        assert "releases/download" in url
        assert "eqemu-server-linux-x64.zip" in url

    def test_release_url_windows(self):
        mgr = EQEmuAssetManager()
        url = mgr.get_release_url(EQEmuComponent.SERVER_BINARY, platform="windows-x64")
        assert url is not None
        assert "eqemu-server-windows-x64.zip" in url

    def test_release_zip_command_cleans_up(self):
        mgr = EQEmuAssetManager()
        cmd = mgr.get_download_command(EQEmuComponent.SERVER_BINARY, DownloadMethod.RELEASE_ZIP)
        assert "rm -f" in cmd  # ZIP cleanup after extraction

    def test_release_url_none_for_source_only(self):
        mgr = EQEmuAssetManager()
        url = mgr.get_release_url(EQEmuComponent.SPIRE)
        assert url is None

    def test_docker_compose_command_for_akk_stack(self):
        mgr = EQEmuAssetManager()
        cmd = mgr.get_download_command(EQEmuComponent.AKK_STACK, DownloadMethod.DOCKER_COMPOSE)
        assert "git clone" in cmd or "docker" in cmd


# ===================================================================
# Asset Component Enum Tests
# ===================================================================

class TestEQEmuComponentEnum:

    def test_all_component_values(self):
        expected = {
            "server_source", "server_binary", "database",
            "quests", "maps", "spire", "akk_stack",
        }
        actual = {c.value for c in EQEmuComponent}
        assert actual == expected

    def test_download_method_values(self):
        expected = {"git_clone", "release_zip", "docker_compose"}
        actual = {m.value for m in DownloadMethod}
        assert actual == expected

    def test_asset_status_values(self):
        assert AssetStatus.NOT_DOWNLOADED.value == "not_downloaded"
        assert AssetStatus.DOWNLOADED.value == "downloaded"
        assert AssetStatus.VERIFIED.value == "verified"
        assert AssetStatus.ERROR.value == "error"
