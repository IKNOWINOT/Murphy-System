"""
Digital Asset Generator Module — Murphy System

Provides a unified pipeline for generating digital creative assets across
multiple target platforms: Unreal Engine, Autodesk Maya, Blender, Fortnite
Creative/UEFN, and general-purpose game development toolchains.

Supports:
  - Full picture array generation for video game sprite sheets and texture atlases
  - 3D model descriptor generation (FBX/glTF/USD metadata)
  - Material and shader parameter generation
  - Level/map descriptor generation for Unreal and Fortnite Creative
  - Animation sequence descriptor generation
  - Batch asset pipeline orchestration with dependency resolution

All outputs are structured metadata descriptors suitable for ingestion by
the target DCC (Digital Content Creation) tools. Actual binary rendering
is delegated to the respective tool APIs/SDKs.
"""

import enum
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
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


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AssetType(enum.Enum):
    """Asset type (Enum subclass)."""
    TEXTURE = "texture"
    SPRITE_SHEET = "sprite_sheet"
    TEXTURE_ATLAS = "texture_atlas"
    MODEL_3D = "model_3d"
    MATERIAL = "material"
    ANIMATION = "animation"
    LEVEL_MAP = "level_map"
    PARTICLE_EFFECT = "particle_effect"
    AUDIO_CUE = "audio_cue"
    UI_ELEMENT = "ui_element"


class TargetPlatform(enum.Enum):
    """Target platform (Enum subclass)."""
    UNREAL_ENGINE = "unreal_engine"
    MAYA = "maya"
    BLENDER = "blender"
    FORTNITE_CREATIVE = "fortnite_creative"
    UNITY = "unity"
    GODOT = "godot"
    GENERIC = "generic"


class AssetFormat(enum.Enum):
    """Asset format (Enum subclass)."""
    FBX = "fbx"
    GLTF = "gltf"
    USD = "usd"
    OBJ = "obj"
    PNG = "png"
    EXR = "exr"
    TGA = "tga"
    PSD = "psd"
    UASSET = "uasset"
    UMAP = "umap"
    MA = "ma"         # Maya ASCII
    MB = "mb"         # Maya Binary
    BLEND = "blend"


class PipelineStatus(enum.Enum):
    """Pipeline status (Enum subclass)."""
    QUEUED = "queued"
    VALIDATING = "validating"
    GENERATING = "generating"
    POST_PROCESSING = "post_processing"
    COMPLETE = "complete"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AssetDescriptor:
    """Describes a single digital asset to be generated."""
    asset_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = ""
    asset_type: AssetType = AssetType.TEXTURE
    target_platform: TargetPlatform = TargetPlatform.GENERIC
    output_format: AssetFormat = AssetFormat.PNG
    resolution: Dict[str, int] = field(default_factory=lambda: {"width": 1024, "height": 1024})
    parameters: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "name": self.name,
            "asset_type": self.asset_type.value,
            "target_platform": self.target_platform.value,
            "output_format": self.output_format.value,
            "resolution": self.resolution,
            "parameters": self.parameters,
            "tags": self.tags,
            "metadata": self.metadata,
        }


@dataclass
class PictureArrayDescriptor:
    """Describes a full picture array (sprite sheet / texture atlas)."""
    array_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = ""
    frame_count: int = 16
    columns: int = 4
    rows: int = 4
    frame_width: int = 256
    frame_height: int = 256
    target_platform: TargetPlatform = TargetPlatform.GENERIC
    animation_fps: int = 24
    parameters: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_width(self) -> int:
        return self.columns * self.frame_width

    @property
    def total_height(self) -> int:
        return self.rows * self.frame_height

    def to_dict(self) -> Dict[str, Any]:
        return {
            "array_id": self.array_id,
            "name": self.name,
            "frame_count": self.frame_count,
            "columns": self.columns,
            "rows": self.rows,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "total_width": self.total_width,
            "total_height": self.total_height,
            "target_platform": self.target_platform.value,
            "animation_fps": self.animation_fps,
            "parameters": self.parameters,
        }


# ---------------------------------------------------------------------------
# Platform-specific configuration presets
# ---------------------------------------------------------------------------

PLATFORM_PRESETS: Dict[str, Dict[str, Any]] = {
    "unreal_engine": {
        "texture_formats": ["png", "tga", "exr"],
        "model_formats": ["fbx", "gltf", "usd"],
        "level_format": "umap",
        "asset_format": "uasset",
        "max_texture_resolution": 8192,
        "default_texture_resolution": 2048,
        "coordinate_system": "left_handed_z_up",
        "unit_scale": "centimeters",
        "supported_features": [
            "nanite_mesh", "lumen_lighting", "virtual_texture",
            "world_partition", "data_layers", "pcg_framework",
            "niagara_particles", "metahuman_integration",
            "chaos_physics", "mass_entity",
        ],
    },
    "maya": {
        "texture_formats": ["png", "exr", "tga", "psd"],
        "model_formats": ["ma", "mb", "fbx", "obj"],
        "max_texture_resolution": 8192,
        "default_texture_resolution": 2048,
        "coordinate_system": "right_handed_y_up",
        "unit_scale": "centimeters",
        "supported_features": [
            "arnold_renderer", "bifrost", "mash",
            "xgen", "uv_toolkit", "blend_shapes",
            "skin_cluster", "ncloth", "nhair",
        ],
    },
    "blender": {
        "texture_formats": ["png", "exr", "tga"],
        "model_formats": ["blend", "fbx", "gltf", "obj", "usd"],
        "max_texture_resolution": 8192,
        "default_texture_resolution": 2048,
        "coordinate_system": "right_handed_z_up",
        "unit_scale": "meters",
        "supported_features": [
            "cycles_renderer", "eevee_renderer", "geometry_nodes",
            "sculpting", "grease_pencil", "compositor",
            "particle_system", "cloth_simulation", "fluid_simulation",
        ],
    },
    "fortnite_creative": {
        "texture_formats": ["png", "tga"],
        "model_formats": ["fbx", "uasset"],
        "level_format": "umap",
        "max_texture_resolution": 2048,
        "default_texture_resolution": 1024,
        "coordinate_system": "left_handed_z_up",
        "unit_scale": "centimeters",
        "supported_features": [
            "verse_scripting", "creative_devices",
            "island_templates", "prop_manipulation",
            "trigger_system", "hud_messages",
            "item_spawners", "vehicle_spawners",
            "music_sequencer", "visual_effects",
        ],
    },
    "unity": {
        "texture_formats": ["png", "exr", "tga", "psd"],
        "model_formats": ["fbx", "gltf", "obj"],
        "max_texture_resolution": 8192,
        "default_texture_resolution": 2048,
        "coordinate_system": "left_handed_y_up",
        "unit_scale": "meters",
        "supported_features": [
            "urp_pipeline", "hdrp_pipeline", "shader_graph",
            "vfx_graph", "timeline", "cinemachine",
            "burst_compiler", "dots_ecs",
        ],
    },
    "godot": {
        "texture_formats": ["png", "exr"],
        "model_formats": ["gltf", "obj", "fbx"],
        "max_texture_resolution": 4096,
        "default_texture_resolution": 1024,
        "coordinate_system": "right_handed_y_up",
        "unit_scale": "meters",
        "supported_features": [
            "gdscript", "visual_shader", "particle_gpu",
            "lightmapper", "navigation_mesh", "tilemap",
        ],
    },
}


# ---------------------------------------------------------------------------
# Asset generation pipeline
# ---------------------------------------------------------------------------

class DigitalAssetGenerator:
    """Orchestrates digital asset generation across target platforms."""

    def __init__(self):
        self._lock = threading.RLock()
        self._assets: Dict[str, Dict[str, Any]] = {}
        self._picture_arrays: Dict[str, Dict[str, Any]] = {}
        self._pipelines: Dict[str, Dict[str, Any]] = {}
        self._generation_log: List[Dict[str, Any]] = []

    # -- Asset generation ---------------------------------------------------

    def generate_asset(self, descriptor: AssetDescriptor) -> Dict[str, Any]:
        """Generate a single asset descriptor with platform-specific metadata."""
        with self._lock:
            platform = descriptor.target_platform.value
            preset = PLATFORM_PRESETS.get(platform, PLATFORM_PRESETS.get("generic", {}))

            # Validate format compatibility
            valid_formats = preset.get("texture_formats", []) + preset.get("model_formats", [])
            fmt = descriptor.output_format.value
            if valid_formats and fmt not in valid_formats:
                return {
                    "success": False,
                    "error": f"Format '{fmt}' not supported for platform '{platform}'. "
                             f"Supported: {valid_formats}",
                    "asset_id": descriptor.asset_id,
                }

            # Validate resolution
            max_res = preset.get("max_texture_resolution", 8192)
            if descriptor.resolution.get("width", 0) > max_res or \
               descriptor.resolution.get("height", 0) > max_res:
                return {
                    "success": False,
                    "error": f"Resolution exceeds platform max ({max_res}x{max_res})",
                    "asset_id": descriptor.asset_id,
                }

            result = {
                "success": True,
                "asset_id": descriptor.asset_id,
                "name": descriptor.name,
                "asset_type": descriptor.asset_type.value,
                "target_platform": platform,
                "output_format": fmt,
                "resolution": descriptor.resolution,
                "platform_config": {
                    "coordinate_system": preset.get("coordinate_system", "right_handed_y_up"),
                    "unit_scale": preset.get("unit_scale", "meters"),
                    "supported_features": preset.get("supported_features", []),
                },
                "parameters": descriptor.parameters,
                "tags": descriptor.tags,
                "generated_at": time.time(),
                "status": PipelineStatus.COMPLETE.value,
            }

            self._assets[descriptor.asset_id] = result
            capped_append(self._generation_log, {
                "action": "generate_asset",
                "asset_id": descriptor.asset_id,
                "timestamp": time.time(),
            })
            return result

    # -- Picture array generation -------------------------------------------

    def generate_picture_array(self, descriptor: PictureArrayDescriptor) -> Dict[str, Any]:
        """Generate a full picture array (sprite sheet / texture atlas) descriptor."""
        with self._lock:
            platform = descriptor.target_platform.value
            preset = PLATFORM_PRESETS.get(platform, {})
            max_res = preset.get("max_texture_resolution", 8192)

            if descriptor.total_width > max_res or descriptor.total_height > max_res:
                return {
                    "success": False,
                    "error": f"Total array size ({descriptor.total_width}x{descriptor.total_height}) "
                             f"exceeds platform max ({max_res}x{max_res})",
                    "array_id": descriptor.array_id,
                }

            frames = []
            for i in range(descriptor.frame_count):
                row = i // descriptor.columns
                col = i % descriptor.columns
                frames.append({
                    "frame_index": i,
                    "x": col * descriptor.frame_width,
                    "y": row * descriptor.frame_height,
                    "width": descriptor.frame_width,
                    "height": descriptor.frame_height,
                    "duration_ms": round(1000.0 / descriptor.animation_fps, 2),
                })

            result = {
                "success": True,
                "array_id": descriptor.array_id,
                "name": descriptor.name,
                "total_width": descriptor.total_width,
                "total_height": descriptor.total_height,
                "frame_count": descriptor.frame_count,
                "columns": descriptor.columns,
                "rows": descriptor.rows,
                "animation_fps": descriptor.animation_fps,
                "frames": frames,
                "target_platform": platform,
                "parameters": descriptor.parameters,
                "generated_at": time.time(),
                "status": PipelineStatus.COMPLETE.value,
            }

            self._picture_arrays[descriptor.array_id] = result
            capped_append(self._generation_log, {
                "action": "generate_picture_array",
                "array_id": descriptor.array_id,
                "frame_count": descriptor.frame_count,
                "timestamp": time.time(),
            })
            return result

    # -- Pipeline orchestration ---------------------------------------------

    def create_pipeline(self, pipeline_id: str, name: str,
                        assets: Optional[List[AssetDescriptor]] = None,
                        arrays: Optional[List[PictureArrayDescriptor]] = None,
                        description: str = "") -> Dict[str, Any]:
        """Create a batch asset generation pipeline."""
        with self._lock:
            pipeline = {
                "pipeline_id": pipeline_id,
                "name": name,
                "description": description,
                "assets": [a.to_dict() for a in (assets or [])],
                "arrays": [a.to_dict() for a in (arrays or [])],
                "status": PipelineStatus.QUEUED.value,
                "created_at": time.time(),
                "results": [],
            }
            self._pipelines[pipeline_id] = pipeline
            return dict(pipeline)

    def execute_pipeline(self, pipeline_id: str) -> Dict[str, Any]:
        """Execute all assets in a pipeline."""
        with self._lock:
            pipeline = self._pipelines.get(pipeline_id)
            if pipeline is None:
                return {"success": False, "error": f"Unknown pipeline: {pipeline_id}"}

            pipeline["status"] = PipelineStatus.GENERATING.value
            results = []

            # Generate individual assets
            for asset_dict in pipeline.get("assets", []):
                desc = AssetDescriptor(
                    asset_id=asset_dict.get("asset_id", str(uuid.uuid4())[:12]),
                    name=asset_dict.get("name", ""),
                    asset_type=AssetType(asset_dict.get("asset_type", "texture")),
                    target_platform=TargetPlatform(asset_dict.get("target_platform", "generic")),
                    output_format=AssetFormat(asset_dict.get("output_format", "png")),
                    resolution=asset_dict.get("resolution", {"width": 1024, "height": 1024}),
                    parameters=asset_dict.get("parameters", {}),
                    tags=asset_dict.get("tags", []),
                )
                result = self.generate_asset(desc)
                results.append(result)

            # Generate picture arrays
            for arr_dict in pipeline.get("arrays", []):
                desc = PictureArrayDescriptor(
                    array_id=arr_dict.get("array_id", str(uuid.uuid4())[:12]),
                    name=arr_dict.get("name", ""),
                    frame_count=arr_dict.get("frame_count", 16),
                    columns=arr_dict.get("columns", 4),
                    rows=arr_dict.get("rows", 4),
                    frame_width=arr_dict.get("frame_width", 256),
                    frame_height=arr_dict.get("frame_height", 256),
                    target_platform=TargetPlatform(arr_dict.get("target_platform", "generic")),
                    animation_fps=arr_dict.get("animation_fps", 24),
                    parameters=arr_dict.get("parameters", {}),
                )
                result = self.generate_picture_array(desc)
                results.append(result)

            all_ok = all(r.get("success") for r in results)
            pipeline["status"] = PipelineStatus.COMPLETE.value if all_ok else PipelineStatus.FAILED.value
            pipeline["results"] = results

            return {
                "pipeline_id": pipeline_id,
                "success": all_ok,
                "results": results,
                "status": pipeline["status"],
            }

    # -- Query methods ------------------------------------------------------

    def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._assets.get(asset_id)

    def get_picture_array(self, array_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._picture_arrays.get(array_id)

    def get_pipeline(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            p = self._pipelines.get(pipeline_id)
            return dict(p) if p else None

    def list_platforms(self) -> List[str]:
        return sorted(PLATFORM_PRESETS.keys())

    def get_platform_preset(self, platform: str) -> Optional[Dict[str, Any]]:
        return PLATFORM_PRESETS.get(platform)

    def list_asset_types(self) -> List[str]:
        return [t.value for t in AssetType]

    def list_formats(self) -> List[str]:
        return [f.value for f in AssetFormat]

    # -- Statistics ---------------------------------------------------------

    def statistics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_assets": len(self._assets),
                "total_picture_arrays": len(self._picture_arrays),
                "total_pipelines": len(self._pipelines),
                "generation_log_entries": len(self._generation_log),
                "supported_platforms": self.list_platforms(),
                "supported_asset_types": self.list_asset_types(),
                "supported_formats": self.list_formats(),
            }


# ---------------------------------------------------------------------------
# Module-level status helper
# ---------------------------------------------------------------------------

def get_status() -> Dict[str, Any]:
    """Return module-level status information."""
    return {
        "module": "digital_asset_generator",
        "version": "1.0.0",
        "status": "operational",
        "supported_platforms": sorted(PLATFORM_PRESETS.keys()),
        "asset_types": [t.value for t in AssetType],
        "output_formats": [f.value for f in AssetFormat],
        "pipeline_statuses": [s.value for s in PipelineStatus],
        "platform_count": len(PLATFORM_PRESETS),
        "timestamp": time.time(),
    }
